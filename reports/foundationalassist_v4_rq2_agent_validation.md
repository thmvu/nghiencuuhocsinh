# Kết quả Agent thật trên VALIDATION FoundationalASSIST v4

Ngày 02/10/2026. Hoàn tất hai lượt development local; chưa Lock C và chưa mở TEST RQ2. RQ1 không train lại. Đây là đánh giá vận hành metadata-only, không phải chất lượng sư phạm hoặc learning gain.

## Runtime và phạm vi

- Ollama 0.34.4, model `gemma3:1b`, digest `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`.
- Config `foundationalassist-v4-rq2-validation-draft-2`: temperature 0, context 8.192, output reserve 256, timeout 90 giây, không repair/retry.
- 50 học sinh pilot × 3 permutation × 2 graph variant = 300 study calls; 33 học sinh challenge × 3 × 2 = 198 study calls. Thêm 8 chat calls để probe context, **không tính vào 498 study calls**.
- Hai cohort có 2 học sinh trùng nhau; không gộp thành 83 học sinh độc lập hoặc gộp tỷ lệ/CI. Challenge được thiết kế sau coverage audit, không đại diện cho toàn bộ học sinh.
- State chỉ từ prefix VALIDATION; model và metadata bài từ TRAIN. Cùng state, candidate membership và order cho mọi policy trong một repetition. `no_edges` bỏ cạnh khỏi input, không thay candidate set hoặc nhãn tham chiếu khi chấm.

Preflight gửi cùng prompt ở context 8.192 và 16.384: pilot có/không cạnh 1.727/1.504 token; challenge 1.726/1.503 token. Số đếm ở hai context bằng nhau. Token tối đa được lưu trong study calls không vượt những mốc này. Các response probe không vào bảng metric.

## Kết quả Agent

Tỷ lệ hợp lệ, agreement và soft-remediation có mẫu số gồm cả lượt lỗi, aggregate mỗi học sinh trọng số bằng nhau. First-position rate dưới đây là tỷ lệ trên **các lượt hợp lệ**, nêu rõ mẫu số. Đổi lựa chọn khi xáo chỉ tính học sinh có cả 3 lượt hợp lệ trong variant tương ứng.

| Cohort / graph | Lượt hợp lệ | Đúng schema | Chọn vị trí đầu trong lượt hợp lệ | Học sinh đổi ID khi xáo | Agreement với B+ | Latency trung bình |
|---|---:|---:|---:|---:|---:|---:|
| Pilot / có cạnh | 142/150 (94,67%) | 150/150 | 134/142 (94,37%) | 43/44 (97,73%) | 10,00% | 1,09 s |
| Pilot / không cạnh | 145/150 (96,67%) | 149/150 | 121/145 (83,45%) | 44/45 (97,78%) | 9,33% | 1,14 s |
| Challenge / có cạnh | 95/99 (95,96%) | 98/99 | 93/95 (97,89%) | 29/29 (100%) | 11,11% | 1,09 s |
| Challenge / không cạnh | 98/99 (98,99%) | 98/99 | 83/98 (84,69%) | 31/32 (96,88%) | 9,09% | 1,10 s |

Pilot tổng 287/300 hợp lệ, challenge 193/198. Lỗi vẫn nằm trong study records: pilot 13 `ValueError`; challenge 4 `ValueError` và 1 `HTTPError`. Không sửa đáp án, repair hoặc gọi lại để thay lượt lỗi.

Runner lưu flag schema/validity nhưng chưa lưu raw response/reason hoặc thông điệp lỗi chi tiết. Có 12 lượt pilot và 3 lượt challenge qua schema rồi bị validation tiếp theo từ chối. Validation tiếp theo gồm reason không rỗng và membership; vì log chỉ ghi loại lỗi, **không thể kết luận tất cả đều là chọn ID ngoài danh sách**, hoặc tách chính xác mọi nguyên nhân. Với lượt `HTTPError`, không có status/body được lưu trong study record. Đây là giới hạn audit cần cải thiện trong phiên bản development tiếp theo; không suy đoán nguyên nhân.

## So với baseline và độ nhạy graph

