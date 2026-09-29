# Protocol v4 — FoundationalASSIST

## 1. Phạm vi và trạng thái

FoundationalASSIST là dataset chính duy nhất. ASSIST09 chỉ là historical/reference/fallback; không thêm lượt train hay đánh giá trên ASSIST09. Các lock A/B/C, checkpoint, graph, split và kết quả cũ không áp dụng cho v4.

Snapshot tải: `82b29188dffd2fd6bd3abc5a3de0db1ef1df12b9`. SHA-256 ba CSV trong `configs/foundationalassist_v4_preprocessing.json`. Counts được tính từ snapshot thực tế, có thể khác README. Không bù/xóa dữ liệu để khớp README.

Trạng thái: RQ1 hoàn tất. Training Configuration và feature/code manifest đã commit `35e5c17` trước fit; Lock B v4 commit `30f8c92` trước one-shot TEST. Xem `reports/foundationalassist_v4_rq1_test.md`. RQ2 chưa phát triển/đánh giá; content review còn chờ. Không chạy lại final TEST hoặc điều chỉnh mô hình theo TEST.

## 2. RQ1

So sánh Global, Problem, PFA, BKT và XGBoost trong dự đoán `discrete_score[t]` trên cùng tập tương tác single-skill. Nhãn là kết quả theo định nghĩa ASSISTments về lần giải đầu độc lập; không đồng nhất với ground-truth mastery hoặc chỉ tính đúng sai của answer text.

Chuỗi chính được tạo sau filtering; tương tác bị loại không cập nhật BKT hoặc history counters. Multi-skill là limitation/future work. Đơn vị skill hiện tại là `skill_id`, không tự gộp các ID theo `node_code`.

## 3. Cleaning đã khóa

1. Đọc nguyên văn trường CSV, giữ chuỗi như `NA` và phân biệt ô trống.
2. Exact dedup theo `id` và `user_id, problem_id, end_time, discrete_score, answer_text, hint_count, saw_answer`. Giữ dòng có vị trí nguồn đầu tiên. `Unnamed: 0` không làm interaction identity.
3. Giữ các interaction khác ID dù cùng nội dung nghiệp vụ. Nếu cùng ID mà khác nghiệp vụ: dừng để kiểm tra, không tự chọn một phiên bản.
4. Loại label missing/không hợp lệ khỏi tập chính; giữ đúng nhãn số 0/1. Không nội suy.
5. Loại thời gian missing/không parse được khỏi sequential KT chính; parse UTC. Không dùng ID làm proxy thời gian.
6. Join bảng mapping đã loại cặp problem–skill trùng; loại bài không có mapping hợp lệ; giữ bài có đúng một `skill_id` duy nhất. Join `many_to_one`, không nhân dòng.
7. Sort theo học sinh và timestamp; nếu trùng timestamp hợp lệ trong cùng học sinh thì dừng. Tạo thứ tự theo chuỗi sau filtering.
8. Metadata Problems conflict không loại interaction RQ1 nếu KT fields hợp lệ; quarantine bài đó khỏi RQ2. Không chọn đại một đáp án trong các phiên bản conflict.

Raw không thay đổi. Artifact mô hình chỉ chứa source row, interaction ID, student ID, problem/skill ID, timestamp/order, target và split; dữ liệu cá nhân và artifact theo dòng chỉ lưu trong `data/` bị Git bỏ qua.

## 4. Split v4 đã khóa

Student-disjoint 70/15/15, seed 42. Sắp xếp ID học sinh hợp lệ, shuffle bằng NumPy `default_rng`, floor 70% TRAIN và 15% VALIDATION, phần còn lại TEST. Manifest mới ở `data/processed/foundationalassist_v4/student_split.json`; bắt buộc dùng lại, không chia lại theo kết quả.

TRAIN 3.500 học sinh / 1.127.951 tương tác; VALIDATION 750 / 241.582; TEST 750 / 242.080. Tổng 1.611.613 tương tác. Chỉ đếm cấu trúc của TEST ở bước chuẩn bị; không chọn feature, model, prompt hoặc policy theo TEST.

## 5. Lock RQ1 trước huấn luyện — đã hoàn tất

Cấu hình cụ thể trong `configs/foundationalassist_v4_rq1_training.json`; final checkpoint/input/code pins trong `configs/foundationalassist_v4_rq1_final.json`. 123 kiểm thử tích hợp đạt trước TEST, bao gồm perturbation current/future label, OOF exclusion, evaluator và one-shot synthetic test.

