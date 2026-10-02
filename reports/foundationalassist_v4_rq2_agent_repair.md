# Sửa Agent và kiểm chứng trên VALIDATION

Ngày 02/10/2026. Đã sửa tính hợp lệ đầu ra và khả năng audit; **chưa khắc phục hoàn toàn thiên lệch vị trí hoặc khả năng thực hiện luật chọn bài**. RQ1, split và 498 lượt Agent cũ giữ nguyên. Chưa Lock C hoặc mở TEST RQ2.

## Thay đổi có code

- Schema mới giới hạn `problem_id` bằng enum đúng candidate IDs; reason tối đa 160 ký tự. Validator vẫn kiểm tra ID, reason và telemetry sau generation. Không sửa đáp án, retry hoặc fallback để biến lượt lỗi thành hợp lệ.
- Enum được xáo bằng RNG độc lập với display order, dùng chung giữa hai arm và hai graph variant. Lưu cả vị trí display và enum để kiểm tra thiên lệch ở cả hai nơi.
- Private record lưu request, response, reason gốc, prompt/output token counts, done_reason, error stage/message, HTTP status/body. Telemetry vẫn được giữ khi generation chạm giới hạn. Không đưa những record này lên Git.
- Arm `schema_only` giữ nguyên prompt cũ, chỉ thay schema. Arm `schema_and_objective` dùng cùng schema và nêu rõ thứ tự xét direct weak source–target, độ gần TRAIN success rate 0,7, support, rồi ID. Không truyền đáp án B+ hoặc sort candidate theo B+ trước khi gửi.
- Objective arm cố ý mô tả luật B+; agreement đo thực hiện luật số, không chứng minh Agent tạo tri thức hoặc chất lượng sư phạm mới.
- Các runner mới tách đường dẫn, chặn ghi đè một study đã hoàn tất, pin config/source/schedule/archived results và kiểm tra lại hash/runtime khi kết thúc. Runner cũ được giữ để bảo toàn provenance, không phải entrypoint của bản sửa.

Code ở `src/rq2/agent_revision.py`. Các config/run script có tên `agent_revision1` và `agent_model_trial1`; đây là phiên bản development, chưa cấu hình cuối.

## Thiết kế hữu hạn

Chọn 12 scenario mỗi cohort bằng seed 20261002, không dùng kết quả policy để chọn. Giữ original scenario index, state, candidates và cả 3 permutation đã dùng ở lượt cũ. Hai subset không trùng học sinh nhưng vẫn báo riêng vì challenge được chọn có điều kiện và không đại diện.

Revision1 có 288 study calls: 12 × 2 cohort × 3 permutation × 2 graph variant × 2 arm. So với đúng 144 archived legacy calls trên các scenario tương ứng; không gọi lại legacy để thay kết quả.

Preflight ban đầu không đạt điều kiện generation hoàn tất, chưa có study calls. Sau đó bổ sung reason maxLength=160 vào cả hai schema trước lượt study. Initial failed preflight chưa giữ đủ raw responses nên không quy mọi nguyên nhân thành output-limit. Preflight sau sửa giữ đủ 8 response và đạt: schema-only có/không cạnh 1.726/1.503 token; objective 1.873/1.650, counts bằng nhau ở context 8.192 và 16.384. Output budget vẫn 256.