Tất cả 3 baseline deterministic/random chọn candidate hợp lệ. B+ ổn định qua permutation trong cả hai cohort; always-first và random thay đổi nhiều, trong đó random dùng draw khác nhau nên không diễn giải variation là position bias.

| Chỉ số | Pilot | Challenge |
|---|---:|---:|
| B+ đổi lựa chọn có/không cạnh | 0% | 87,88% (29/33 học sinh) |
| Agent đổi lựa chọn có/không cạnh, trung bình theo học sinh trên các cặp hợp lệ | 17,33% | 14,14% |
| Cặp Agent hợp lệ / tổng cặp | 138/150 | 94/99 |
| Học sinh còn ít nhất một cặp hợp lệ | 50 | 33 |
| Agent chọn soft-remediation có cạnh, theo graph tham chiếu chung | 0% | 18,18% |
| Agent chọn soft-remediation không cạnh, cùng nhãn tham chiếu | 0% | 17,17% |
| Random chọn soft-remediation, có hoặc không cạnh | 0% | 21,21% |
| Always-first chọn soft-remediation, có hoặc không cạnh | 0% | 19,19% |

Không có nhãn sư phạm độc lập: agreement với B+ chỉ đo giống policy, còn soft-remediation chỉ đo theo giả định graph tác giả. Prompt hiện tại nêu chọn bài từ các tín hiệu và semantics của cạnh, nhưng không bắt Agent tái tạo toàn bộ ranking B+; agreement thấp không tự chứng minh recommendation sai.

Tuy nhiên, tỷ lệ chọn bài đầu rất cao và thay đổi khi xáo cho thấy **cấu hình model/prompt hiện tại phụ thuộc mạnh vào thứ tự trình bày**. Trong challenge, Agent không thể hiện tỷ lệ soft-remediation cao hơn random hoặc always-first về mặt số mô tả. Chưa thực hiện kiểm định để gọi đây là khác biệt có ý nghĩa thống kê. Không có bằng chứng từ lượt development này rằng thêm Agent mang lại ưu thế so với B+.

Agent có thể đổi lựa chọn khi thêm cạnh ngay cả trong pilot không kích hoạt luật B+. Vì vậy graph sensitivity không tự chứng minh hiểu prerequisite; có thể là phản ứng với thay đổi prompt. Không suy ra động cơ từ selection khi reason chưa được giữ để audit.

## Hậu kiểm và artifact

`scripts/audit_foundational_rq2_agent_runs.py` chạy đọc-chỉ, không gọi model: xác nhận đủ calls, học sinh/scenario/permutation đúng, mọi lựa chọn được chấp nhận thuộc candidate set và đúng vị trí, agreement và soft-remediation khớp graph tham chiếu chung, public metric tính lại khớp private records. Hash checkpoint/code/TRAIN/VALIDATION/manifest/config/scenarios không đổi; runtime version và model digest sau chạy khớp preflight.

- Public summary: `artifacts/tables/foundationalassist_v4_rq2_validation_summary.json` và `artifacts/tables/foundationalassist_v4_rq2_challenge_summary.json`.
- Public audit: `artifacts/tables/foundationalassist_v4_rq2_agent_audit.json`; chỉ số tổng hợp và hash, không chứa student ID hoặc response từng lượt.
- Private calls, scenarios, checkpoint từng call và probe ở `data/processed/foundationalassist_v4/rq2_validation/`, nhóm challenge trong subfolder riêng, đều bị Git bỏ qua.
- 145 kiểm thử tích hợp đạt trước lượt study. Hậu kiểm trên dữ liệu thật đã đạt sau lượt study; không điều chỉnh policy/model/config giữa hai cohort.

## Trước Lock C

Chốt giữ cấu hình này để báo cáo kết quả âm, hoặc phát triển phiên bản mới có mục tiêu chọn bài rõ hơn và log nguyên nhân lỗi/raw response trong thư mục private. Nếu phát triển mới, giữ riêng config/hash/artifact phiên bản hiện tại, chỉ dùng VALIDATION và không thay thế lượt lỗi bằng kết quả tốt hơn. Không tăng độ phức tạp chỉ để thắng B+.

Chưa khóa Lock C hoặc mở TEST. Chưa expert-validate graph, chưa xét chất lượng nội dung hoặc learning gain.
