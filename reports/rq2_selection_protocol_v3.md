# RQ2: Agent chọn bài độc lập — protocol v3 (lần sửa cuối)

Ngày 04/10/2026. Protocol triển khai được commit cùng config/code trước 48 lượt chẩn đoán; config batch chính được commit riêng sau quyết định contract, trước inference chính. Đây là development lock, chưa Lock C, không truy cập TEST. Trạng thái thực thi ghi trong báo cáo và manifest riêng; protocol này được giữ nguyên sau lượt chẩn đoán đầu tiên.

## Lý do và phạm vi

Batch v2 (`reports/foundationalassist_v4_rq2_selection_v2.md`) đạt 144/144 lựa chọn hợp lệ nhưng ID-stable chỉ 1–3/12 học sinh mỗi ô. Đọc raw response thấy 104/144 reason có chữ Hán và 37/144 chạm đúng 360 ký tự, một số câu dang dở. Đây là phát hiện chẩn đoán, chưa phải chấm rubric.

v3 là **phiên bản sửa duy nhất và cuối cùng** của Agent chọn độc lập. Mọi quyết định dưới đây phải được commit trước khi chạy batch chính. Kết quả được giữ nguyên dù âm hay dương; sau v3 không sửa prompt/model/contract nữa.

Câu hỏi giữ nguyên: BKT ước lượng trạng thái → candidate set từ TRAIN → Agent chọn một bài và giải thích ngắn. B+, random-uniform-by-ID và always-first là baseline dùng cùng đầu vào; không baseline nào là đáp án vàng.

## Bước 1 — Thử contract (chỉ chẩn đoán)

Mục đích: kiểm tra giả thuyết `maxLength` trong schema gây cắt câu. Chưa kết luận nguyên nhân là grammar trước bước này.

- Prompt: prompt v3 đầy đủ (mục "Contract v3"), **giống hệt ở hai arm**, bao gồm yêu cầu tiếng Việt và tối đa 2 câu.
- Yếu tố thay đổi duy nhất: `reason.maxLength` = 360 so với 600. `num_predict=512` giữ nguyên ở cả hai arm.
- Input: 24 request cố định, lấy repetition 0, graph `curriculum_edges` của 24 học sinh trong subset v2 (12 pilot + 12 challenge). Tổng 48 calls. Đây là scenario đã dùng; ghi rõ là chẩn đoán contract.
- Thứ tự arm: case có index chẵn chạy 360 rồi 600, index lẻ chạy 600 rồi 360; pin schedule trước inference. Không retry/fallback.
- Chỉ đo: tỷ lệ chạm trần, tỷ lệ output lỗi/thiếu reason, cờ kết thúc câu, cờ chữ CJK, `done_reason`. **Không tính hoặc xem metric chọn bài** của bước này.
- Output lỗi/thiếu reason: lượt không qua schema/ID/telemetry (gồm `done_reason` khác `stop` hoặc hết `num_predict=512`), transport lỗi, hoặc reason rỗng.
- Quy tắc quyết định đã định trước: v3 dùng `maxLength=600` **chỉ khi** tỷ lệ chạm trần của arm 600 thấp hơn arm 360 **và** tỷ lệ output lỗi/thiếu reason của arm 600 không cao hơn arm 360. Ngược lại giữ 360. Nếu chạm trần không giảm, ghi là **chưa xác định được nguyên nhân** cắt câu, không kết luận giới hạn độ dài không phải yếu tố chính. Không thử mức thứ ba.

## Contract v3

