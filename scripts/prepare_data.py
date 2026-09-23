"""Build Gate A data artifacts without fitting models or reporting test labels."""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocessing.pipeline import (
    clean_interactions, apply_split, add_history_features, add_problem_difficulty,
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    config_path = ROOT / "configs/protocol_a.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    warmup = config["evaluation"]["warmup"]
    folds = config["problem_difficulty"]["n_splits"]
    alpha = config["problem_difficulty"]["alpha"]
    if config["history"]["cold_start_accuracy"] != 0.5:
        raise ValueError("History implementation uses the locked cold-start accuracy 0.5")
    raw = ROOT / "data/raw/skill_builder_data_corrected_collapsed.csv"
    split_path = ROOT / config["split"]["manifest"]
    if sha256(split_path) != config["split"]["manifest_sha256"]:
        raise ValueError("Split manifest differs from Configuration Lock A")
    manifest = json.loads(split_path.read_text(encoding="utf-8"))
    raw_hash = sha256(raw)
    if raw_hash != manifest["raw_sha256"] or raw_hash != config["split"]["raw_sha256"]:
        raise ValueError("Raw file changed since EDA; refusing to reuse the split")
    df = pd.read_csv(
        raw, encoding="cp1252", low_memory=False,
        dtype={k: "string" for k in ["user_id", "problem_id", "skill_id", "skill_name"]},
    )
    clean = clean_interactions(df)
    split = apply_split(clean, manifest)
    featured = add_problem_difficulty(add_history_features(split, warmup=warmup), n_splits=folds, alpha=alpha)
    # Whitelist: current hints/attempts/response text never enter model artifacts.
    columns = [
        "source_row", "user_id", "order_id", "problem_id", "skill_id", "correct", "split",
        "prior_skill_success", "prior_skill_failure", "prior_skill_count",
        "prior_skill_accuracy", "prior_overall_accuracy", "history_length", "scored",
        "problem_difficulty",
    ]
    featured = featured[columns]
    if featured.source_row.duplicated().any():
        raise ValueError("Source row identity is not unique")
    first_skill = featured.groupby(["user_id", "skill_id"], sort=False).head(1)
    assert first_skill.prior_skill_success.eq(0).all()
    assert first_skill.prior_skill_failure.eq(0).all()
    assert featured.scored.eq(featured.history_length.ge(warmup)).all()
    assert featured.problem_difficulty.between(0, 1).all()
    assert not featured.isna().any().any(), "Model artifact contains missing values"
    out = ROOT / "data/processed"
    out.mkdir(exist_ok=True, parents=True)
    summary = {
        "status": "data_prepared_not_trained", "raw_sha256": raw_hash,
        "split_manifest_sha256": sha256(split_path), "raw_rows": len(df),
        "clean_rows": len(featured), "warmup": warmup, "oof_folds": folds, "smoothing_alpha": alpha,
        "config_version": config["version"], "config_sha256": sha256(config_path),
        "label_dependent_test_statistics_reported": False, "partitions": {},
        "feature_columns": columns,
    }
    for name in ["train", "validation", "test"]:
        part = featured[featured.split.eq(name)].copy()
        file = out / f"{name}.parquet"
        part.to_parquet(file, index=False)
        # Read-back verifies the persisted artifact, including types and row identity.
        pd.testing.assert_frame_equal(pd.read_parquet(file), part.reset_index(drop=True))
        sizes = part.groupby("user_id").size()
        summary["partitions"][name] = {
            "rows": len(part), "students": part.user_id.nunique(),
            "scored_rows": int(part.scored.sum()), "students_without_scored_rows": int(sizes.le(warmup).sum()),
            "sha256": sha256(file),
        }
    target = ROOT / "artifacts/tables/preprocessing_summary.json"
    target.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    prepare()
