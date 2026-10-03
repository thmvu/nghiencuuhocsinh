# B+ chọn bài và Agent giải thích: kiểm chứng development

Ngày 03/10/2026. Đã triển khai nhánh giải thích có kiểm tra bằng chứng và chạy Agent thật. **Bộ kiểm tra hoạt động, nhưng Agent chưa đạt độ tin cậy để làm nguồn giải thích mặc định**: trong lượt runtime ổn định, 144/144 đầu ra đúng schema/ID, chỉ 21/144 đạt toàn bộ kiểm tra. Template đạt 144/144 theo thiết kế. Chưa Lock C hoặc mở TEST RQ2; RQ1 không train lại.

## Thay đổi vai trò RQ2

Theo hướng người dùng đồng ý tiếp tục, B+ là thành phần duy nhất chọn bài. Agent nhận lựa chọn cố định và bảng bằng chứng để xác định yếu tố quyết định, dẫn chứng và viết một draft ngắn. Nhánh Agent chọn bài độc lập và các kết quả âm trước được giữ nguyên làm development reference. Không gọi nhánh mới là sửa thành công khả năng chọn độc lập.

Thiết kế ở `reports/rq2_grounded_explanation_design.md`; config gốc ở `configs/foundationalassist_v4_rq2_explanation1.json`. Bảng bằng chứng chỉ dùng metadata TRAIN, state đã lưu và graph variant được cấp; không có đề bài hoặc dữ liệu tương lai. Các ID cùng standard giữ state riêng. Graph vẫn author-proposed, chưa expert-validated.

Trace ghi số ứng viên còn lại sau từng bước xếp hạng. Bước đầu tiên còn đúng một ứng viên là yếu tố quyết định; không nhận một bước sau làm nguyên nhân chính. Renderer kiểm tra lại fixed ID, factor, membership/độ đầy đủ citation và không trùng citation; chỉ dựng câu từ fact catalog đã tính. Nó **không hiển thị raw draft**. Đầu ra lỗi bị từ chối rõ, không retry/sửa đáp án hoặc âm thầm dùng template để tăng tỷ lệ Agent đạt.

Baseline template dùng cùng bằng chứng. Renderer đảm bảo câu hiển thị nằm trong catalog theo thiết kế; không coi đó là bằng chứng LLM hiểu hoặc viết chính xác. Ngay cả draft chứa tuyên bố learning gain sai cũng có thể vượt kiểm tra cấu trúc nếu các trường khác đúng: kiểm thử đã xác nhận draft ấy không được hiển thị, và trạng thái ngữ nghĩa vẫn chưa xác minh. Muốn đánh giá raw draft/readability phải có rubric và review riêng.

## Hai lượt và sự cố runtime

Giữ đúng subset cũ: 12 pilot và 12 challenge, ba permutation và hai graph variant, 144 calls mỗi lượt. Đây là mẫu development đã xem, không phải xác nhận độc lập; hai cohort báo riêng. Temperature 0, context 8.192, output 512, draft tối đa 240 ký tự. Không sweep model hoặc prompt.

