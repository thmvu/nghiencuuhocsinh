# RQ2 v3 — lần phát triển cuối của Agent chọn bài độc lập

Ngày 04/10/2026. Báo cáo phát triển trên VALIDATION, chưa Lock C, chưa mở TEST RQ2. RQ1, cleaning, split và checkpoint BKT giữ nguyên. Agent chọn bài; B+ là policy tham chiếu, không phải đáp án vàng. Cả hai nhận cùng state ước lượng BKT và cùng candidate metadata từ TRAIN.

## Khóa trước thực thi

Protocol, code và config chẩn đoán được commit/push tại `7c8d189` trước 48 lượt chẩn đoán. Sau khi áp quy tắc chọn contract đã định trước, config batch chính và lịch nhóm mới được commit/push tại `00d9add` trước inference chính. Protocol/code/config của thí nghiệm được giữ nguyên sau inference; trạng thái thực thi nằm trong manifest riêng.

Model Qwen2.5:1.5b, Ollama 0.35.1, temperature 0, context 8.192, `num_predict=512`; digest model được khóa trong config. Inference gọi Ollama cục bộ. Không retry, fallback, sửa lựa chọn hay bỏ lượt có cờ.

## Chẩn đoán contract

24 request cũ chạy hai arm, cùng prompt v3 tiếng Việt/tối đa hai câu, chỉ khác `maxLength` 360/600. Thứ tự arm luân phiên theo index đã khóa. Không tính hoặc dùng metric chọn bài trong quyết định contract.

| Chỉ số | 360 | 600 |
|---|---:|---:|
| Lượt đã lên lịch/nhận response | 24/24 | 24/24 |
| Output lỗi/thiếu reason | 0 | 0 |
| Reason chạm trần | 0 | 0 |
| Có chữ CJK | 24 | 24 |
| Không kết thúc bằng `.`, `!`, `?`, `…` | 24 | 24 |
| Cờ số không khớp metadata | 11 | 8 |

Quy tắc đã khóa chọn **360**, vì arm 600 không giảm số lượt chạm trần. Không kết luận nguyên nhân cắt câu đã được xác định. Cờ kết thúc chỉ kiểm tra tập dấu câu của contract; câu kết thúc bằng dấu CJK cũng bị gắn cờ, nên không đồng nhất cờ này với câu thực sự dang dở. Cờ số là heuristic, không phải điểm đúng/sai ngữ nghĩa.

## Nhóm mới và giới hạn graph

40 học sinh VALIDATION chọn bằng seed 20261005, loại 81 học sinh đã xuất hiện trong các scenario RQ2 cũ. Nhóm mới chưa chạy policy/Agent trước lượt này; không gọi là hoàn toàn chưa xem, vì coverage audit trước đây đã kiểm tra 750 học sinh VALIDATION. Không còn học sinh mới thỏa tiêu chí challenge cũ, không nới tiêu chí để tạo challenge mới.

Mỗi học sinh có ba permutation và hai graph variant: 240 study calls. Membership/state giữ nguyên giữa các variant và permutation. Thêm bốn context probes; 12 request chọn trước bằng seed 20261007 được gửi lại nguyên văn ba lần (36 calls). Tổng batch chính 280, cộng chẩn đoán 48 là 328 lượt gọi.

Trong 40 scenario, 17 có nguồn graph yếu, 10 có đích graph yếu được trình bày, nhưng chỉ một có nguồn yếu liên quan cùng ứng viên nguồn. Đây là nhóm đại diện có ít tín hiệu graph; không dùng độ nhạy nhỏ để bác bỏ graph hoặc suy ra tác dụng sư phạm.

## Kết quả và hậu kiểm

Đã nhận đủ 328 responses: 48 chẩn đoán, 4 probes, 240 study và 36 repeat. Context probes có/không cạnh lần lượt 1.870/1.647 prompt tokens, bằng nhau ở context 8.192 và 16.384. Runtime identity trước/sau từng call và cuối batch đạt; request/response, input/source hashes, baseline replay và metric tái tính khớp. Không có lỗi transport/schema/telemetry trong study.

