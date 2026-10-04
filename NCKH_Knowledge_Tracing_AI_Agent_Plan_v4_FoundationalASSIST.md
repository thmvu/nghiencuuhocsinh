# Protocol v4 — FoundationalASSIST

## 1. Phạm vi và trạng thái

FoundationalASSIST là dataset chính duy nhất. ASSIST09 chỉ là historical/reference/fallback; không thêm lượt train hay đánh giá trên ASSIST09. Các lock A/B/C, checkpoint, graph, split và kết quả cũ không áp dụng cho v4.

Snapshot tải: `82b29188dffd2fd6bd3abc5a3de0db1ef1df12b9`. SHA-256 ba CSV trong `configs/foundationalassist_v4_preprocessing.json`. Counts được tính từ snapshot thực tế, có thể khác README. Không bù/xóa dữ liệu để khớp README.

Trạng thái: RQ1 hoàn tất. Training Configuration và feature/code manifest đã commit `35e5c17` trước fit; Lock B v4 commit `30f8c92` trước one-shot TEST. Xem `reports/foundationalassist_v4_rq1_test.md`. RQ2 đã chạy các nhánh phát triển VALIDATION; từ 04/10/2026 khôi phục Agent chọn độc lập làm hướng chính theo `reports/rq2_selection_protocol_v2.md`, batch mới chỉ chuẩn bị. Chưa có TEST v4, content review còn chờ. Không chạy lại final TEST hoặc điều chỉnh mô hình theo TEST.

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

Hai policy B+ deterministic và Local Agent nhận cùng BKT latent state, cùng graph và cùng candidate metadata (`problem_id`, `skill_id`, difficulty proxy, support). Hai policy không cần question text để chọn ID; do đó metadata candidate inventory được xây riêng trên TRAIN và không bị chặn bởi `rq2_text_eligible`. Nó vẫn loại problem có metadata conflict và chỉ chứa candidate trong skill scope đã chọn. BKT checkpoint phải được fit trên TRAIN v4; không dùng checkpoint ASSIST09. Mô hình thắng RQ1 không bắt buộc là nguồn state.

Thiết kế metadata-only phải có hai baseline: chọn đều ngẫu nhiên theo problem ID trong candidate set hợp lệ, và luôn chọn candidate đầu tiên theo thứ tự được trình bày. Mỗi repetition VALIDATION dùng một hoán vị có seed; cùng thứ tự được đưa cho B+, Agent và cả hai baseline, còn các repetition khác nhau dùng hoán vị khác. Ghi lại seed/thứ tự, giữ nguyên thành viên candidate set, và báo cáo tần suất chọn theo vị trí cùng độ ổn định khi problem đổi vị trí. Khóa số repetition và cách tạo permutation trước Lock C. Đây là phép kiểm tra vận hành/position bias, không phải chất lượng dạy học.

Skills.csv là problem–skill mapping, không phải prerequisite graph. Xây graph riêng có nguồn curriculum hoặc giả định được ghi rõ. Graph, candidate rules và prompt phát triển bằng TRAIN/VALIDATION, khóa trước TEST RQ2 mới.

`node_code` có định dạng mã chuẩn Common Core, nhưng đây chỉ là căn cứ nhận diện standard, không tự chứng minh cạnh tiên quyết. Với nội dung Illustrative Mathematics được phân phối trên ASSISTments, dùng Copyright Notice của ASSISTments làm nguồn license: nội dung IM thuộc phạm vi notice được nêu là CC BY-NC-SA 4.0; một số bài có thể đã được ASSISTments chỉnh sửa hoặc tách phần. FoundationalASSIST không chỉ gồm nội dung IM, và metadata hiện có chưa xác định nguồn IM theo từng problem. Vì vậy không áp license IM cho toàn dataset; trước khi tái sử dụng/hiển thị nội dung cụ thể cần xác minh attribution và license theo problem. Ưu tiên diễn giải thay vì sao chép nguyên văn; ghi attribution và ShareAlike khi áp dụng.

Graph draft phải phân biệt (a) cạnh liên standard/domain/grade được đề xuất từ thứ tự curriculum và (b) các standard con cùng cluster. Các standard con như `6.RP.A.3a–d` và pilot `7.RP.A.2a–c` là các khía cạnh trong cùng cluster; không mặc định nối thành chuỗi tiên quyết tuyến tính. Cạnh curriculum không chứng minh mastery nguồn là điều kiện cần để học đích.

