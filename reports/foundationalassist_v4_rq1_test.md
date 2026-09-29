# RQ1 FoundationalASSIST v4 — final TEST

Một lượt TEST sau Training Lock `35e5c17` và Final Lock `30f8c92`, đều được commit/push trước giai đoạn tương ứng.
Các mô hình chỉ fit TRAIN; chọn cấu hình bằng VALIDATION; không refit TRAIN+VALIDATION.

| Model | Scored rows | Students | Brier ↓ | ROC-AUC ↑ | Log loss ↓ |
|---|---:|---:|---:|---:|---:|
| Global | 238330 | 750 | 0.235420 | 0.500000 | 0.663701 |
| Problem | 238330 | 750 | 0.209004 | 0.697131 | 0.605033 |
| PFA | 238330 | 750 | 0.210532 | 0.690395 | 0.609967 |
| BKT | 238330 | 750 | 0.210158 | 0.686573 | 0.609358 |
| XGBoost | 238330 | 750 | 0.178223 | 0.788408 | 0.531971 |

Reference được chọn trước TEST theo Brier VALIDATION: **XGBoost**.

| Model trừ reference | Chênh Brier | CI 95% |
|---|---:|---|
| Global | 0.057197 | [0.054313, 0.060054] |
| Problem | 0.030780 | [0.027950, 0.033744] |
| PFA | 0.032309 | [0.031044, 0.033586] |
| BKT | 0.031934 | [0.030678, 0.033163] |

Bootstrap ghép cặp 1.000 lần theo học sinh, seed42; chênh lệch là Brier interaction-weighted. Giá trị dương có lợi cho reference. Calibration dùng 10 bin cố định, không fit calibrator.

PFA C=0,01; C=0,1/1/10 không hội tụ trong budget. BKT: 171 fit groups, 513 optimizer runs; 23 skill ít support/one-class dùng pooled. XGBoost depth4, eta0,1, 300 cây.

Hậu kiểm đã tính lại metrics/CI từ predictions được lưu và đối chiếu hàng/mask giữa cả năm mô hình, không chạy model lần nữa.

Giới hạn: single-skill và filtered sequences; outcome là discrete_score, không phải mastery thật. Kết quả dự đoán này chưa chứng minh chất lượng recommendation hoặc learning gain. Không tune tiếp bằng TEST.

Bước sau: BKT latent state v4, graph có nguồn và rà soát rq2_text_eligible, rồi phát triển B+/Agent trên VALIDATION theo Lock C v4 riêng.
