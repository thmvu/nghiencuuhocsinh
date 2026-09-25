# Tiến độ — plan v3

Phạm vi khởi động: môi trường local, bảo toàn CSV, notebook EDA chạy được và báo cáo dữ liệu thật.

- Plan: NCKH_Knowledge_Tracing_AI_Agent_Plan_v3_Consolidated.md.
- Ruling: thư mục chưa có Git; làm trực tiếp trong workspace người dùng chỉ định, không tạo worktree.
- Ruling: dùng Python 3.10.11 hiện có cho giai đoạn EDA; v3 không khóa Python version. Kiểm tra tương thích BKT riêng trước Gate A.
- Ruling: giữ nguyên CSV gốc ở thư mục chính, sao chép có kiểm tra SHA-256 vào data/raw.
- CSV người dùng cung cấp; chưa xác minh byte-for-byte với bản tải chính thức.
- Chưa train; Gate A/B/C chưa hoàn thành.

- Ruling: CSV không phải UTF-8; CP1252 strict decode/encode roundtrip thành công. Dùng CP1252 cho EDA, ghi rõ đây là suy luận encoding.

- EDA complete: notebook executed end-to-end; all code cells ran, no error outputs; nbformat validation passed.
- pip check passed; requirements-lock.txt saved.
- Independent review: no blocking leakage issue; added retention counts and dependency snapshot.
- Pending: preprocessing/features/tests + Lock A; Ollama smoke test; RQ1/RQ2 not complete.

## Gate A — parallel implementation

- Branch: feat/gate-a-preprocessing.
- Team: data_pipeline (preprocessing), protocol_evaluation (protocol/sequential evaluator), independent_tests (adversarial tests), root (integration/report).
- Shared interface: clean_interactions → apply_split(existing manifest) → add_history_features(warmup=5) → add_problem_difficulty(grouped OOF).
- Ruling: continue in the user-selected workspace on a feature branch; agents own separate files, no concurrent git operations.
- Ruling: initial milestone is Gate A only; no training or test model metrics until gates are satisfied.
- Verification pending: unit suite, independent leakage tests, real-data pipeline and notebook execution.

- Gate A complete: 21 tests PASS, preprocessing notebook executed, parquet read-back equality verified.
- Independent agent authored 8 adversarial tests; usage interruption prevented final independent review. Root executed/reviewed integrated suite.
- Fix RED→GREEN: reject unknown skill encoding and missing/duplicate source identity.
- Ruling: BKT future fitter uses bounded SciPy likelihood rather than pyBKT; cost is additional hand-derived sequence verification before fit.
- Gate B/C pending; no models trained, no heldout model metrics inspected. See reports/gate_a_report.md.

## Global/Problem baseline + PFA

- User preference: all new commit messages in Vietnamese without diacritics.
- Two model implementation agents + one independent tester; root owns experiment runner, integration and report.
- Train/validation only, four predeclared PFA C candidates; no test scoring or expanded search.

- Global/Problem/PFA train and validation complete on 32,382 scored rows/481 students; PFA selected C=0.1 by Brier. C=1,10 invalid nonconvergence within locked budget. No TEST scoring.
- Independent review found and verified fixes for Problem model serialization and parameter snapshot mutation. See reports/models_review.md.

## RQ1 hoàn tất và RQ2 validation development

- RQ1 Lock B hoàn tất; đánh giá TEST cuối trên cùng 29.751 lượt tương tác của 483 sinh viên. XGBoost có Brier 0,17347, thấp nhất trong năm mô hình đã khóa. Chi tiết và bootstrap theo sinh viên ở `reports/rq1_test_results.md`.
- RQ2 đã có BKT latent-mastery snapshots, graph prototype 20 kỹ năng/5 cạnh giả định, TRAIN-only candidate pool, B+ deterministic policy và Agent contract cho Ollama.
- 50 validation scenarios từ 50 sinh viên riêng; Agent `gemma3:1b` đạt 49/50 output đúng schema, 48/50 candidate hợp lệ trong một lượt phát triển. Đây chưa phải kết quả TEST RQ2; xem `reports/rq2_validation_progress.md`.
- Reviewer độc lập xác nhận sửa lỗi trùng mã kỹ năng, chặn dữ liệu held-out vào graph/pool và kiểm tra lại B+ từ shared inputs. Lock C, rubric và RQ2 TEST còn chờ.

## Lock C và TEST RQ2

- Lock C commit `18b3091` đã push trước khi mở TEST RQ2. 24 hash, runtime/model và 100 kiểm thử được kiểm tra; Gate C đạt.
- Một lượt TEST: 50 sinh viên, 3 lần Agent/scenario, 147/150 output qua xác thực candidate (98%; CI bootstrap theo sinh viên 94–100%), 49/50 sinh viên có cùng một lựa chọn hợp lệ qua cả ba lần. Không timeout. Xem `reports/rq2_test_results.md`.
- Kiểm toán độc lập xác nhận Lock C trước dấu mốc TEST, các chỉ số tính lại khớp nhật ký riêng và không có sửa mã sau khóa. Không có người chấm mù hoặc học liệu xác nhận graph, nên chưa có kết luận Agent khuyến nghị tốt hơn B+ hay cải thiện learning gain.