- Model/runtime giữ như v2: `qwen2.5:1.5b`, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`, Ollama 0.35.1, temperature 0, `num_ctx=8192`, timeout 90 giây. Đổi runtime nghĩa là protocol mới, không bỏ qua mismatch.
- Giữ nguyên đầu vào metadata, enum, cách thay "prerequisite graph" và journal của v2.
- Thêm vào prompt riêng v3: trả lời **chỉ bằng tiếng Việt**, **tối đa 2 câu hoàn chỉnh**, chỉ nhắc số liệu có trong input.
- `maxLength` theo kết quả bước 1. Reason chạm trần vẫn tính là lựa chọn hợp lệ cho metric kỹ thuật nhưng bị gắn cờ.

## Bước 2 — Nhóm VALIDATION mới

- Nguồn: học sinh VALIDATION **chưa xuất hiện trong bất kỳ scenario RQ2 nào** trước đây (pilot 50, challenge 33, subset revision). Toàn bộ 750 học sinh đã qua coverage audit, nên gọi là "chưa chạy policy/Agent", không gọi là "chưa từng xem".
- Cohort đại diện: **40 học sinh**, chọn bằng seed `20261005`, cùng quy tắc prefix/cutoff, candidate generation và skill universe như pilot. Nếu không đủ 40 người đủ điều kiện thì dừng và báo, không nới tiêu chí.
- Challenge: chỉ thêm nếu còn học sinh mới thỏa **đúng** tiêu chí challenge cũ. Kiểm tra khả thi trước khi xem bất kỳ output nào; báo riêng, không gộp với đại diện.
- Thiết kế: 40 × 3 permutation × 2 graph variant = **240 study calls**. Cách sinh display/enum permutation giữ như v2.

## Bước 3 — Lặp request y hệt (báo riêng)

- Chọn bằng seed `20261007` 12 request trong 240 study calls, cân bằng 6 request mỗi graph variant.
- Gửi lại nguyên văn mỗi request thêm 3 lần: **36 calls bổ sung**, ghi scope `repeat` riêng trong journal.
- Metric: tỷ lệ request có cùng ID qua cả 4 lần gửi (lượt gốc + 3 lần lặp). Đây là **mức tham chiếu** cho biến động khi input giữ nguyên, không phải trần toán học. Báo cạnh ID-stable qua permutation; không dùng để quy nguyên nhân cho display, enum hay runtime.

Tổng batch đại diện: 4 context probes + 240 study + 36 repeat = **280 lượt gọi**. Con số này **chưa gồm** 48 lượt chẩn đoán contract ở bước 1 và mọi lượt challenge bổ sung (nếu khả thi); các phần đó có scope và báo cáo riêng.

## Cờ rationale (gắn cờ, không loại)

Áp dụng cho mọi lượt có reason. Giữ toàn bộ output. Tỷ lệ cờ dùng mẫu số **toàn bộ 240 study calls**; lượt lỗi hoặc thiếu reason được tính là có cờ ở mọi cờ có ngưỡng, để lỗi không làm tỷ lệ cờ trông tốt hơn.

| Cờ | Định nghĩa |
|---|---|
| `flag_cjk_ideograph` (có ngưỡng) | Có chữ trong dải U+4E00–U+9FFF, U+3400–U+4DBF hoặc U+F900–U+FAFF |
| `flag_cjk_punctuation` (mô tả) | Có ký tự trong dải U+3000–U+303F hoặc U+FF00–U+FFEF; báo riêng, không gộp vào cờ chữ |
| `flag_length_cap` (có ngưỡng) | Độ dài reason (số ký tự Unicode) bằng `maxLength` |
| `flag_no_terminal_punctuation` (có ngưỡng) | Ký tự cuối sau khi bỏ khoảng trắng không thuộc `.`, `!`, `?`, `…`. Không có cờ không đồng nghĩa câu đầy đủ |
| `flag_numeric_mismatch` (mô tả) | Tỷ lệ/mastery trong reason không khớp giá trị input nào của bài hoặc skill được nhắc, dung sai ±0,01 hoặc ±1 điểm phần trăm; problem ID, skill ID và support phải **khớp nguyên** |
| `flag_unknown_id` (mô tả) | Có chuỗi dạng ID không thuộc candidate set hoặc skill scope |

Các cờ là sàng lọc tự động để người đọc kiểm tra, không phải chấm ngữ nghĩa. Không có cờ chữ CJK không đồng nghĩa với tiếng Việt đúng. Cờ số có thể gắn nhầm khi model diễn đạt số theo cách khác, và bỏ sót trường hợp dùng đúng số nhưng gán sai ý nghĩa.

## Rubric rationale

- Rubric 0/1/2 bốn chiều như protocol v2 (nhất quán bằng chứng, liên quan lựa chọn, nhận biết giới hạn, dễ hiểu). Điểm một lượt = trung bình bốn chiều.
- Mẫu xác suất khóa trước: seed `20261006`, chọn ngẫu nhiên không hoàn lại **20 lượt hợp lệ mỗi graph variant** (tổng 40), không lọc theo cờ. Nếu một variant có ít hơn 20 lượt hợp lệ thì chấm toàn bộ lượt hợp lệ của variant đó.
- **Ước lượng điểm không điều kiện**, tính theo từng variant \(v\) rồi lấy trung bình với trọng số bằng nhau (mỗi variant có 120 study calls):
  \[
  \widehat{\mu}=\tfrac12\left(p_{\text{valid,có cạnh}}\,\bar{s}_{\text{có cạnh}}+p_{\text{valid,không cạnh}}\,\bar{s}_{\text{không cạnh}}\right)
  \]
  với \(p_{\text{valid},v}\) là tỷ lệ lượt hợp lệ trên 120 study calls của variant \(v\), \(\bar{s}_v\) là điểm trung bình mẫu đã chấm của variant đó. Lượt lỗi nhận điểm 0 thông qua \(p_{\text{valid},v}\).
- Độ bất định: bootstrap 1.000 vòng, seed 42, lấy lại theo học sinh trong từng variant trên mẫu đã chấm, giữ \(p_{\text{valid},v}\) quan sát. Báo khoảng 95% và ghi rõ khoảng này chỉ phản ánh biến động lấy mẫu rubric. Báo riêng điểm có điều kiện \(\bar{s}_v\) của từng variant.
- Variant không có lượt hợp lệ đóng góp 0; variant có lượt hợp lệ nhưng chưa có người chấm ghi chưa đánh giá. Điểm ngưỡng dùng ước lượng trung bình, không dùng cận CI làm ngưỡng mới.
- Ẩn danh model, xáo thứ tự bằng seed. Lý tưởng hai người chấm độc lập; báo đồng thuận và cách xử lý bất đồng. AI judge nếu có chỉ báo riêng, không thay người chấm.
- **Nếu không có người chấm, chiều rationale ghi "chưa đánh giá"**; Agent không thể được xếp là đạt toàn bộ tiêu chí.

## Tiêu chí vận hành đã định trước

Đây là yêu cầu vận hành của prototype trong nghiên cứu sinh viên, **chưa phải chuẩn sư phạm đã được xác nhận**. Tính riêng cohort đại diện; challenge nếu có chỉ báo mô tả.

| Chiều | Ngưỡng | Lý do |
|---|---|---|
| Kỹ thuật | ≥98% lựa chọn hợp lệ trên 240 study calls; runtime/hash đạt; không retry/fallback | Enum khiến kỳ vọng gần 100%; cho phép tối đa 4 lỗi được giải thích |
| Rationale | Trên 240 study calls: `flag_cjk_ideograph` ≤2% (≤4); `flag_length_cap` ≤1% (≤2); `flag_no_terminal_punctuation` ≤5% (≤12); ước lượng điểm không điều kiện \(\widehat{\mu}\) ≥1,5/2 | Lời giải thích phải đọc được bằng tiếng Việt và phần lớn đủ ý nếu đưa cho người dùng |
| Ổn định | **≥32/40 học sinh** ID-stable qua ba permutation **ở mỗi graph variant**. Mẫu số luôn là 40 học sinh đã lên lịch; triplet có bất kỳ lượt lỗi nào tính là **chưa ổn định** | Chấp nhận tối đa 20% học sinh nhận gợi ý khác chỉ vì đổi cách trình bày; tránh tính 80% chỉ trên triplet thành công. Chưa tách nguyên nhân display/enum/runtime |

Chỉ báo mô tả, không dùng làm ngưỡng: vị trí display/enum, hạng mastery, chọn skill đáy, agreement với B+, soft-remediation, độ nhạy graph theo cặp, latency, mức tham chiếu lặp request. Báo cạnh B+, random (kết quả và kỳ vọng giải tích) và always-first như v2.

## Quy tắc dừng

1. Sau batch v3 không sửa thêm prompt, model, contract hoặc nhóm học sinh.
2. Đạt cả ba chiều: Agent v3 được ghi là **đạt yêu cầu vận hành đã đặt**, không phải tốt hơn về sư phạm.
3. Không đạt bất kỳ chiều nào hoặc rationale "chưa đánh giá": giữ kết quả âm; Agent v3 vẫn là cấu hình được đánh giá trong thiết kế cuối, kết luận ghi rõ chưa đạt.
4. Trong cả hai trường hợp, Lock C chỉ được khóa khi đã hoàn tất thiết kế đánh giá TEST (scenario rules, metric, failure handling, CI, rubric/rater) và commit trước khi mở TEST một lần. Lock C là đóng băng thiết kế, không phải công nhận Agent tốt.

## Lưu trữ và giới hạn

Journal, schedule, raw response, per-student output và phiếu chấm chỉ lưu trong đường dẫn bị Git bỏ qua. Git chỉ lưu protocol, config, code, aggregate manifest và báo cáo tổng hợp. Metadata-only chỉ cho phép kết luận về hành vi chọn vận hành; không kết luận chất lượng sư phạm, nội dung bài hay learning gain.

## Việc cần làm trước khi chạy

- [x] Chốt seed: nhóm mới `20261005`, mẫu rubric `20261006`, request lặp `20261007`.
- [ ] Code entrypoint v3 mới; không sửa runner/artifact v2 đã pin.
- [ ] Kiểm thử: các cờ rationale (tách chữ/dấu câu CJK, dung sai số chỉ cho tỷ lệ/mastery), lượt lỗi tính có cờ trong mẫu số 240, quy tắc chọn contract gồm tỷ lệ lỗi, ước lượng \(\widehat{\mu}\) theo variant, ổn định với mẫu số 40 và triplet lỗi tính chưa ổn định, scope `repeat`, kiểm tra khả thi challenge, dừng khi runtime mismatch.
- [ ] Chạy bước 1, ghi kết quả chẩn đoán contract và áp quy tắc quyết định.
- [ ] Commit config v3 và protocol đã khóa **trước** batch chính.
