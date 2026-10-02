# Thử nghiệm Agent với bằng chứng tính sẵn

Ngày 02/10/2026. Đã chạy thêm đúng **144 lượt VALIDATION** bằng Qwen2.5:1.5b, tất cả hợp lệ. Tuy nhiên, **bộ tính toán hỗ trợ chưa sửa được việc thực hiện luật chọn bài hoặc tính ổn định**. Đây là kết quả development âm; chưa Lock C, chưa mở TEST RQ2 và không train lại RQ1.

## Mục đích và thay đổi

Revision1 sửa được schema/logging. Model trial trước giảm xu hướng chọn bài đầu so với Gemma nhưng vẫn rất ít lựa chọn đúng luật B+. Thử nghiệm này kiểm tra việc đưa sẵn các phép tính cho Agent có giúp thực hiện luật hay không.

Mỗi ứng viên nhận thêm ba giá trị:

- `weak_linked_source`: skill nguồn yếu có cạnh trực tiếp tới skill đích yếu hiện diện trong danh sách ứng viên hay không, theo ngưỡng 0,5 đã dùng ở B+.
- `train_success_gap`: trị tuyệt đối giữa TRAIN success rate của bài và mốc 0,7. Đây không phải xác suất học sinh hiện tại làm đúng.
- `train_support`: số quan sát TRAIN của bài.

Giữ từng skill ID riêng, kể cả khi cùng mã chuẩn. Không pooling mastery, không AND các skill và không biến cạnh thành hard prerequisite. Tín hiệu cạnh tính từ graph **đang được cung cấp**; phiên bản không cạnh luôn có `weak_linked_source=false`. Graph tham chiếu đầy đủ chỉ dùng để chấm cùng tiêu chí soft-remediation cho cả hai phiên bản.

Giữ thứ tự hiển thị cũ cho cả danh sách ứng viên và bảng bằng chứng. Không truyền ID đáp án B+, rank hoặc shortlist; enum vẫn dùng permutation độc lập đã lưu. B+ nhận cùng bằng chứng và so theo tuple `(ưu tiên nguồn yếu, gap, -support, ID)`. Không làm tròn gap: giữ đúng phép trừ float trong B+ đã khóa để tránh thay đổi tie-break.

Đây là **tiền tính bằng Python rồi đưa số liệu vào prompt**, chưa phải mô hình tự gọi công cụ. Không coi việc tái tạo luật B+ là sáng tạo tri thức sư phạm. Baseline calculator B+ khớp chính xác B+ cũ trên 144/144 đầu vào; không thay baseline đã lưu hoặc tuyên bố đo lại latency B+.

## Thiết kế trước khi chạy

Config `configs/foundationalassist_v4_rq2_agent_calculator1.json` khai báo đúng một intervention, 144 study calls và metric trước khi chạy. Dùng lại 12 scenario pilot và 12 scenario challenge, mỗi scenario ba permutation và hai graph variant. State, candidate membership/display order, enum, model, temperature, context/output budget và lý do tối đa 160 ký tự giống model trial trước. Chỉ thêm bảng bằng chứng và hướng dẫn cách dùng bảng.

Mẫu này đã được xem ở lượt development trước, vì vậy **không phải xác nhận trên mẫu độc lập**. Challenge được chọn có điều kiện, không đại diện; báo riêng hai cohort. Không tiếp tục sweep prompt/model sau lượt này.

Ngưỡng chẩn đoán đã ghi trước: tất cả đầu ra hợp lệ, agreement với B+ ít nhất 95%, variability không quá 10% trong từng cohort/variant. Ngưỡng này chỉ giúp quyết định liệu bản sửa có thực hiện đáng tin cậy luật đã nêu hay chưa, không tự cấp quyền Lock C hoặc chứng minh lợi ích giáo dục.

