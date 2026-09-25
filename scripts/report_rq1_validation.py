"""Summarize development-only RQ1 models and calibration curves."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "artifacts/tables"
PREDICTIONS = ROOT / "data/processed/predictions"


def load(name):
    return json.loads((TABLES / name).read_text(encoding="utf-8"))


def main():
    base = load("baselines_pfa_validation.json")
    bkt = load("bkt_validation.json")
    xgb = load("xgboost_validation.json")
    if any(x.get("test_opened") is not False for x in (base, bkt, xgb)):
        raise ValueError("Only development results belong in this report")
    rows = [*base["results"], {"model": "BKT", **bkt["metrics"]}, *xgb["results"]]
    expected_count = {(row["n_rows"], row["n_students"]) for row in rows}
    if expected_count != {(32382, 481)}:
        raise ValueError(f"Scoring populations differ: {expected_count}")
    table = pd.DataFrame(rows)[["model", "n_rows", "n_students", "brier_score", "roc_auc", "log_loss"]]
    table.to_csv(TABLES / "rq1_validation_comparison.csv", index=False)
    paths = {
        "Global": PREDICTIONS / "validation_Global.parquet",
        "Problem": PREDICTIONS / "validation_Problem.parquet",
        "PFA": PREDICTIONS / f"validation_PFA_C_{base['pfa_selected_C']}.parquet",
        "BKT": PREDICTIONS / "validation_BKT.parquet",
        "XGBoost": PREDICTIONS / "validation_XGBoost_selected.parquet",
    }
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.plot([0, 1], [0, 1], "--", color="#777777", label="Perfect calibration")
    bins = np.linspace(0, 1, 11)
    calibration_rows = []
    common = None
    for name, path in paths.items():
        frame = pd.read_parquet(path)
        scored = frame.loc[frame.is_scored].copy()
        identities = set(scored.source_row)
        if common is None:
            common = identities
        elif common != identities:
            raise ValueError(f"{name} has different scored row identities")
        if not scored.probability.between(0, 1).all():
            raise ValueError(f"Invalid {name} probability")
        scored["bin"] = np.minimum(np.searchsorted(bins, scored.probability.to_numpy(), side="right") - 1, 9)
        grouped = scored.groupby("bin").agg(count=("correct", "size"),
                                            mean_prediction=("probability", "mean"),
                                            observed_rate=("correct", "mean"))
        for index, item in grouped.iterrows():
            calibration_rows.append({"model": name, "bin": int(index), **item.to_dict()})
        ax.plot(grouped.mean_prediction, grouped.observed_rate, marker="o", label=name)
    ax.set(xlabel="Mean predicted probability", ylabel="Observed success rate",
           title="RQ1 validation calibration (10 fixed-width bins)", xlim=(0, 1), ylim=(0, 1))
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(ROOT / "artifacts/plots/rq1_validation_calibration.png", dpi=180)
    plt.close(fig)
    pd.DataFrame(calibration_rows).to_csv(TABLES / "rq1_validation_calibration_bins.csv", index=False)
    report = [
        "# RQ1 — so sánh trên validation", "",
        "Các kết quả dưới đây dùng cùng 32.382 tương tác đã qua warm-up của 481 sinh viên validation. Đây là số liệu phát triển để chọn cấu hình; chưa phải kết quả TEST cuối.", "",
        "| Mô hình | Brier ↓ | ROC-AUC ↑ | Log Loss ↓ |", "|---|---:|---:|---:|",
    ]
    for row in rows:
        report.append(f"| {row['model']} | {row['brier_score']:.4f} | {row['roc_auc']:.4f} | {row['log_loss']:.4f} |")
    report += [
        "", f"PFA: C={base['pfa_selected_C']}; C=1 và C=10 không hội tụ trong ngân sách đã khóa. "
        f"XGBoost: {xgb['xgboost_selected']}. BKT: {bkt['fit_diagnostics']['fit_groups']} fit groups, "
        f"{bkt['fit_diagnostics']['optimizer_runs']} optimizer runs, pooled fit hội tụ.", "",
        "XGBoost có Brier validation thấp nhất trong các cấu hình đã xét. Đường calibration 10 bin được lưu ở `artifacts/plots/rq1_validation_calibration.png`; đây là đánh giá trực quan, không fit calibrator.", "",
        "TEST vẫn cần Gate B. Trước Gate B cần ghi Lock B cho tất cả mô hình, protocol bootstrap theo sinh viên, xác minh checkpoint/code hash và rà soát checklist. Chưa thể kết luận mô hình tốt nhất trên population ngoài mẫu từ validation.", "",
    ]
    (ROOT / "reports/rq1_validation.md").write_text("\n".join(report), encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
