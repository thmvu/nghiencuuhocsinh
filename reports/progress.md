# Tiến độ — v4 hiện hành, v3 lịch sử

## FoundationalASSIST v4

- 04/10/2026, sau review: khôi phục Agent chọn độc lập làm hướng chính; B+ là baseline, agreement không phải gold label. Nhánh giải thích giữ lịch sử/phụ, 132/144 đúng yếu tố quyết định và 21/144 đạt hợp đồng dẫn chứng không phải điểm ngữ nghĩa. Thêm entrypoint mới bảo toàn các runner đã pin, journal lưu raw response trước truy vấn runtime sau call; regression endpoint lỗi, mismatch và transport error đạt. Chuẩn bị 144 study calls trên subset VALIDATION cũ (12 pilot + 12 challenge), chưa gọi model; operational metrics, paired graph sensitivity và rubric rationale riêng được viết trong `reports/rq2_selection_protocol_v2.md`. 181 tests PASS; hậu kiểm explanation replication chỉ đọc đạt, source/artifacts cũ giữ nguyên. Không retrain RQ1, không Lock C/TEST; manifest `artifacts/tables/foundationalassist_v4_rq2_selection_v2_preparation.json`.

- 03/10/2026, triển khai hướng B+ chọn/Agent giải thích, cập nhật thiết kế riêng; không nhận Agent chọn độc lập đã sửa thành công. 171 tests PASS. Lượt đầu đủ 144 calls nhưng Ollama đổi 0.34.4→0.35.1, giữ archive chưa xác nhận. Replication giữ request giống hệt, kiểm tra runtime từng call: 144/144 schema/ID đúng, 21/144 đạt toàn bộ gate giải thích; template 144/144, B+ giữ lựa chọn qua permutation. Audit source/raw response/trace/metric/runtime đạt. Raw draft chưa review ngữ nghĩa và không hiển thị; renderer chỉ dùng catalog đã kiểm tra. Chưa dùng Agent mặc định, Lock C/TEST đóng. Xem `reports/foundationalassist_v4_rq2_explanation.md`.

- 02/10/2026, thử calculator trên cùng subset VALIDATION: thêm bằng chứng tính sẵn cho từng ứng viên, giữ model/state/display/enum order; calculator B+ khớp B+ cũ 144/144 đầu vào. Qwen chạy 144/144 lượt hợp lệ, audit request/raw response/hash/metric/context đạt, 160 tests PASS. Agreement chỉ 1/36, 2/36, 1/36, 6/36 và variability 11–12/12: chưa sửa được thực hiện luật, không promote cấu hình hoặc Lock C. Không tiếp tục sweep, RQ1/TEST giữ nguyên. Xem `reports/foundationalassist_v4_rq2_agent_calculator.md`.

- 02/10/2026, sửa Agent: thêm schema enum/giới hạn reason, enum order độc lập, raw response và error stages vào private logs. Revision1 chạy 288 calls với hai arm schema-only/objective; thêm đúng một model trial Qwen2.5:1.5b với 144 request chỉ thay model. Tổng 432 calls mới hợp lệ; raw-response/request/hash/metric audit đạt và 152 tests PASS. Giảm first-position rate ở Qwen nhưng variability vẫn 83–100%, không promote model hoặc Lock C. 498 calls cũ giữ nguyên. Xem `reports/foundationalassist_v4_rq2_agent_repair.md`.

- 02/10/2026, Agent thật đã chạy: Ollama 0.34.4 / gemma3:1b, 300 pilot calls (287 hợp lệ) và 198 challenge calls (193 hợp lệ), không repair/retry. Context probe đạt ở cả hai cohort. Thiên lệch vị trí đầu mạnh: khoảng 83–98% trong lựa chọn hợp lệ; chưa có bằng chứng Agent hữu ích hơn B+. Hậu kiểm private calls/public metrics/pinned inputs/runtime đạt; hai cohort trùng 2 học sinh, không gộp estimates. Xem `reports/foundationalassist_v4_rq2_agent_validation.md`. RQ1 giữ nguyên, chưa Lock C/TEST RQ2. Các ghi chú Ollama bị chặn/chưa chạy dưới đây là trạng thái trước lượt này.

