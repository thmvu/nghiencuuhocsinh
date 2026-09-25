"""Run locked XGBoost candidates on TRAIN/VALIDATION."""
from itertools import product
from pathlib import Path
import hashlib
import json
import platform
import sys
import time

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.metrics import evaluate_predictions
from src.evaluation.sequential import sequential_predict
from src.models.xgboost_model import XGBoostModel


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_development_data():
    config_path = ROOT / "configs/protocol_a.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / "artifacts/tables/preprocessing_summary.json").read_text())
    if evidence["config_sha256"] != digest(config_path):
        raise ValueError("Protocol A has changed since preprocessing")
    data = {}
    for partition in ("train", "validation"):
        path = ROOT / f"data/processed/{partition}.parquet"
        if digest(path) != evidence["partitions"][partition]["sha256"]:
            raise ValueError(f"{partition} artifact changed")
        data[partition] = pd.read_parquet(path)
        if not data[partition].split.eq(partition).all():
            raise ValueError(f"Incorrect {partition} partition label")
    if not set(data["train"].user_id).isdisjoint(set(data["validation"].user_id)):
        raise ValueError("Student overlap")
    return config, evidence, data["train"], data["validation"]


def run():
    config, evidence, train, validation = load_development_data()
    warmup = config["evaluation"]["warmup"]
    scored = validation[["source_row", "user_id", "order_id", "correct", "history_length"]].copy()
    scored["is_scored"] = validation.scored.astype(bool)
    if not scored.is_scored.eq(scored.history_length.ge(warmup)).all():
        raise ValueError("Scoring mask differs from locked warm-up")
    checkpoint_dir = ROOT / "artifacts/models/rq1_development"
    prediction_dir = ROOT / "data/processed/predictions"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    prediction_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "stage": "validation_development_not_final_test", "test_opened": False,
        "protocol_a_sha256": digest(ROOT / "configs/protocol_a.json"),
        "input_sha256": {k: evidence["partitions"][k]["sha256"] for k in ("train", "validation")},
        "python": platform.python_version(), "selection_metric": "validation_brier_score",
        "results": [], "xgboost_candidates": [], "model_sha256": {},
    }

    grid = config["xgboost"]["grid"]
    order = config["xgboost"]["grid_order"]
    assert order == ["max_depth", "learning_rate", "n_estimators"]
    candidates = list(product(*(grid[key] for key in order)))
    assert len(candidates) == config["xgboost"]["maximum_fits"] == 8
    best = None
    best_score = float("inf")
    for values in candidates:
        params = dict(zip(order, values))
        start = time.perf_counter()
        model = XGBoostModel(**params, seed=config["xgboost"]["seed"]).fit(train)
        before = model.global_parameters_snapshot()
        prediction = scored.copy()
        prediction["probability"] = model.predict_batch(validation)
        if model.global_parameters_snapshot() != before:
            raise RuntimeError("XGBoost fitted parameters changed during prediction")
        small = validation[validation.user_id.isin(sorted(validation.user_id.unique())[:2])]
        seq = sequential_predict(small, model, warmup=warmup)
        lookup = prediction.set_index("source_row")
        np.testing.assert_allclose(seq.probability, lookup.loc[seq.source_row, "probability"], atol=1e-12)
        metrics = evaluate_predictions(prediction)
        record = {**params, **metrics, "fit_evaluate_seconds": time.perf_counter()-start}
        result["xgboost_candidates"].append(record)
        print("XGBoost", record, flush=True)
        if metrics["brier_score"] < best_score:
            best, best_score, selected = model, metrics["brier_score"], record
            prediction.to_parquet(prediction_dir / "validation_XGBoost_selected.parquet", index=False)
    path = checkpoint_dir / "XGBoost.joblib"
    joblib.dump(best, path)
    np.testing.assert_allclose(joblib.load(path).predict_batch(validation.head(20)),
                               best.predict_batch(validation.head(20)), atol=1e-12)
    result["model_sha256"]["XGBoost"] = digest(path)
    result["results"].append({"model": "XGBoost", **selected})
    result["xgboost_selected"] = {key: selected[key] for key in order}
    result["code_sha256"] = {name: digest(ROOT / name) for name in [
        "scripts/train_xgboost.py", "src/models/xgboost_model.py",
        "src/evaluation/metrics.py", "src/evaluation/sequential.py",
    ]}
    result["requirements_sha256"] = digest(ROOT / "requirements-lock.txt")
    (ROOT / "artifacts/tables/xgboost_validation.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    run()

