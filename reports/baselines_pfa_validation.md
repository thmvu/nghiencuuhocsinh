# Global / Problem / PFA — validation development

Các số dưới đây chỉ từ VALIDATION sau 5 tương tác warm-up. TEST chưa dùng để chọn mô hình. Cả ba được chấm trên 32.382 tương tác của 481 sinh viên.

| Model | Brier ↓ | AUC ↑ | Log Loss ↓ |
|---|---:|---:|---:|
| Global | 0.2223 | 0.5000 | 0.6366 |
| Problem | 0.2030 | 0.6781 | 0.5923 |
| PFA | 0.1975 | 0.7003 | 0.5824 |

PFA chọn C=0.1 theo Brier validation. C=1 và C=10 không hội tụ trong ngân sách 2.000 vòng đã khóa; không tăng ngân sách sau khi xem kết quả. Đây là kết quả phát triển, chưa phải bảng cuối RQ1.

Nguồn tái lập: `configs/protocol_a.json`, `scripts/train_baselines_pfa.py`, `artifacts/tables/baselines_pfa_validation.json`. Checkpoint và dự đoán từng dòng nằm cục bộ, không commit.

Đánh giá tiếp theo: BKT, XGBoost trên cùng mask; sau đó khóa B rồi mới chấm TEST. Cần calibration curve và paired bootstrap theo sinh viên trước khi hoàn thành RQ1.
