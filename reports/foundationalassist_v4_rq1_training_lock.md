# RQ1 Training Configuration — FoundationalASSIST v4

Configuration: `configs/foundationalassist_v4_rq1_training.json`. Cleaning/split giữ cố định trong lock preprocessing; không đọc TEST trong development. Đây là khóa thiết kế TRAIN/VALIDATION; final TEST cần Lock B v4 riêng với checkpoint đã chọn.

| Thành phần | Cấu hình khóa trước development |
|---|---|
| History | Prior skill success/failure/accuracy, prior overall accuracy, history length; chỉ các interaction đủ điều kiện trước t; cold-start accuracy 0,5 |
| Difficulty feature | Proxy tỷ lệ đúng (cao nghĩa là dễ hơn), GroupKFold 5 fold theo học sinh TRAIN, alpha=10; fallback mean của fit fold; VALIDATION dùng full TRAIN |
| Encoding | Skill one-hot fit TRAIN, unknown all-zero; không dùng problem one-hot hoặc numeric IDs; Problem baseline dùng mapping mean theo problem |
| Mask | Warm-up 5 interaction mỗi học sinh; t có history_length >=5 mới được score; vẫn predict/update các dòng warm-up |
| Global / Problem | TRAIN mean / TRAIN smoothed problem mean alpha=10; bài chưa thấy dùng TRAIN mean |
| PFA | Skill-specific intercept và hệ số success/failure, thêm global intercept; L2/lbfgs, C=[0.01,0.1,1,10], max_iter=2000, tol=1e-6; không hội tụ thì candidate invalid |
| BKT | Không forgetting; pooled + per-skill có >=100 TRAIN interactions và cả 2 labels; skill thiếu support/chưa thấy dùng pooled; student-skill state riêng |
| BKT fitting | TRAIN sequence likelihood, L-BFGS-B; 3 starts đã liệt kê trong config; bounds L0=[.001,.999], T=[.001,.5], G/S=[.001,.3]; maxiter=500, maxfun=10000, ftol=1e-9 |
| BKT budget | Tối đa 225 fit groups và 675 optimizer runs (224 metadata skills + pooled); 1 recipe, không search theo VALIDATION |
| XGBoost | 6 numeric features nêu trên + skill one-hot; depth=[2,4], eta=[.05,.1], trees=[100,300]; 8 fits theo thứ tự config; hist/1 thread/seed42, không early stopping |
| Selection | VALIDATION Brier thấp nhất, exact tie lấy candidate đầu; không mở rộng budget khi thất bại; không refit TRAIN+VALIDATION |
| Metrics | Primary Brier; ROC-AUC, log loss; calibration 10 equal-width bins, không fit calibrator; không tune alpha |
| Final CI | Paired bootstrap 1.000 lần theo học sinh, seed42, chênh Brier interaction-weighted, CI percentile 2.5–97.5%; reference chọn bằng VALIDATION |

XGBoost numeric features chính xác: prior_skill_success, prior_skill_failure, prior_skill_accuracy, prior_overall_accuracy, history_length, problem_difficulty. Không dùng answer_text[t], hint_count[t], saw_answer[t], outcome hiện tại hoặc thời gian kết thúc hiện tại làm predictor. Các identity columns chỉ dùng group/order/join, không dùng làm giá trị số cho mô hình.

Evaluator dùng predict(t) → observe y[t] → update → t+1; tham số toàn cục bất biến, state reset khi đổi học sinh. Batch prediction cho mô hình stateless phải khớp sequential adapter trên cùng feature rows/mask. VALIDATION và TEST dùng cùng evaluator và quy tắc history/difficulty; chỉ được tạo TEST features ở giai đoạn cuối đã khóa.

Kiểm thử gate riêng phải xác nhận history không nhìn current/future labels, student isolation, OOF không dùng label của held student, VALIDATION labels không thay đổi difficulty, thứ tự callbacks và đồng nhất mask. Bộ preprocessing tests trước đây không thay thế các kiểm thử này.

Runbook: chạy bộ tests tích hợp → `scripts/prepare_foundational_rq1_features.py` → pin manifest/code/config và commit lock → `scripts/train_foundational_rq1.py --group baselines_pfa`, `--group bkt`, `--group xgboost`. Outputs theo dòng và checkpoints chỉ lưu cục bộ. Bảng public chỉ chứa aggregates/diagnostics không ID học sinh.
