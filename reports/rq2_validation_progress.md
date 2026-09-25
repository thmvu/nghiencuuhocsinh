# RQ2 — tiến độ trên validation

Đã dựng một pipeline phát triển RQ2 riêng, chưa mở TEST RQ2 và chưa có Configuration Lock C. Hai chính sách nhận cùng BKT latent-mastery state, cùng prerequisite graph và cùng candidate set. State là ước lượng của mô hình, không phải tri thức thật của sinh viên hay xác suất trả lời đúng.

## Dữ liệu và prototype

- 50 scenario được lấy cố định bằng seed 42 từ 50 sinh viên VALIDATION khác nhau, mỗi sinh viên một snapshot. BKT chỉ cập nhật bằng lịch sử đến cutoff; checkpoint được fit trên TRAIN và giữ nguyên.
- Graph gồm 20 kỹ năng phổ biến trong TRAIN và 5 cạnh tiên quyết. **Cả 5 cạnh hiện là giả định prototype**, chưa có xác nhận từ giáo viên hoặc nguồn học liệu. Vì vậy chưa thể suy diễn rằng graph phản ánh cấu trúc kiến thức thật.
- Pool có 5.328 cặp bài toán/kỹ năng đủ ít nhất 5 tương tác TRAIN. Mỗi scenario có 8 candidate thuộc 8 kỹ năng khác nhau; độ trải xác suất thành công TRAIN của candidate ít nhất 0,45. Đây là proxy độ khó từ TRAIN, không phải tham số độ khó chuẩn hóa.
- B+ chọn xác định theo kỹ năng tiên quyết yếu, độ vừa sức, remediation/progression, support và ID bài toán. Chưa đánh giá chất lượng sư phạm của lựa chọn.

Số liệu tổng hợp và graph ở `artifacts/tables/rq2_validation_summary.json` và `rq2_prototype_graph.json`. Scenario và kết quả từng sinh viên nằm trong `data/processed/rq2_validation_scenarios/`, bị Git bỏ qua.

## Local Agent feasibility và validation

Ollama 0.34.4 và `gemma3:1b` Q4_K_M đã chạy cục bộ trên NVIDIA RTX 3050 Laptop GPU (4 GiB VRAM, Ollama báo 100% GPU ở context 2048). Mô hình có mã `8648f39daa8f`. [Trang model chính thức](https://ollama.com/library/gemma3%3A1b) ghi bản tải 815 MB và Q4_K_M; [tài liệu structured outputs](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx) mô tả việc đưa JSON Schema vào trường `format` của API. Prompt yêu cầu chọn đúng một `problem_id` trong candidate set và nêu lý do ngắn; Pydantic kiểm tra output sau khi Ollama trả lời. Giao tiếp chỉ tới API loopback `127.0.0.1`.

Pilot 5 scenario **giả lập** đạt 5/5 schema-valid và 5/5 candidate-valid. Mean latency 17,25 giây bị chi phối bởi cold start 84,01 giây. RSS tiến trình Ollama được lấy mẫu giữa các lượt, không phải peak thật hay VRAM. Đây chỉ là kiểm tra khả thi, không đưa vào kết quả RQ2.

Lượt Agent đầu trên 50 scenario VALIDATION: 49/50 output đúng schema, 48/50 chọn candidate hợp lệ, median latency 0,95 giây, mean 1,08 giây, tối đa 6,11 giây. Có 1 output sai schema và 1 output đúng schema nhưng chọn ngoài candidate set. Chạy lại đúng cùng model, prompt và scenario để tách JSON cú pháp khỏi schema cho kết quả **49/50 JSON đúng cú pháp, 49/50 đúng schema, 48/50 candidate hợp lệ**; median latency 0,94 giây. Trong 48 scenario hợp lệ ở cả hai lượt, Agent chọn cùng một bài ở 48/48; hai scenario không hợp lệ vẫn không hợp lệ. Đây là quan sát ổn định trên VALIDATION, không phải 100 quan sát sinh viên độc lập. Agent trùng lựa chọn B+ ở 1/50 scenario; **mức trùng thấp không phải thước đo chất lượng**. Chưa có rubric độc lập hoặc đánh giá người chấm để nói chính sách nào tốt hơn. Không dùng VALIDATION này như kết quả TEST cuối.

Trước Lock C cần rà soát graph với nguồn học liệu hoặc người am hiểu chương trình học, thiết kế rubric độc lập với B+, chốt prompt/model/timeout/repair và giao thức repeated runs. Sau Lock C và Gate C mới tạo/đánh giá TEST scenarios; các lần lặp của cùng sinh viên phải giữ cùng cụm khi phân tích bất định.