Theo hướng người dùng ngày 02/10/2026, tiếp tục project giáo dục riêng bằng graph tác giả đề xuất có nguồn, ghi `expert_validated=false`, dùng cho metadata-only development. Draft ở `configs/foundationalassist_v4_rq2_curriculum_graph.json`; nguồn và giới hạn ở `reports/foundationalassist_v4_rq2_graph_decisions.md`. Human review không chặn metadata-only development; vẫn cần trước khi tuyên bố expert validation hoặc chất lượng sư phạm. AI critique kể cả Astra không thay human review. Khóa giả định này và thiết kế độ nhạy bỏ cạnh trước TEST RQ2; chưa Lock C.

### Điều kiện `rq2_text_eligible`

Cờ chỉ bật khi đồng thời: metadata không conflict; body tồn tại; không phụ thuộc image/media/external asset; options và answer parse được đúng loại câu hỏi; math markup giữ đủ ý nghĩa; skill mapping phù hợp với thiết kế. MVP dùng single-skill cho state/policy tương thích. Cờ này áp dụng cho candidate có thể hiển thị nội dung hoặc dùng trong human pedagogical review/demo, không áp dụng cho metadata-only ranking bank.

Screen tự động chỉ đánh dấu `automatic_screen_pass`. Không có ảnh không chứng minh đủ nội dung. `rq2_text_eligible=False` cho tới khi có xác nhận nội dung kèm người rà soát/nguồn. Không yêu cầu rà toàn bộ 2.233 bài qua automatic screen chỉ để chạy metadata-only policy: trước hết tạo scenario trên VALIDATION, lấy hợp các `problem_id` thực sự xuất hiện trong candidate lists, rồi chỉ rà các item duy nhất đó nếu cần hiển thị nội dung hoặc human pedagogical assessment. Người rà graph nên đồng thời rà các item đã surfaced để gom thành một đợt; hiện chưa xác định được người này. Review kiểm tra cả phụ thuộc biểu đồ, nội dung phần trước và lựa chọn trả lời, không chỉ `<img>`.

Normalize bảo toàn HTML/LaTeX: Unicode NFC và newline thống nhất, giữ nguyên markup; không strip tags cho input Agent. Nếu hiển thị HTML cho người chấm, cần renderer bảo toàn toán và vô hiệu hóa mã/script cùng tài nguyên ngoài. Không đưa raw HTML không tin cậy vào trang chạy trực tiếp. Đáp án dùng kiểm tra parse nội bộ; không tự động đưa đáp án vào prompt recommendation.

Review packet cục bộ ở `data/processed/foundationalassist_v4/rq2_content_review.json` lưu đủ phiên bản conflict, lý do screen và các ô review; không đưa lên Git. Việc review bài không cần xem kết quả TEST. Metadata-only Agent chỉ nhận ID bài, skill, difficulty proxy tính trên TRAIN, support, state và graph; vì thế kết quả chỉ hỗ trợ phát biểu về hành vi chọn/xếp hạng theo các tín hiệu này, tính hợp lệ candidate, tuân thủ ràng buộc, mức đồng thuận với B+, latency/độ ổn định và position bias. Không gọi đó là chất lượng sư phạm, độ phù hợp nội dung hay lợi ích học tập. Chỉ nội dung đã `rq2_text_eligible=True` mới được hiển thị cho người chấm/demo hoặc dùng cho đánh giá chất lượng dựa trên nội dung.

## 7. Đánh giá và giới hạn

Hướng chính từ 04/10/2026: BKT ước lượng kỹ năng → candidate set → Agent chọn độc lập, B+ là baseline; xem `reports/rq2_selection_protocol_v2.md`. Agreement với B+ chỉ là metric bổ sung, không phải chất lượng giáo dục. Nhánh 03/10 B+ chọn/Agent giải thích giữ làm kết quả phụ: 132/144 xác định đúng yếu tố quyết định và 21/144 đạt toàn bộ gate dẫn chứng, chưa phải điểm ngữ nghĩa. Renderer chỉ dựng câu từ catalog đã kiểm tra; raw draft chưa được xác minh ngữ nghĩa và không hiển thị. Luồng mới lưu response trước truy vấn runtime sau call, bảo toàn source đã pin của thí nghiệm cũ. Chuẩn bị một batch 144 calls VALIDATION trên scenario đã quan sát, chưa gọi model; không sweep, chưa Lock C hoặc TEST.