Lượt đầu thực hiện đủ 144 calls nhưng gate cuối phát hiện Ollama đổi **0.34.4 → 0.35.1**. Hash Qwen2.5:1.5b vẫn khớp `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. Lượt này có 37 transport errors và 19 đầu ra đạt kiểm tra, nhưng không xác định được ranh giới đổi runtime. Không suy nguyên nhân chính xác của từng lỗi từ việc đổi version. Lưu nguyên kết quả với trạng thái `completed_runtime_drift_not_validated`; các số đó chỉ là chẩn đoán lưu trữ, không dùng làm estimate đã xác nhận hoặc gộp với lượt sau.

Sau sự cố, khai báo đúng một replication kỹ thuật trong `configs/foundationalassist_v4_rq2_explanation1_replication.json`, pin Ollama **0.35.1** và giữ **request giống hệt** lượt trước. Không đổi prompt, schema, model, các giới hạn generation, state, candidates, permutation, enum hoặc cách chấm dựa trên kết quả vừa thấy. Kiểm tra model/version sau mỗi probe và trước/sau từng study call. Lượt đầu, config và code gốc được giữ để bảo toàn provenance.

Replication thực hiện đủ 144 calls, runtime gate đạt. Bốn context probes riêng có prompt count 700 token cho từng graph variant, bằng nhau ở context 8.192 và 16.384; generation hoàn tất bình thường. Byte guard tối đa 4.511/4.512, không cắt bằng chứng. Tổng thực tế là 288 study calls + 8 context probes; chỉ lượt replication ổn định dùng trong bảng kết quả bên dưới.

## Kết quả replication trên Ollama 0.35.1

Mỗi ô có 36 study calls của 12 học sinh. Mẫu số gồm toàn bộ calls, không bỏ lượt lỗi. Các repetition thuộc cùng học sinh, không coi là quan sát độc lập. Schema validity gồm cấu trúc, draft không trống và giới hạn độ dài.

| Cohort / graph | Schema và fixed ID | Factor đúng | Citation không trùng/ngoài catalog | Coverage đủ | Đạt tất cả | Template |
|---|---:|---:|---:|---:|---:|---:|
| Pilot / có cạnh | 36/36 | 36/36 | 24/36 | 0/36 | 0/36 | 36/36 |
| Pilot / không cạnh | 36/36 | 36/36 | 21/36 | 0/36 | 0/36 | 36/36 |
| Challenge / có cạnh | 36/36 | 24/36 | 33/36 | 31/36 | 21/36 | 36/36 |
| Challenge / không cạnh | 36/36 | 36/36 | 27/36 | 0/36 | 0/36 | 36/36 |

Tổng tỷ lệ đạt tất cả là **21/144 = 14,58%**; chỉ dùng như thống kê mô tả trên hai cohort development, không như estimate cho toàn bộ học sinh. Bài B+ chọn không đổi khi đảo ứng viên ở 12/12 học sinh trong từng cohort/variant. Độ ổn định này thuộc B+, không phải công của Agent. Challenge có cạnh có 7/12 học sinh đủ cả ba lời giải thích đạt; các nhóm khác 0/12.

Coverage chấm `rank_<bước quyết định đúng từ trace>` cùng `selected_item`, `state_estimate`, `graph_assumption`, `learning_limit`. Wording `rank_<predicted decisive factor>` trong config mô tả trường Agent phải trả; code đã pin trước run chấm coverage theo bước đúng, đồng thời chấm factor accuracy riêng. Khi factor sai, dẫn chứng đúng cho một bước khác vẫn không làm explanation được chấp nhận. Đây là coverage của các trường bắt buộc, không phải semantic grounding của draft tự do.

Chẩn đoán bổ sung sau run: 39 calls có citation trùng; 12 calls sai factor. Có 113 calls thiếu `selected_item`, 113 thiếu `graph_assumption`, 113 thiếu `learning_limit`, 76 thiếu `state_estimate` và 78 thiếu `rank_success_gap`. Các nhóm lỗi chồng lấp, không cộng thành số calls lỗi. Điều này giải thích vì sao JSON đúng và ID đúng chưa đủ. Không nới gate hoặc tune prompt sau khi nhìn các số này.

Mean latency mỗi nhóm khoảng 1,19–1,51 giây; output tối đa 162 token, không có transport/telemetry error trong replication. Đây là latency pipeline gọi Agent/logging, không phải phép so tốc độ với template đã benchmark. Không lấy việc output dưới budget hoặc schema hợp lệ làm bằng chứng explanation đúng.

## Hậu kiểm và code

- **171 kiểm thử tích hợp đạt**, gồm trace của bốn bước/singleton, parity với B+ qua permutation, no-edge/multi-ID, ID sai, factor sai, citation lạ/trùng/thiếu, blank/long draft, raw draft không được hiển thị, telemetry và không retry. Hai kiểm thử runtime tái hiện đổi version sau một study call, xác nhận giữ raw response và dừng; partial calls không bị ghi đè.
- Module `src/rq2/grounded_explanation.py` tạo packet, request, đánh giá cấu trúc và renderer. Các runner `scripts/run_foundational_rq2_explanation1.py` và `...explanation1_replication.py` tách đường dẫn, pin nguồn và chặn rerun âm thầm.
- `scripts/archive_foundational_rq2_explanation1_drift.py` lưu đúng trạng thái thất bại runtime gate. Auditor gốc xác nhận raw calls/metric có thể tái tính nhưng không nhận runtime identity đã đạt.
- `scripts/audit_foundational_rq2_explanation1_replication.py` xác nhận 144 request giống archive, phiên bản trước/sau mỗi call, trace/template, raw response được replay qua validator/renderer, metric và context probes. Auditor không gọi model.
- Public summaries/audits ở `artifacts/tables/foundationalassist_v4_rq2_explanation1*.json`. Private packets, raw draft/response, từng lựa chọn và lịch học sinh ở `data/processed/foundationalassist_v4/rq2_validation/explanation1/` và `explanation1_replication/`, bị Git bỏ qua.
- Không sửa config/model/split hoặc kết quả RQ1 và các study chọn bài trước. Config/source/thiết kế mới giữ LF; public snapshot JSON giữ CRLF theo attributes để tái lập SHA-256 sau checkout.

## Trạng thái để tiếp tục

Bộ kiểm tra cùng renderer có thể dùng để ngăn hiển thị đầu ra thiếu bằng chứng. Template là baseline kỹ thuật đáng tin cậy hơn trong task này; chưa có bằng chứng Agent tạo giá trị vượt template. Chưa đặt Agent làm lời giải thích mặc định, chưa gọi hệ thống này là sản phẩm hoàn chỉnh.

Không tiếp tục sweep trên cùng subset để kiếm tỷ lệ thuận lợi. Để hoàn tất RQ2 cần chốt protocol cuối: báo kết quả vận hành âm hoặc thêm đánh giá chất lượng draft có rubric/reviewer và mẫu phù hợp. Việc so nội dung bài/chất lượng giáo dục vẫn có yêu cầu review riêng; metadata-only explanation không thay thế bước đó. Chưa Lock C và chưa mở TEST để quyết định hướng nghiên cứu.
