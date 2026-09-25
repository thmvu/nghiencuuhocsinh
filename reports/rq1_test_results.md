# RQ1 — final TEST results

All five frozen train-fitted models were evaluated on the same post-warm-up TEST rows.

| Model | Rows | Students | Brier ↓ | ROC-AUC ↑ | Log Loss ↓ |
|---|---:|---:|---:|---:|---:|
| Global | 29751 | 483 | 0.2217 | 0.5000 | 0.6355 |
| Problem | 29751 | 483 | 0.2014 | 0.6819 | 0.5888 |
| PFA | 29751 | 483 | 0.1959 | 0.7029 | 0.5795 |
| BKT | 29751 | 483 | 0.1923 | 0.7065 | 0.5691 |
| XGBoost | 29751 | 483 | 0.1735 | 0.7725 | 0.5204 |

Paired student bootstrap compares interaction-weighted Brier differences (model minus XGBoost); positive values favor XGBoost.

| Model | Difference | 95% CI |
|---|---:|---:|
| Global | 0.0483 | [0.0427, 0.0549] |
| Problem | 0.0279 | [0.0224, 0.0347] |
| PFA | 0.0224 | [0.0197, 0.0252] |
| BKT | 0.0188 | [0.0167, 0.0210] |

Calibration uses 10 fixed-width probability bins and no fitted calibrator. See `artifacts/plots/rq1_test_calibration.png`.
