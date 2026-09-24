"""Locked train/validation experiment. Deliberately never opens test.parquet."""
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

from src.models.baselines import GlobalBaseline, ProblemBaseline
from src.models.pfa import PFA, PFAConvergenceError
from src.evaluation.metrics import evaluate_predictions
from src.evaluation.sequential import sequential_predict


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    config_path = ROOT / "configs/protocol_a.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    prepared = json.loads((ROOT / "artifacts/tables/preprocessing_summary.json").read_text())
    if digest(config_path) != prepared["config_sha256"]:
        raise ValueError("Configuration changed since preprocessing")
    data = {}
    for name in ["train", "validation"]:
        path = ROOT / f"data/processed/{name}.parquet"
        if digest(path) != prepared["partitions"][name]["sha256"]:
            raise ValueError(f"{name} artifact differs from preprocessing evidence")
        data[name] = pd.read_parquet(path)
        if not data[name].split.eq(name).all():
            raise ValueError(f"Wrong partition in {name}")
    train, validation = data["train"], data["validation"]
    assert set(train.user_id).isdisjoint(set(validation.user_id))
    rows = validation[["source_row", "user_id", "order_id", "correct", "history_length"]].copy()
    rows["is_scored"] = validation.scored.astype(bool)
    assert rows.is_scored.eq(rows.history_length.ge(config["evaluation"]["warmup"])).all()
    models_dir = ROOT / "artifacts/models/baselines_pfa"
    models_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir = ROOT / "data/processed/predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    results, candidate_records, fitted = [], [], {}

    def evaluate(name, model):
        snapshot = model.global_parameters_snapshot()
        prediction = rows.copy()
        prediction["probability"] = model.predict_batch(validation)
        assert snapshot == model.global_parameters_snapshot(), "Predict changed fitted parameters"
        # Check vectorized scoring against predict-before-update on actual trajectories.
        sample = validation[validation.user_id.isin(sorted(validation.user_id.unique())[:3])]
        sequential = sequential_predict(sample, model, warmup=config["evaluation"]["warmup"])
        lookup = prediction.set_index("source_row")
        np.testing.assert_allclose(sequential.probability, lookup.loc[sequential.source_row, "probability"], atol=1e-12)
        assert sequential.is_scored.tolist() == lookup.loc[sequential.source_row, "is_scored"].tolist()
        metrics = evaluate_predictions(prediction)
        prediction.to_parquet(predictions_dir / f"validation_{name}.parquet", index=False)
        return metrics

    for name, model in [("Global", GlobalBaseline()), ("Problem", ProblemBaseline(alpha=config["problem_difficulty"]["alpha"]))]:
        start = time.perf_counter()
        model.fit(train)
        metrics = evaluate(name, model)
        results.append({"model": name, **metrics, "fit_evaluate_seconds": time.perf_counter() - start})
        fitted[name] = model
        print(name, metrics, flush=True)

    cfg = config["pfa"]
    candidates = cfg["C_candidates"]
    assert len(candidates) == cfg["maximum_fits"] == 4
    best_model = None
    best_score = float("inf")
    for c in candidates:
        start = time.perf_counter()
        record = {"C": c}
        try:
            model = PFA(C=c, max_iter=cfg["max_iter"], tol=cfg["tol"], seed=cfg["seed"])
            model.fit(train)
            metrics = evaluate(f"PFA_C_{c}", model)
            record.update(status="valid", **metrics)
            if metrics["brier_score"] < best_score:
                best_model, best_score = model, metrics["brier_score"]
                selected_c, selected_metrics = c, metrics
        except PFAConvergenceError as exc:
            record.update(status="invalid", reason=str(exc))
        record["fit_evaluate_seconds"] = time.perf_counter() - start
        candidate_records.append(record)
        print("PFA", record, flush=True)
    if best_model is not None:
        fitted["PFA"] = best_model
        results.append({"model": "PFA", "selected_C": selected_c, **selected_metrics})
    else:
        selected_c = None
    for name, model in fitted.items():
        path = models_dir / f"{name}.joblib"
        joblib.dump(model, path)
        loaded = joblib.load(path)
        np.testing.assert_allclose(loaded.predict_batch(validation.head(20)), model.predict_batch(validation.head(20)))
    output = {
        "stage": "validation_development_not_final_test", "config_sha256": digest(config_path),
        "python": platform.python_version(), "test_opened": False,
        "input_hashes": {k: prepared["partitions"][k]["sha256"] for k in data},
        "selection_metric": "validation_brier_score", "pfa_selected_C": selected_c,
        "results": results, "pfa_candidates": candidate_records,
        "model_sha256": {name: digest(models_dir / f"{name}.joblib") for name in fitted},
        "code_sha256": {name: digest(ROOT / name) for name in [
            "scripts/train_baselines_pfa.py", "src/models/pfa.py", "src/models/baselines.py",
            "src/evaluation/metrics.py", "src/evaluation/sequential.py",
        ]},
        "requirements_sha256": digest(ROOT / "requirements-lock.txt"),
    }
    (ROOT / "artifacts/tables/baselines_pfa_validation.json").write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    if best_model is None:
        raise RuntimeError("All locked PFA candidates invalid; report saved, do not expand budget automatically")
    return output


if __name__ == "__main__":
    run()
