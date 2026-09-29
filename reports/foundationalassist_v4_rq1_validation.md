# RQ1 FoundationalASSIST v4 — TRAIN/VALIDATION

**Chưa đánh giá TEST.** Training Lock đã commit trước fit; selection chỉ dùng VALIDATION.

| Model | Scored rows | Students | Brier ↓ | ROC-AUC ↑ | Log loss ↓ |
|---|---:|---:|---:|---:|---:|
| Global | 237832 | 750 | 0.236013 | 0.500000 | 0.664908 |
| Problem | 237832 | 750 | 0.208951 | 0.699264 | 0.604885 |
| PFA | 237832 | 750 | 0.212648 | 0.684572 | 0.614802 |
| BKT | 237832 | 750 | 0.212654 | 0.679572 | 0.614888 |
| XGBoost | 237832 | 750 | 0.180681 | 0.782683 | 0.538378 |

Brier VALIDATION thấp nhất: **XGBoost**. Đây là kết quả phát triển, chưa phải kết luận TEST.

PFA selected: {"C": 0.01}.
XGBoost selected: {"max_depth": 4, "learning_rate": 0.1, "n_estimators": 300}.
BKT dùng một recipe đã khóa; chọn optimizer start theo TRAIN likelihood, không mở search bằng VALIDATION.

Các mô hình dùng cùng source rows/labels và warm-up mask đã đối chiếu trực tiếp từ predictions riêng.
Calibration dùng 10 bin độ rộng cố định, không fit calibrator; plot ở `artifacts/plots/foundationalassist_v4_validation_calibration.png`.

Bước tiếp theo: khóa checkpoint và one-shot evaluator trong Lock B v4 trước khi mở TEST.

PFA candidates không hợp lệ do không hội tụ trong budget: {'C': 0.1}, {'C': 1.0}, {'C': 10.0}. Không tăng budget sau khi xem kết quả.