RQ2 là exploratory recommendation study, đo vận hành và chất lượng dưới rubric nếu có người chấm. Quy trình human evaluation/prompt/model/rubric của ASSIST09 không tự động trở thành Lock C v4. Cần thiết kế và khóa riêng trước TEST v4. Không tuyên bố learning gain hoặc causal benefit nếu chưa có thử nghiệm học tập phù hợp.

Giới hạn phải báo: single-skill filtering, filtered sequences không cập nhật những tương tác bị loại, missing label/time, định nghĩa outcome, BKT latent estimates, graph provenance, text-only selection bias và các bài không đủ nội dung.

## 8. Checklist tiến độ

- [x] Xác minh snapshot và SHA-256.
- [x] Audit duplicate, missing, chronology và metadata conflict.
- [x] Khóa cleaning và báo số interaction mất theo từng filter.
- [x] Tạo và lưu split học sinh mới.
- [x] Tạo screen nội dung bảo toàn markup, fail-closed cho RQ2.
- [x] Tạo metadata-only TRAIN candidate inventory tách khỏi text eligibility; chưa khóa C.
- [x] Tạo graph draft có nguồn: 15 chuẩn/18 skill ID, 9 cạnh chuẩn; chưa expert-validated, chưa Lock C.
- [x] Tạo 50 VALIDATION scenarios v4/69 surfaced IDs, chạy B+ v4, random-by-ID và always-first dưới permutation chung; xem `reports/foundationalassist_v4_rq2_review_response.md`.
- [x] Chẩn đoán coverage trên 750 VALIDATION học sinh; giữ pilot 50 học sinh, bổ sung riêng cohort thăm dò 33 học sinh tại prefix50. Xem `reports/foundationalassist_v4_rq2_coverage.md`; không gộp cohort hoặc suy ra chất lượng sư phạm từ graph sensitivity.
- [ ] Chốt vai trò từng cohort và protocol cuối trước Lock C; thiết kế bổ sung được chọn sau coverage audit, chưa tiền đăng ký.
- [x] Đo prompt_eval_count bằng Ollama thật và chạy 498 Agent VALIDATION calls qua hai cohort riêng; xem `reports/foundationalassist_v4_rq2_agent_validation.md`. Hậu kiểm đạt, chưa mở TEST. Agent hiện tại thiên lệch vị trí mạnh; cần chốt hướng cuối trước Lock C.
- [x] Sửa schema/logging và kiểm chứng hữu hạn: 432 calls mới, 152 tests PASS; xem `reports/foundationalassist_v4_rq2_agent_repair.md`. Validity đạt trong thử nghiệm nhưng order bias/decision stability chưa giải quyết hoàn toàn; không tự promote cấu hình hoặc mở TEST.
- [x] Thử calculator hữu hạn: 144 calls VALIDATION, parity B+ và hậu kiểm đạt, 160 tests PASS; xem `reports/foundationalassist_v4_rq2_agent_calculator.md`. Các giá trị tính sẵn chưa cải thiện nhất quán khả năng thực hiện luật/stability; giữ kết quả âm, không sweep thêm hoặc tự khóa C. Chuyển sang B+ chọn/Agent giải thích, nếu chọn hướng đó, là thay đổi RQ2 cần protocol riêng.
- [x] Triển khai B+ chọn/Agent giải thích cùng template baseline và renderer có kiểm tra. 171 tests PASS; lượt đầu giữ archive do runtime drift, replication 144 calls trên Ollama 0.35.1 có request giống hệt và hậu kiểm đạt. Chỉ 21/144 lời giải thích đạt toàn bộ gate, chưa đặt Agent mặc định. Xem `reports/foundationalassist_v4_rq2_explanation.md`; raw draft chưa review ngữ nghĩa, Lock C/TEST vẫn đóng.
- [ ] Hoàn thành rà soát nội dung để bật eligibility cho problem bank RQ2.
- [x] Khôi phục Agent chọn độc lập làm nhánh chính; chuẩn bị protocol v2 và 144 calls VALIDATION, chưa inference. Thêm journal bền vững trước post-call runtime query, 181 tests PASS; các runner/artifacts đã pin giữ nguyên. Xem `reports/rq2_selection_protocol_v2.md`.
- [x] Khóa features/models/evaluation và kiểm thử đường chạy RQ1 v4.
- [x] Train/VALIDATION RQ1; Lock B v4; one-shot TEST.
- [ ] Graph, B+, Agent development; Lock C v4; one-shot TEST RQ2.

Không cần chờ toàn bộ RQ2 xong mới train RQ1; Gate RQ1 chỉ phụ thuộc protocol và kiểm thử RQ1.