| Graph | Policy | Hợp lệ | ID/skill-stable | Hạng mastery TB | Chọn skill đáy | Chọn display đầu |
|---|---|---:|---:|---:|---:|---:|
| Có cạnh | Agent | 120/120 | 5/40; 5/40 | 0,593 | 11/120 | 22,5% |
| Không cạnh | Agent | 120/120 | 6/40; 6/40 | 0,594 | 8/120 | 21,7% |
| Có cạnh | B+ | 120/120 | 40/40; 40/40 | 0,582 | 0/120 | 10,8% |
| Không cạnh | B+ | 120/120 | 40/40; 40/40 | 0,600 | 0/120 | 10,0% |
| Cả hai, mỗi variant | Random | 120/120 | 0/40; 0/40 | 0,492 | 12/120 | 16,7% |
| Cả hai, mỗi variant | Always-first | 120/120 | 0/40; 0/40 | 0,452 | 19/120 | 100% |

Mỗi ô có 40 học sinh với đủ ba lượt hợp lệ. Mẫu số ổn định vận hành là 40 học sinh đã lên lịch; không coi 120 lượt là 120 học sinh độc lập. Hạng tính trên kỹ năng phân biệt, mid-rank khi đồng hạng; cả 240 lượt có hạng xác định. Hạng thấp chỉ nghĩa là chọn kỹ năng có mastery BKT thấp hơn, không phải lựa chọn tốt hơn về sư phạm.

Kỳ vọng giải tích random trong nhóm này: ID-stable 1/64, hạng mastery 0,5, chọn skill đáy 12,5%, mỗi vị trí 12,5%. Random bốc khác nhau theo lượt đã định trước; 0/40 ổn định không được diễn giải là thiên lệch vị trí. Agent không thể hiện xu hướng chọn kỹ năng mastery thấp hơn random trên nhóm này. B+ cũng không luôn chọn skill đáy, do có mục tiêu graph/độ vừa sức riêng; không nhận B+ là chuẩn vàng.

Agent chọn enum đầu 14/120 (11,7%) ở mỗi variant, display vị trí 1 (vị trí thứ hai, đánh số từ 0) ở 39/120 và 37/120. Đây là phân bố mô tả có dấu hiệu phụ thuộc cách trình bày, không kiểm định hoặc xác nhận nguyên nhân. Lặp nguyên request cho kết quả cùng ID ở **11/12 request qua cả bốn lần**; một request đổi ID dù input giống hệt. Đây là mức tham chiếu, không phải trần toán học và không quy toàn bộ biến động permutation cho thứ tự.

Agent đổi ID giữa có/không cạnh ở 27/120 cặp; B+ ở 3/120, random/always-first ở 0/120 theo thiết kế. Agent trùng B+ 19/120 mỗi variant, soft-remediation 0/120; B+ có cạnh soft-remediation 3/120. Chỉ một scenario có tín hiệu liên kết phù hợp, nên giữ giới hạn coverage khi giải thích độ nhạy graph. Latency Agent trung bình 0,934/0,730 giây có/không cạnh, gồm request/transport/runtime checks/validation; baseline chỉ đo tính policy nội bộ, không phải benchmark thời gian cùng phạm vi.

| Chiều đã khóa | Quan sát | Quyết định |
|---|---|---|
| Kỹ thuật: ≥236/240 hợp lệ, integrity đạt | 240/240, audit đạt | Đạt |
| Ổn định: ≥32/40 ở mỗi variant | 5/40 và 6/40 | Không đạt |
| Rationale: CJK ≤4; chạm trần ≤2; thiếu dấu kết thúc ≤12 | 240; 0; 240 trên 240 lượt | Không đạt cờ vận hành |
| Rubric ngữ nghĩa: điểm không điều kiện ≥1,5/2 | Chưa có người chấm | Chưa đánh giá |

