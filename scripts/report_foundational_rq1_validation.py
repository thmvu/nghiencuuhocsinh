"""Combine completed v4 VALIDATION runs and plot calibration; no TEST access."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config_hash = digest(ROOT / 'configs/foundationalassist_v4_rq1_training.json')
    rows, reports = [], {}
    for group in ('baselines_pfa', 'bkt', 'xgboost'):
        report = json.loads((ROOT / f'artifacts/tables/foundationalassist_v4_{group}_validation.json').read_text())
        if report['status'] != 'completed' or report['config_sha256'] != config_hash:
            raise ValueError('Incomplete group or changed training lock')
        reports[group] = report
        rows.extend(report['results'])
    if {r['model'] for r in rows} != {'Global', 'Problem', 'PFA', 'BKT', 'XGBoost'}:
        raise ValueError('Five models required')
    base = ROOT / 'data/processed/foundationalassist_v4/predictions'
    reference_frame = None
    fig, ax = plt.subplots(figsize=(7, 6))
    bins = np.linspace(0, 1, 11)
    for row in rows:
        name = row['model']
        frame = pd.read_parquet(base / f'validation_{name}.parquet').sort_values('source_row').reset_index(drop=True)
        identity = frame[['source_row', 'user_id', 'correct', 'is_scored']]
        if reference_frame is None:
            reference_frame = identity
        else:
            pd.testing.assert_frame_equal(reference_frame, identity)
        scored = frame.loc[frame.is_scored]
        bucket = np.minimum(np.searchsorted(bins, scored.probability, side='right') - 1, 9)
        points = scored.assign(bucket=bucket).groupby('bucket').agg(
            predicted=('probability', 'mean'), observed=('correct', 'mean'))
        ax.plot(points.predicted, points.observed, marker='o', label=name)
    ax.plot([0, 1], [0, 1], '--', color='gray')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Mean predicted probability',
           ylabel='Observed success rate', title='FoundationalASSIST — VALIDATION calibration (10 fixed bins)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / 'artifacts/plots/foundationalassist_v4_validation_calibration.png', dpi=160)
    plt.close(fig)
    best = min(rows, key=lambda r: r['brier_score'])['model']
    lines = ['# RQ1 FoundationalASSIST v4 — TRAIN/VALIDATION', '',
             '**Chưa đánh giá TEST.** Training Lock đã commit trước fit; selection chỉ dùng VALIDATION.', '',
             '| Model | Scored rows | Students | Brier ↓ | ROC-AUC ↑ | Log loss ↓ |',
             '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['model']} | {r['n_rows']} | {r['n_students']} | {r['brier_score']:.6f} | {r['roc_auc']:.6f} | {r['log_loss']:.6f} |")
    lines += ['', f'Brier VALIDATION thấp nhất: **{best}**. Đây là kết quả phát triển, chưa phải kết luận TEST.',
              '', 'PFA selected: ' + json.dumps(reports['baselines_pfa']['selected_parameters']) + '.',
              'XGBoost selected: ' + json.dumps(reports['xgboost']['selected_parameters']) + '.',
              'BKT dùng một recipe đã khóa; chọn optimizer start theo TRAIN likelihood, không mở search bằng VALIDATION.',
              '', 'Các mô hình dùng cùng source rows/labels và warm-up mask đã đối chiếu trực tiếp từ predictions riêng.',
              'Calibration dùng 10 bin độ rộng cố định, không fit calibrator; plot ở `artifacts/plots/foundationalassist_v4_validation_calibration.png`.',
              '', 'Bước tiếp theo: khóa checkpoint và one-shot evaluator trong Lock B v4 trước khi mở TEST.']
    invalid = [r for r in reports['baselines_pfa']['candidates'] if r['status'] != 'valid']
    if invalid:
        lines += ['', 'PFA candidates không hợp lệ do không hội tụ trong budget: ' +
                  ', '.join(str(r['parameters']) for r in invalid) + '. Không tăng budget sau khi xem kết quả.']
    (ROOT / 'reports/foundationalassist_v4_rq1_validation.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Saved reports/foundationalassist_v4_rq1_validation.md; selected reference:', best)


if __name__ == '__main__':
    main()