Runtime Ollama 0.34.4, model digest giữ nguyên `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. Bốn context probes được lưu riêng: prompt có/không cạnh 2.340/2.117 token, bằng nhau ở context 8.192 và 16.384, generation kết thúc bình thường. Không cắt state, graph hay candidates để đạt budget; output vẫn 256 token.

## Kết quả

Mỗi ô có 36 lượt hợp lệ. Agreement đo thực hiện **luật số đã được nêu rõ**, không đo chất lượng giáo dục. Variability là số học sinh thay ID giữa ba permutation / số học sinh đủ ba lượt hợp lệ.

| Cohort / graph | Agreement Qwen trước | Agreement có calculator | Variability trước | Variability có calculator | Chọn đầu trước → mới |
|---|---:|---:|---:|---:|---:|
| Pilot / có cạnh | 1/36 (2,78%) | 1/36 (2,78%) | 10/12 | 12/12 | 12/36 → 14/36 |
| Pilot / không cạnh | 2/36 (5,56%) | 2/36 (5,56%) | 10/12 | 11/12 | 12/36 → 14/36 |
| Challenge / có cạnh | 0/36 (0%) | 1/36 (2,78%) | 12/12 | 12/12 | 22/36 → 21/36 |
| Challenge / không cạnh | 8/36 (22,22%) | 6/36 (16,67%) | 11/12 | 12/12 | 21/36 → 18/36 |

Không nhóm nào đạt ngưỡng chẩn đoán đã khai báo. B+ vẫn không đổi ID khi đảo ứng viên. Trong challenge, Agent có calculator chọn soft-remediation ở 3/36 lượt cho mỗi graph variant, so với 2/36 trước; sự thay đổi nhỏ này không chứng minh cải thiện đáng tin cậy.

Agent đổi lựa chọn giữa có/không cạnh: pilot 19,44% trước và sau; challenge 19,44% → 22,22%, với 36 cặp hợp lệ mỗi cohort. Đây là phản ứng của lựa chọn với graph trên cùng candidate set, không chứng minh graph đúng hoặc learning gain. First enum position lần lượt 3/36, 3/36, 7/36 và 5/36; vẫn phải phân biệt enum order với display order.

Tất cả 144 lượt mới hợp lệ, không retry, sửa đáp án hoặc fallback. Tính hợp lệ đầu ra vẫn ổn; đưa thêm phép tính không tạo cải thiện nhất quán về thực hiện luật hoặc stability. Kết quả cho thấy **cách hỗ trợ tính toán này chưa đủ**, không chứng minh một nguyên nhân duy nhất của lỗi, cũng không khái quát cho mọi LLM. Chưa chấm tính đúng đắn của reason, không xem lời giải thích trôi chảy là bằng chứng chọn đúng.

## Hậu kiểm và tái lập

- 160 kiểm thử tích hợp đạt, gồm tám kiểm thử mới về endpoint, multi-ID, không leak graph qua evidence, giữ thứ tự ứng viên, gap/tie-break, parity B+, evidence bị sửa và telemetry/logging không fallback.
- Runner `scripts/run_foundational_rq2_agent_calculator1.py` pin nguồn/config/lịch chạy/kết quả trước, chặn ghi đè cả completed và partial calls, kiểm tra lại hash/model/runtime cuối lượt.
- Auditor `scripts/audit_foundational_rq2_agent_calculator1.py` không gọi model. Nó dựng lại bằng chứng từ graph variant, so request mới với request Qwen cũ, xác nhận chỉ thay evidence/instruction, kiểm tra toàn bộ raw responses, positions, metric, parity và bốn context probes.
- Public summary/audit ở `artifacts/tables/foundationalassist_v4_rq2_agent_calculator1_*.json`, chỉ chứa thống kê tổng hợp. Full request/response/reason và lịch theo học sinh nằm trong `data/processed/foundationalassist_v4/rq2_validation/agent_calculator1/`, bị Git bỏ qua.
- RQ1, split, checkpoint và mọi lượt Agent trước giữ nguyên. Config/code mới giữ LF; public JSON snapshot giữ CRLF theo `.gitattributes`, đảm bảo SHA-256 có thể tái lập sau checkout.

## Hướng hoàn thiện RQ2

Giữ kết quả âm này trong báo cáo; không tự promote calculator thành cấu hình cuối và không tiếp tục chỉnh trên cùng subset chỉ để nâng agreement. Có hai hướng cần trình bày minh bạch khi chốt protocol cuối:

1. Giữ RQ2 về Agent chọn bài độc lập, chốt một cấu hình và báo giới hạn vận hành/kết quả âm sau khi hoàn thành gate đánh giá. Không đổi nghĩa agreement thành chất lượng giáo dục.
2. Nếu mục tiêu ưu tiên một hệ thống vận hành ổn định, để B+ chọn và Agent giải thích bằng chứng. Hướng này thay vai trò Agent và câu hỏi RQ2; phải viết lại thiết kế, định nghĩa/chấm grounded explanation, rồi khóa riêng trước TEST. Không gọi đó là sửa thành công Agent chọn bài độc lập.

Graph vẫn author-proposed, chưa expert-validated. Đánh giá sư phạm theo nội dung vẫn cần reviewer và content eligibility; nghiên cứu vận hành metadata-only phải giữ giới hạn phát biểu tương ứng. Chưa có cơ sở tuyên bố ưu thế giáo dục hoặc learning gain.
