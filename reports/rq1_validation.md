# RQ1 — so sánh trên validation

Các kết quả dưới đây dùng cùng 32.382 tương tác đã qua warm-up của 481 sinh viên validation. Đây là số liệu phát triển để chọn cấu hình; chưa phải kết quả TEST cuối.

| Mô hình | Brier ↓ | ROC-AUC ↑ | Log Loss ↓ |
|---|---:|---:|---:|
| Global | 0.2223 | 0.5000 | 0.6366 |
| Problem | 0.2030 | 0.6781 | 0.5923 |
| PFA | 0.1975 | 0.7003 | 0.5824 |
| BKT | 0.1925 | 0.7116 | 0.5690 |
| XGBoost | 0.1738 | 0.7767 | 0.5208 |

PFA: C=0.1; C=1 và C=10 không hội tụ trong ngân sách đã khóa. XGBoost: {'max_depth': 4, 'learning_rate': 0.1, 'n_estimators': 300}. BKT: 84 fit groups, 252 optimizer runs, pooled fit hội tụ.

XGBoost có Brier validation thấp nhất trong các cấu hình đã xét. Đường calibration 10 bin được lưu ở `artifacts/plots/rq1_validation_calibration.png`; đây là đánh giá trực quan, không fit calibrator.

TEST vẫn cần Gate B. Trước Gate B cần ghi Lock B cho tất cả mô hình, protocol bootstrap theo sinh viên, xác minh checkpoint/code hash và rà soát checklist. Chưa thể kết luận mô hình tốt nhất trên population ngoài mẫu từ validation.
