# RQ2 v2 — Agent chọn bài độc lập trên VALIDATION

Ngày 04/10/2026. Đã hoàn tất batch được khóa trước inference: 4 context probes + 144 study calls. RQ1 và split giữ nguyên; chưa Lock C hoặc TEST RQ2. Kết quả chứng minh tính hợp lệ vận hành, chưa cho thấy lựa chọn ổn định hoặc giá trị giáo dục của Agent.

## Thực thi và hậu kiểm

Ollama được khởi động nền trước inference; version 0.35.1 và Qwen2.5:1.5b digest khớp config. Context probes có/không cạnh lần lượt 1.777/1.554 prompt tokens, bằng nhau ở context 8.192 và 16.384. Cả 148 lần gọi đều nhận response; 144/144 study calls hợp lệ, không repair/retry/fallback. Kiểm tra identity trước/sau mỗi call và cuối batch đạt; request, response, source/input hashes, baseline replay và metric tái tính khớp.

Subset: 12 học sinh pilot, 12 challenge không trùng học sinh, ba permutation, hai graph variant. Mỗi ô 36 calls nhưng chỉ 12 học sinh. Các scenario đã được dùng trong phát triển trước đó; đây là nghiên cứu thăm dò, không phải holdout mới. Source/config/protocol của lượt chạy giữ nguyên sau inference. Raw responses, journal và per-student outputs nằm trong data ignored; chỉ aggregate và report lên Git.

## Đối chiếu baseline

Hạng mastery chuẩn hóa tính theo kỹ năng phân biệt: thấp hơn nghĩa là chọn skill có ước lượng mastery thấp hơn, không có nghĩa bài tốt hơn. ID-stable/skill-stable tính trên triplets đủ ba lượt; tất cả triplets đều đầy đủ trong batch này. Không có lượt phải loại vì candidate set chỉ có một skill.

| Cohort | Graph | Policy | Hợp lệ | ID/skill-stable | Hạng mastery TB | Chọn skill đáy | Chọn display đầu |
|---|---|---|---:|---:|---:|---:|---:|
| Pilot | Có cạnh | Agent | 36/36 | 2/12; 2/12 | 0,758 | 0/36 | 22,2% |
| Pilot | Không cạnh | Agent | 36/36 | 3/12; 3/12 | 0,754 | 0/36 | 19,4% |
| Pilot | Cả hai | B+ | 36/36 mỗi ô | 12/12; 12/12 | 0,583 | 0/36 | 13,9% |
| Pilot | Cả hai | Random | 36/36 mỗi ô | 1/12; 1/12 | 0,488 | 5/36 | 8,3% |
| Pilot | Cả hai | Always-first | 36/36 mỗi ô | 0/12; 0/12 | 0,444 | 5/36 | 100% |
| Challenge | Có cạnh | Agent | 36/36 | 2/12; 2/12 | 0,527 | 4/36 | 50,0% |
| Challenge | Không cạnh | Agent | 36/36 | 1/12; 1/12 | 0,549 | 3/36 | 44,4% |
| Challenge | Có cạnh | B+ | 36/36 | 12/12; 12/12 | 0,161 | 9/36 | 11,1% |
| Challenge | Không cạnh | B+ | 36/36 | 12/12; 12/12 | 0,772 | 0/36 | 8,3% |
| Challenge | Cả hai | Random | 36/36 mỗi ô | 1/12; 2/12 | 0,468 | 3/36 | 13,9% |
| Challenge | Cả hai | Always-first | 36/36 mỗi ô | 1/12; 1/12 | 0,397 | 7/36 | 100% |

Random kỳ vọng hạng là 0,500 ở pilot và khoảng 0,47 ở challenge; xác suất chọn skill đáy lần lượt 12,5% và khoảng 14,6%. Agent không thể hiện xu hướng chọn skill mastery thấp hơn random ở các ô này. Pilot không chọn skill đáy ở lượt nào. Đây là mô tả hành vi trên subset, không là kiểm định hoặc kết luận một recommendation cụ thể sai.

Agent và B+ có mục tiêu khác nhau: B+ ưu tiên nguồn yếu có liên kết đích yếu, rồi TRAIN success rate gần 0,7; Agent cân nhắc kỹ năng yếu và độ thử thách tự do. Không dùng một scalar rank hoặc agreement để kết luận hơn/kém sư phạm. Agent ID-stable chỉ 1–3/12 so với B+ 12/12, nên vẫn có phụ thuộc permutation. Random có những lần bốc khác nhau theo thiết kế, không nhận độ không ổn định của random là position bias.

Agent chọn enum đầu ở 5,6% cho cả hai ô pilot; challenge là 11,1% có cạnh và 16,7% không cạnh. Always-first chọn enum đầu 16,7%/19,4% ở pilot/challenge. Báo cạnh kỳ vọng uniform 12,5% trên tám ID và baseline cùng permutation; mẫu nhỏ chưa hỗ trợ kiểm định thiên lệch. Tỷ lệ display đầu 44–50% ở challenge cần giữ trong báo cáo, không nhận đã loại bỏ phụ thuộc vị trí.

## Graph và thời gian

Agent đổi ID giữa có/không cạnh ở 5/36 cặp pilot và 10/36 challenge. B+ lần lượt 0/36 và 36/36; random/always-first đều 0 theo thiết kế. Đây là phản ứng với thông tin cạnh trên cùng membership, không phải kiểm chứng graph hoặc so sánh toàn bộ hệ thống có/không graph. Challenge được chọn có điều kiện để có tín hiệu graph; không gộp hai cohort để suy rộng.

Agent latency trung bình từng ô khoảng 0,92–1,07 giây, bao gồm request/transport/runtime checks/validation. Baseline latency chỉ tính policy nội bộ, không đối chiếu trực tiếp như một benchmark cùng phạm vi. Runtime lượt Qwen cũ là 0.34.4, khác 0.35.1 hiện tại; không quy mọi khác biệt lịch sử cho prompt v2.

## Kết luận và bước tiếp theo

Tính hợp lệ đạt 144/144 và hậu kiểm đầy đủ. Các chỉ số ổn định, vị trí và mastery chưa chứng minh lợi ích của Agent chọn độc lập. Không promote model hoặc mở TEST. Reason vẫn `semantically_verified=false`, chưa được người chấm đọc theo rubric; số liệu này không đo chất lượng lời giải thích, đề bài hoặc learning gain.

Giữ nguyên batch và kết quả âm, không sweep thêm trên 24 học sinh này. Trước Lock C cần chốt vai trò và mục tiêu policy, rubric/rater và cách diễn giải; nếu thêm nhóm VALIDATION chưa chạy policy/Agent thì khóa seed và tiêu chí trước. Không gọi nhóm đó hoàn toàn chưa xem vì coverage đã kiểm tra 750 học sinh. Nếu mục tiêu vẫn là chọn bài có giá trị giáo dục, cần review graph và nội dung thực tế; metadata-only chưa trả lời mục tiêu đó.

Nguồn tái lập: `reports/rq2_selection_protocol_v2.md`, `configs/foundationalassist_v4_rq2_selection_v2.json`, `artifacts/tables/foundationalassist_v4_rq2_selection_v2_preparation.json`, `artifacts/tables/foundationalassist_v4_rq2_selection_v2_audit.json`. Hậu kiểm bằng `scripts/audit_foundational_rq2_selection_v2.py` không gọi model.
