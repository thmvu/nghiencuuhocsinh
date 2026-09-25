# Configuration Lock C — RQ2 operational TEST

Khóa ngày 2026-09-25, trước khi tạo hoặc đánh giá RQ2 TEST scenarios. Bản máy đọc được là `configs/protocol_c.json` (SHA-256 `294eaf588b1cfb3d4bde922ec5580c0392e693ea3e25d9da60e63c0d9f21f70d`). Mã nguồn cuối của evaluator đã push ở commit `20317ae`. Chưa có dấu mốc `data/processed/rq2_test_scenarios/evaluation_started.json` hoặc bảng `rq2_test_summary.json` lúc lập khóa.

## Lựa chọn đã đóng băng

- State: checkpoint BKT fit trên TRAIN từ Lock B; latent mastery sau khi cập nhật **chỉ** prefix lịch sử đến cutoff. Đây là ước lượng mô hình, không phải tri thức thật.
- Graph: 20 kỹ năng TRAIN, 5 cạnh đều là `prototype_assumption`. Chưa có bằng chứng chương trình học hoặc xác nhận giáo viên cho các cạnh. Candidate pool chỉ từ TRAIN, support tối thiểu 5; proxy độ khó là tỷ lệ thành công TRAIN. B+ và Agent nhận cùng state/graph/8 candidate, B+ xếp hạng xác định theo mã nguồn đã hash.
- TEST sampling: 50 sinh viên TEST khác nhau, mỗi sinh viên một snapshot; seed 42, prefix tối thiểu 5 tương tác, cutoff chọn nguyên đều trong khoảng được phép. Nếu thiếu 50 sinh viên đủ điều kiện thì dừng, không đổi quy tắc sau khi xem TEST.
- Agent: Ollama `0.34.4`, `gemma3:1b` digest `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc`, Q4_K_M, API loopback, temperature 0, context 2048, timeout 90 giây, không truyền seed, không repair, 3 lượt mỗi scenario. API `/api/tags` và `/api/version` phải khớp trước khi đọc TEST. Prompt và JSON schema đã hash riêng trong Lock C.
- Primary endpoint: tỷ lệ Agent chọn candidate hợp lệ trên **mọi 150 lượt gọi dự kiến**. Secondary: JSON cú pháp/schema, lỗi/timeout, latency, tỷ lệ cùng một lựa chọn hợp lệ cả 3 lượt. CI bootstrap theo **50 cụm sinh viên**, giữ 3 lượt của cùng sinh viên cùng nhau, 1.000 vòng seed 42. B+ luôn chọn trong candidate set theo định nghĩa; không diễn giải chênh lệch validity là ưu thế sư phạm. Mức trùng B+–Agent chỉ mô tả sự khác nhau.
- Rubric mù đã cố định ở `reports/rq2_rubric_lock_c.md` để sử dụng **nếu có hai người chấm độc lập**. Hiện chưa xác nhận người chấm, nên kết quả vận hành không đưa ra tuyên bố Agent chọn bài tốt hơn hay cải thiện học tập.

## Kiểm tra trước TEST

- [x] RQ2 validation development hoàn tất trên 50 sinh viên riêng; hai lượt cùng cấu hình có 48/48 lựa chọn hợp lệ trùng nhau ở các scenario hợp lệ ở cả hai lượt. Đây là thông tin phát triển, không phải kết quả TEST.
- [x] Split, TRAIN/VALIDATION/TEST parquet, BKT checkpoint, graph, candidate pool, config phát triển, rubric, requirements và 9 tệp mã RQ2 khớp 24 SHA-256 trong Lock C. TEST parquet chỉ được hash, không đọc hàng/nhãn cho RQ2.
- [x] Phiên bản Ollama, digest model và quantization cài trên máy khớp Lock C; prompt/schema hash được kiểm tra trong preflight.
- [x] 100/100 kiểm thử tích hợp đạt; `pip check` không có xung đột.
- [x] Output theo sinh viên/lượt gọi nằm ở `data/processed/` bị Git bỏ qua; chỉ báo cáo tổng hợp được đưa vào Git.
- [x] Không có dấu mốc chạy TEST RQ2 hoặc kết quả TEST RQ2 trước khóa này.

**Gate C: RQ2 VALIDATION DEVELOPMENT COMPLETE + CONFIGURATION LOCK C COMPLETE + RQ2 PRE-TEST CHECKLIST PASS.** Mã đánh giá phải kiểm tra Lock C và runtime trước khi đọc hàng TEST, tạo dấu mốc một lần, rồi báo cáo nguyên kết quả kể cả lỗi/invalid. Giới hạn graph prototype và thiếu người chấm vẫn áp dụng sau Gate C.
