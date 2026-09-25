# Configuration Lock B — RQ1 final evaluation

Date: 2026-09-25. Machine-readable authority: `configs/protocol_b.json` (SHA-256 `0a5800e6a2c1688cd50df028aec2970a4645ac5f10c44914e02ea70b73f04c4d`). This lock precedes the final TEST model evaluation. It freezes the choices below; TEST outcomes cannot change them.

## Locked choices

| Item | Final choice |
|---|---|
| Input and split | Reuse the student-disjoint split manifest and TRAIN/VALIDATION/TEST parquet files named and hashed in `protocol_b.json`. No regeneration. TEST file hash was checked without opening labels or scoring predictions. |
| Shared scoring | Warm-up five cleaned interactions per student. Score only the common post-warm-up row identities; reset student state and predict before updating it with the current response. Use interaction-weighted Brier as the primary metric, plus ROC-AUC, log loss and a ten-bin calibration curve. |
| Global and Problem | Retain the existing TRAIN-fitted checkpoints. Problem smoothing alpha 10, fixed in Lock A. |
| PFA | Retain TRAIN-fitted checkpoint with `C=0.1`, the minimum valid validation Brier candidate. `C=1` and `C=10` did not converge inside the locked budget and were invalid. |
| BKT | Retain the TRAIN-fitted checkpoint containing the pooled and per-skill parameters. Pooled fit converged; 84 fit groups and 252 optimizer runs remained within Lock A limits. The checkpoint SHA-256 and fitting source are pinned in `protocol_b.json`. |
| XGBoost | Retain TRAIN-fitted checkpoint with depth 4, learning rate 0.1 and 300 trees. It had the minimum Brier in the eight-candidate validation grid. No extra fit or train-plus-validation refit. |
| Calibration | No fitted calibrator. Calibration curve is descriptive only. |
| Uncertainty | Paired percentile bootstrap over students: 1,000 iterations, seed 42, 2.5% and 97.5% quantiles. Sample student clusters with replacement, retaining all their scored interactions; compute interaction-weighted Brier differences as `model minus XGBoost` on paired rows. |

## Pre-TEST evidence and checklist

All five models were evaluated on the same 32,382 scored validation interactions from 481 students. Their validation Brier scores were Global 0.222258, Problem 0.202996, PFA 0.197534, BKT 0.192527 and XGBoost 0.173848. These select configurations; they are not final TEST estimates. Sources: `artifacts/tables/baselines_pfa_validation.json`, `bkt_validation.json`, and `xgboost_validation.json`.

- [x] EDA and Gate A preprocessing completed; cleaning, student split, evaluation mask, five-fold student GroupKFold problem-difficulty cross-fitting, and target definition were locked in `configs/protocol_a.json`.
- [x] PFA form, BKT fitting strategy, XGBoost features and encoding, tuning budgets, primary metric and calibration protocol were locked before model fitting.
- [x] All five TRAIN-fitted checkpoints exist. The split manifest, three parquet files, five checkpoints, three validation artifacts and recorded model/evaluation source files match their SHA-256 hashes. Only the TEST file bytes were hashed; its labels and model outcomes were not inspected for this lock.
- [x] Validation selected PFA `C=0.1` and XGBoost depth 4 / learning rate 0.1 / 300 trees; BKT pooled fitting converged. No calibrator was fitted and final fitting policy remains no refit.
- [x] Paired student bootstrap protocol was frozen before TEST. The full integrated test suite passed: 67 tests, including two bootstrap tests, with no failures (2026-09-25).
- [x] Validation result artifacts identify their stage as development and `test_opened=false`; train/validation/config and source hashes matched the current files. No TEST label-based tuning or scoring has occurred in this lock step.

Gate B condition: **RQ1 DEVELOPMENT COMPLETE + CONFIGURATION LOCK B COMPLETE + RQ1 PRE-TEST CHECKLIST PASS**. The final evaluator must reject any mismatch in locked hashes or choices before opening TEST labels. Run it once and report the unchanged model ranking, uncertainty and calibration results regardless of outcome. RQ2 has its own later Lock C and Gate C.
