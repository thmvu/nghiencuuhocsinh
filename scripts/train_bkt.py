"""Fit and assess BKT on TRAIN/VALIDATION under Configuration Lock A."""
from pathlib import Path
import hashlib
import json
import sys
import time

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.metrics import evaluate_predictions
from src.evaluation.sequential import sequential_predict
from src.models.bkt import BKT


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    config_path = ROOT / "configs/protocol_a.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "artifacts/tables/preprocessing_summary.json").read_text(encoding="utf-8"))
    if sha256(config_path) != summary["config_sha256"]:
        raise ValueError("Lock A changed since preprocessing")
    data = {}
    for part in ("train", "validation"):
        path = ROOT / f"data/processed/{part}.parquet"
        if sha256(path) != summary["partitions"][part]["sha256"]:
            raise ValueError(f"{part} partition changed")
        data[part] = pd.read_parquet(path)
        if not data[part].split.eq(part).all():
            raise ValueError(f"wrong {part} split")
    train, validation = data["train"], data["validation"]
    if not set(train.user_id).isdisjoint(set(validation.user_id)):
        raise ValueError("student overlap")
    start = time.perf_counter()
    model = BKT(config=config["bkt"]).fit(train)
    predictions = sequential_predict(validation, model, warmup=config["evaluation"]["warmup"])
    if len(predictions) != len(validation):
        raise ValueError("prediction coverage differs")
    mask = predictions.set_index("source_row").is_scored.reindex(validation.source_row)
    if not mask.to_numpy().tolist() == validation.scored.to_numpy().tolist():
        raise ValueError("evaluation mask differs")
    metrics = evaluate_predictions(predictions)
    predpath = ROOT / "data/processed/predictions/validation_BKT.parquet"
    predpath.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(predpath, index=False)
    path = ROOT / "artifacts/models/rq1_development/BKT.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    restored = joblib.load(path)
    sample = validation[validation.user_id.isin(sorted(validation.user_id.unique())[:2])]
    np.testing.assert_allclose(
        sequential_predict(sample, restored, warmup=config["evaluation"]["warmup"]).probability,
        sequential_predict(sample, model, warmup=config["evaluation"]["warmup"]).probability,
    )
    output = {
        "stage": "validation_development_not_final_test", "test_opened": False,
        "model": "BKT", "metrics": metrics,
        "fit_evaluate_seconds": time.perf_counter() - start,
        "fit_diagnostics": model.fit_diagnostics_,
        "config_sha256": sha256(config_path),
        "input_sha256": {part: summary["partitions"][part]["sha256"] for part in data},
        "model_sha256": sha256(path),
        "code_sha256": {name: sha256(ROOT / name) for name in [
            "scripts/train_bkt.py", "src/models/bkt.py", "src/evaluation/sequential.py",
            "src/evaluation/metrics.py",
        ]},
    }
    (ROOT / "artifacts/tables/bkt_validation.json").write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("stage", "metrics", "fit_evaluate_seconds")}, indent=2))
    return output


if __name__ == "__main__":
    run()