Revision1 khắc phục validity nhưng Gemma vẫn thiên lệch vị trí. Vì máy chỉ còn khoảng 1,3 GB RAM trống, thử thêm đúng một model local `qwen2.5:1.5b`, download 986.061.892 byte. Chọn theo tài nguyên và [mô tả model chính thức](https://ollama.com/library/qwen2.5), không giả định trước rằng model tốt hơn. Gemma cache được unload để giải phóng RAM; không xóa model. Qwen digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`, runtime Ollama 0.34.4.

Model trial có 144 study calls, dùng **đúng request của objective arm, chỉ thay model**. Context preflight giữ 4 response: có/không cạnh 1.830/1.607 token, counts bằng nhau ở hai context. Không chạy sweep thêm model/prompt hoặc dùng TEST.

## Kết quả trên cùng subset

Mỗi ô mới có 36 study calls. Tỷ lệ bài đầu tính trên lượt hợp lệ. Variability là số học sinh đổi ID giữa 3 permutation / số học sinh có cả 3 lượt hợp lệ, không phải tỷ lệ từng lượt đổi.

| Cohort / graph | Legacy hợp lệ | Legacy chọn đầu | Schema-only chọn đầu | Objective Gemma chọn đầu | Objective Qwen chọn đầu |
|---|---:|---:|---:|---:|---:|
| Pilot / có cạnh | 34/36 | 32/34 (94,12%) | 34/36 (94,44%) | 31/36 (86,11%) | 12/36 (33,33%) |
| Pilot / không cạnh | 33/36 | 26/33 (78,79%) | 28/36 (77,78%) | 23/36 (63,89%) | 12/36 (33,33%) |
| Challenge / có cạnh | 34/36 | 33/34 (97,06%) | 35/36 (97,22%) | 32/36 (88,89%) | 22/36 (61,11%) |
| Challenge / không cạnh | 36/36 | 29/36 (80,56%) | 29/36 (80,56%) | 27/36 (75,00%) | 21/36 (58,33%) |

**Tất cả 432 study calls mới hợp lệ** (288 Gemma + 144 Qwen), so với legacy subset 137/144. Không quan sát lỗi mới trong các lượt này; không bảo đảm tỷ lệ 100% ở dữ liệu/runtime khác.

| Cohort / graph | Objective Gemma variability | Objective Qwen variability | Gemma agreement B+ | Qwen agreement B+ |
|---|---:|---:|---:|---:|
| Pilot / có cạnh | 12/12 (100%) | 10/12 (83,33%) | 5/36 (13,89%) | 1/36 (2,78%) |
| Pilot / không cạnh | 12/12 (100%) | 10/12 (83,33%) | 4/36 (11,11%) | 2/36 (5,56%) |
| Challenge / có cạnh | 11/12 (91,67%) | 12/12 (100%) | 3/36 (8,33%) | 0/36 (0%) |
| Challenge / không cạnh | 12/12 (100%) | 11/12 (91,67%) | 4/36 (11,11%) | 8/36 (22,22%) |

Schema-only vẫn variability 100% ở pilot và 91,67% ở challenge. Qwen giảm tỷ lệ chọn đầu nhưng stability vẫn kém; không đồng nhất giảm first-position rate với sửa xong decision policy. Agreement Qwen không cải thiện nhất quán. Trong challenge, Qwen soft-remediation chỉ 2/36 ở mỗi graph variant, so với Gemma objective 6/36 có cạnh và 4/36 không cạnh. B+ ổn định và thực hiện đúng rule theo code.

First enum position của các arm mới chiếm khoảng 8–17% trong từng cohort/variant; không thấy hành vi đa số chọn đầu enum trong subset này. Đây là mô tả, không phải kiểm định không thiên lệch hoặc bằng chứng sư phạm.

## Audit và giới hạn

- 152 kiểm thử tích hợp đạt, gồm enum/membership, budget, không leak reference graph trong no-edge prompt, blank reason, output-limit telemetry, HTTP body và không retry/fallback.
- `scripts/audit_foundational_rq2_agent_revision1.py` xác nhận 288 calls/raw responses/requests/positions, metric và hash cũ khớp. `scripts/audit_foundational_rq2_agent_model_trial1.py` xác nhận 144 calls và request **chỉ đổi model**, kiểm tra reason, positions, metric, hash cũ.
- Public summaries/audits ở `artifacts/tables/foundationalassist_v4_rq2_agent_revision1_*.json` và `...agent_model_trial1_*.json`; không chứa raw response, ID học sinh hoặc từng lựa chọn.
- Private schedule, full calls và probes ở `data/processed/foundationalassist_v4/rq2_validation/agent_revision1/` và `agent_model_trial1/`; bị Git bỏ qua.
- `.gitattributes` giữ CRLF cho các JSON snapshot RQ2, hai config mới và hai snapshot khóa final/preprocessing được RQ2 tham chiếu byte-for-byte, khớp SHA-256 đã ghi trên máy Windows. Không sửa nội dung hoặc byte hiện tại của config/model/code/dữ liệu RQ1. Kiểm tra tái dựng byte từ Git index + checkout EOL đảm bảo clone không tự làm lệch hash; không đổi dữ liệu để sửa số liệu.
- Reason giới hạn độ dài có thể thiếu giải thích; chưa chấm factual grounding hay chất lượng reason. Mẫu development nhỏ, comparison legacy ở thời điểm khác, không có kiểm định hoặc full-cohort xác nhận.

## Quyết định hiện tại

Giữ sửa schema/logging cho phiên bản tiếp theo. Không tự promote model thử nghiệm thành cấu hình RQ2 cuối; **chưa khóa Lock C**. Không thêm LLM lớn hơn chỉ để tìm kết quả thuận lợi trong điều kiện tài nguyên hiện tại.

Với task thuần metadata và luật chọn bài đã xác định, B+ vẫn là phần chọn bài đáng tin cậy hơn về vận hành. Nếu chuyển Agent sang giải thích kết quả B+, đó là thay đổi câu hỏi/thiết kế RQ2 và phải ghi rõ, không gọi là Agent độc lập chọn bài tốt hơn. Một hướng khác là giữ kết quả âm của Agent chọn bài để hoàn tất nghiên cứu, sau khi chốt protocol cuối. Chưa có cơ sở tuyên bố educational benefit hoặc learning gain.