- Khóa trước grid, giới hạn fits/optimizer, điều kiện hội tụ, fallback skill chưa thấy, warm-up, metric chính và tie-break; không sao chép cấu hình thắng ASSIST09 như thể đã được chọn cho bộ mới.
- Tất cả mô hình fit TRAIN; chọn cấu hình trên VALIDATION; dùng cùng scored rows sau warm-up. Predict trước update; reset state khi đổi học sinh.
- Mọi history chỉ từ các tương tác đủ điều kiện trước thời điểm hiện tại. Cấm `answer_text[t]`, `hint_count[t]`, `saw_answer[t]`, `discrete_score[t]` làm predictor của nhãn hiện tại. Không đưa ID số hoặc timestamp kết thúc hiện tại vào predictor.
- Problem statistics chỉ fit TRAIN; TRAIN sử dụng OOF theo học sinh nếu dùng làm feature. Encoder/scaler chỉ fit TRAIN, có fallback đã khóa cho bài/kỹ năng chưa thấy.
- Brier làm metric chính đề xuất; AUC, log loss và calibration bổ sung. Trước TEST phải khóa metric, bootstrap theo học sinh, checkpoint/code/input hashes và quy tắc one-shot. Không dùng TEST để chọn mô hình.
- Cần script v4 dùng artifact v4; script train/evaluate ASSIST09 hiện có vẫn là lịch sử, không được chạy nhầm.

## 6. RQ2: BKT state + graph + bài thật

Hai policy B+ deterministic và Local Agent nhận cùng BKT latent state, cùng graph, cùng candidate set và cùng nội dung bài được phép. BKT checkpoint phải được fit trên TRAIN v4; không dùng checkpoint ASSIST09. Mô hình thắng RQ1 không bắt buộc là nguồn state.

Skills.csv là problem–skill mapping, không phải prerequisite graph. Xây graph riêng có nguồn curriculum hoặc giả định được ghi rõ. Graph, candidate rules và prompt phát triển bằng TRAIN/VALIDATION, khóa trước TEST RQ2 mới.

### Điều kiện `rq2_text_eligible`

Cờ chỉ bật khi đồng thời: metadata không conflict; body tồn tại; không phụ thuộc image/media/external asset; options và answer parse được đúng loại câu hỏi; math markup giữ đủ ý nghĩa; skill mapping phù hợp với thiết kế. MVP dùng single-skill cho state/policy tương thích.

Screen tự động chỉ đánh dấu `automatic_screen_pass`. Không có ảnh không chứng minh đủ nội dung. Tất cả bài hiện chờ rà soát; `rq2_text_eligible=False` cho tới khi có xác nhận nội dung kèm người rà soát/nguồn. Review kiểm tra cả phụ thuộc biểu đồ, nội dung phần trước và lựa chọn trả lời, không chỉ `<img>`.

Normalize bảo toàn HTML/LaTeX: Unicode NFC và newline thống nhất, giữ nguyên markup; không strip tags cho input Agent. Nếu hiển thị HTML cho người chấm, cần renderer bảo toàn toán và vô hiệu hóa mã/script cùng tài nguyên ngoài. Không đưa raw HTML không tin cậy vào trang chạy trực tiếp. Đáp án dùng kiểm tra parse nội bộ; không tự động đưa đáp án vào prompt recommendation.

Review packet cục bộ ở `data/processed/foundationalassist_v4/rq2_content_review.json` lưu đủ phiên bản conflict, lý do screen và các ô review; không đưa lên Git. Việc review bài không cần xem kết quả TEST.

## 7. Đánh giá và giới hạn

RQ2 là exploratory recommendation study, đo vận hành và chất lượng dưới rubric nếu có người chấm. Quy trình human evaluation/prompt/model/rubric của ASSIST09 không tự động trở thành Lock C v4. Cần thiết kế và khóa riêng trước TEST v4. Không tuyên bố learning gain hoặc causal benefit nếu chưa có thử nghiệm học tập phù hợp.

Giới hạn phải báo: single-skill filtering, filtered sequences không cập nhật những tương tác bị loại, missing label/time, định nghĩa outcome, BKT latent estimates, graph provenance, text-only selection bias và các bài không đủ nội dung.

## 8. Checklist tiến độ

- [x] Xác minh snapshot và SHA-256.
- [x] Audit duplicate, missing, chronology và metadata conflict.
- [x] Khóa cleaning và báo số interaction mất theo từng filter.
- [x] Tạo và lưu split học sinh mới.
- [x] Tạo screen nội dung bảo toàn markup, fail-closed cho RQ2.
- [ ] Hoàn thành rà soát nội dung để bật eligibility cho problem bank RQ2.
- [x] Khóa features/models/evaluation và kiểm thử đường chạy RQ1 v4.
- [x] Train/VALIDATION RQ1; Lock B v4; one-shot TEST.
- [ ] Graph, B+, Agent development; Lock C v4; one-shot TEST RQ2.

Không cần chờ toàn bộ RQ2 xong mới train RQ1; Gate RQ1 chỉ phụ thuộc protocol và kiểm thử RQ1.
