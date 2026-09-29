"""Report already saved final TEST predictions; never calls a fitted model."""
from pathlib import Path
import hashlib
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.metrics import evaluate_predictions
from src.evaluation.bootstrap import paired_student_brier_bootstrap


def main():
    summary = json.loads((ROOT / 'artifacts/tables/foundationalassist_v4_rq1_test.json').read_text())
    lock_path = ROOT / 'configs/foundationalassist_v4_rq1_final.json'
    if hashlib.sha256(lock_path.read_bytes()).hexdigest() != summary['lock_sha256']:
        raise ValueError('Final lock changed')
    names = ['Global', 'Problem', 'PFA', 'BKT', 'XGBoost']
    joined = None
    fig, ax = plt.subplots(figsize=(7, 6))
    lines = ['# RQ1 FoundationalASSIST v4 — final TEST', '',
             'Một lượt TEST sau Training Lock `35e5c17` và Final Lock `30f8c92`, đều được commit/push trước giai đoạn tương ứng.',
             'Các mô hình chỉ fit TRAIN; chọn cấu hình bằng VALIDATION; không refit TRAIN+VALIDATION.', '',
             '| Model | Scored rows | Students | Brier ↓ | ROC-AUC ↑ | Log loss ↓ |',
             '|---|---:|---:|---:|---:|---:|']
    for name in names:
        pred = pd.read_parquet(ROOT / f'data/processed/foundationalassist_v4/final_test/{name}.parquet').sort_values('source_row').reset_index(drop=True)
        metrics = evaluate_predictions(pred)
        expected = summary['metrics'][name]
        for key, value in metrics.items():
            if value is None:
                assert expected[key] is None
            else:
                np.testing.assert_allclose(value, expected[key], rtol=0, atol=1e-12)
        columns = ['source_row', 'user_id', 'correct', 'is_scored']
        if joined is None:
            joined = pred[columns].copy()
        else:
            pd.testing.assert_frame_equal(joined[columns], pred[columns])
        joined[name] = pred.probability
        r = metrics
        lines.append(f"| {name} | {r['n_rows']} | {r['n_students']} | {r['brier_score']:.6f} | {r['roc_auc']:.6f} | {r['log_loss']:.6f} |")
        points = pd.DataFrame(summary['calibration'][name])
        ax.plot(points.mean_prediction, points.observed, marker='o', label=name)
    reference = summary['reference_chosen_on_validation']
    lines += ['', f'Reference được chọn trước TEST theo Brier VALIDATION: **{reference}**.', '',
              '| Model trừ reference | Chênh Brier | CI 95% |', '|---|---:|---|']
    config = json.loads((ROOT / 'configs/foundationalassist_v4_rq1_training.json').read_text())
    for name, expected in summary['paired_student_brier_bootstrap'].items():
        actual = paired_student_brier_bootstrap(joined, name, reference,
                 iterations=config['bootstrap']['iterations'], seed=config['bootstrap']['seed'])
        for key, value in actual.items():
            np.testing.assert_allclose(value, expected[key], rtol=0, atol=1e-12)
        lines.append(f"| {name} | {actual['difference']:.6f} | [{actual['ci_low']:.6f}, {actual['ci_high']:.6f}] |")
    ax.plot([0, 1], [0, 1], '--', color='gray')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Mean predicted probability',
           ylabel='Observed success rate', title='FoundationalASSIST — TEST calibration (10 fixed bins)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT / 'artifacts/plots/foundationalassist_v4_test_calibration.png', dpi=160)
    plt.close(fig)
    lines += ['', 'Bootstrap ghép cặp 1.000 lần theo học sinh, seed42; chênh lệch là Brier interaction-weighted. Giá trị dương có lợi cho reference. Calibration dùng 10 bin cố định, không fit calibrator.',
              '', 'PFA C=0,01; C=0,1/1/10 không hội tụ trong budget. BKT: 171 fit groups, 513 optimizer runs; 23 skill ít support/one-class dùng pooled. XGBoost depth4, eta0,1, 300 cây.',
              '', 'Hậu kiểm đã tính lại metrics/CI từ predictions được lưu và đối chiếu hàng/mask giữa cả năm mô hình, không chạy model lần nữa.',
              '', 'Giới hạn: single-skill và filtered sequences; outcome là discrete_score, không phải mastery thật. Kết quả dự đoán này chưa chứng minh chất lượng recommendation hoặc learning gain. Không tune tiếp bằng TEST.',
              '', 'Bước sau: BKT latent state v4, graph có nguồn và rà soát rq2_text_eligible, rồi phát triển B+/Agent trên VALIDATION theo Lock C v4 riêng.']
    (ROOT / 'reports/foundationalassist_v4_rq1_test.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Saved final report and calibration; persisted predictions/metrics/bootstrap verified.')


if __name__ == '__main__':
    main()