- 02/10/2026, cập nhật coverage: kiểm tra cả 750 VALIDATION học sinh ở prefix 5/10/20/50; lần lượt 3/5/13/33 có liên kết cùng yếu với cả hai skill đã quan sát. Generator ban đầu giữ tín hiệu ở 0/0/0/4. Thêm cohort thăm dò riêng tại prefix50, không thay pilot: 33 học sinh/97 surfaced IDs, B+ đổi lựa chọn có/không cạnh ở 29/33. Đây là kiểm tra phản ứng policy có điều kiện, không chứng minh graph hoặc lợi ích học tập. 145 tests PASS; Agent chưa chạy do Ollama chưa mở được. Xem `reports/foundationalassist_v4_rq2_coverage.md`. Chưa Lock C/TEST RQ2.

- 02/10/2026, sau review graph: thêm compact input/no-edge variant, B+ v4 xét cạnh trực tiếp tới weak target được trình bày (soft ranking, không AND), runner VALIDATION với hash/split/checkpoint v4 và baseline/permutation chung. 50 scenario/69 surfaced problem IDs; 1.025 TRAIN pairs sau support5. B+ graph/no-graph chưa khác vì graph signal không kích hoạt trên 50 scenario. 141 tests PASS. Context preflight bị URLError do Ollama chưa hoạt động; token runtime chưa đo, Agent chưa chạy. Chi tiết `reports/foundationalassist_v4_rq2_review_response.md`. Chưa Lock C/TEST RQ2.

- 02/10/2026: người dùng tiếp tục project giáo dục riêng; hướng đề tài giảng viên đề nghị là AI hỗ trợ quyết định doanh nghiệp. Đã tạo graph giả định có nguồn cho RQ2 v4: 15 chuẩn/18 skill ID, 9 cạnh chuẩn/13 cạnh skill; expert_validated=false, Astra critique chưa thực hiện. Script chỉ đọc TRAIN có hash khớp Lock B v4. 133 kiểm thử tích hợp đạt. Graph chưa được nối vào runner scenario v4; bước tiếp là scenarios VALIDATION và độ nhạy bỏ cạnh, chưa Lock C/TEST RQ2.

- Cleaning/split giữ nguyên: 1.611.613 interactions, 3.500/750/750 học sinh.
- Training Lock commit `35e5c17` trước fit. 119 tests đạt trước TRAIN/VALIDATION; 123 trước TEST, gồm kiểm thử leakage và final gate.
- PFA C=0,01; ba C lớn hơn không hội tụ trong budget. BKT 171 fit groups/513 starts, pooled fallback cho 23 skill. XGBoost depth4/eta0,1/300 trees chọn bằng VALIDATION.
- Final Lock `30f8c92` push trước marker TEST. One-shot TEST: 238.330 scored rows/750 học sinh. XGBoost Brier 0,178223, AUC 0,788408; xem `reports/foundationalassist_v4_rq1_test.md`.
- Hậu kiểm tái tính metrics và paired student bootstrap từ predictions đã lưu, không chạy model lại. RQ2 v4 có metadata-only TRAIN inventory 1.063 problem-skill pairs cho pilot 15 standard/18 skill ID; không chứa text và không lọc theo `rq2_text_eligible`. Graph/policy chưa khóa, không có lượt TEST RQ2 v4; content eligibility vẫn chờ human review. Bước review nội dung sẽ giới hạn vào các candidate ID duy nhất thực sự xuất hiện trong VALIDATION scenarios, không rà hết 2.233 bài auto-screen-pass. Reviewer hiện chưa được xác định; người đó nên review cả graph và candidate items surfaced.
- Khi so policy metadata-only, RQ2 chỉ kết luận về lựa chọn/xếp hạng vận hành (valid candidate, ràng buộc graph, agreement, latency/stability và position bias), không kết luận chất lượng sư phạm hoặc lợi ích học tập. Thiết kế VALIDATION bổ sung random-uniform-by-ID và always-first baselines dưới các candidate-order permutation có seed dùng chung giữa policy.

## Lịch sử ASSIST09 / plan v3

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