Cờ số không khớp: 88/240; unknown-ID được heuristic nhận diện: 0; thiếu reason: 0. Cả 240 có dấu câu CJK và chữ CJK; không suy ra cả 240 câu bị cắt chỉ từ cờ dấu kết thúc. Không có lượt chạm trần. 36 lượt repeat được báo riêng, không gộp vào mẫu số study hoặc ngưỡng.

**Agent v3 chưa đạt yêu cầu vận hành đã đặt.** Giữ kết quả này, không chạy lại hoặc sửa cấu hình để vượt ngưỡng. Schema hợp lệ không chứng minh rationale đúng, graph hợp lý hoặc lợi ích học tập. Kết quả âm này thuộc một model/contract/nhóm VALIDATION cụ thể, không bác bỏ toàn bộ hướng BKT → Agent chọn bài.

## Rubric và bước tiếp theo

Cập nhật sau thí nghiệm: người dùng nhận tự rà soát; giao diện local và hướng dẫn ở `reports/rq2_selection_v3_author_review_guide.md`. Tác giả tự chấm được lưu riêng và không nhận là expert review độc lập. Không sửa protocol, phiếu source hoặc manifest này để thay đổi kết quả đã khóa. Nhánh training Agent/teacher examples mới chỉ là phương án tại `reports/rq2_small_agent_training_options.md`, chưa huấn luyện.

Đã tạo phiếu local 40 lượt hợp lệ bằng seed 20261006, cân bằng 20 mỗi graph variant, xáo thứ tự và ẩn danh model. Lấy mẫu từ tất cả lượt hợp lệ, bao gồm lượt có cờ. Điểm và reviewer còn trống. Chưa xác định người chấm, không tự tạo điểm và không thay người chấm bằng AI. Chiều rationale ghi **chưa đánh giá** về ngữ nghĩa; Agent không được xếp là đạt toàn bộ yêu cầu chỉ dựa vào schema hoặc các cờ.

Sau v3 không sửa thêm prompt/model/contract hoặc nhóm học sinh để cải thiện kết quả. Trước Lock C cần hoàn tất thiết kế TEST: scenario rules, metric/CI, failure handling và rubric/rater, commit trước một lần mở TEST. Metadata-only chỉ hỗ trợ kết luận vận hành; không đo chất lượng sư phạm, nội dung bài hoặc learning gain. Graph vẫn là tác giả đề xuất, chưa expert-validated.

## Tái lập và lưu trữ

Protocol: `reports/rq2_selection_protocol_v3.md`. Config: `configs/foundationalassist_v4_rq2_selection_v3_diagnostic.json` và `configs/foundationalassist_v4_rq2_selection_v3.json`. Runner: `scripts/run_foundational_rq2_selection_v3.py`. Hậu kiểm: `scripts/audit_foundational_rq2_selection_v3.py` (không gọi model). Manifest/audit tổng hợp ở `artifacts/tables/foundationalassist_v4_rq2_selection_v3_*.json`.

Journal, request, response, schedule, phiếu chấm và output theo học sinh nằm trong `data/processed/foundationalassist_v4/rq2_validation/selection_v3/`, bị Git bỏ qua. Không đưa ID học sinh, text bài toán hoặc predictions theo dòng lên Git. 200 kiểm thử tích hợp đạt trước batch chính và trước commit kết quả; hậu kiểm v2 chỉ đọc cũng đạt và không gọi model. Ba thử nghiệm thay đổi dữ liệu trong bộ nhớ (reason, metric và thiếu repeat record) đều bị auditor từ chối; không sửa dữ liệu thật hoặc gọi model thêm. Kiểm tra các manifest công khai không chứa trường ID học sinh, request/raw response hoặc kết quả theo dòng cũng đạt.
