# RQ2 — kết quả TEST vận hành

Lock C đã được commit và push trước khi tạo scenario TEST. Một lượt đánh giá cuối dùng 50 sinh viên TEST khác nhau, một snapshot BKT theo prefix lịch sử mỗi sinh viên, cùng graph prototype và cùng 8 candidate cho B+ và Agent. Agent `gemma3:1b` chạy **3 lần mỗi scenario**, tổng cộng **150 lần gọi**. Ba lần của cùng sinh viên là các phép đo lặp, không phải 150 quan sát độc lập.

| Chỉ số đã khóa | Kết quả TEST |
|---|---:|
| JSON đúng cú pháp / đúng schema | 150/150 / 150/150 |
| Lựa chọn qua kiểm tra candidate/output | **147/150 (98,0%)** |
| CI 95% cho tỷ lệ trên, bootstrap 1.000 lần theo sinh viên | **94,0%–100,0%** |
| Cùng một lựa chọn hợp lệ cả 3 lượt | 49/50 sinh viên (98,0%) |
| Timeout | 0/150 |
| Output bị bộ xác thực từ chối | 3/150, cùng thuộc một scenario |
| Latency median / p95 / tối đa | 0,78 / 1,06 / 6,54 giây |
| Trùng lựa chọn B+ | 15/150 lượt gọi; chỉ mô tả sự khác nhau |

Tỷ lệ **147/150** là endpoint vận hành đã khóa: output phải đúng schema, lý do không rỗng và `problem_id` thuộc candidate set. Ba output bị từ chối sau khi JSON/schema đã đạt, không phải timeout. Nhật ký hiện lưu loại lỗi nhưng không lưu nguyên văn câu trả lời của ba trường hợp đó; do vậy báo cáo không chia nhỏ thêm nguyên nhân. CI lấy mẫu lại **50 cụm sinh viên**, giữ cả ba lượt của mỗi sinh viên trong cùng cụm. Tất cả 150 lượt được giữ trong mẫu số.

Kết quả này cho thấy Agent chạy được và phần lớn output tuân thủ giao thức trên máy hiện tại. **Nó không chứng minh Agent chọn bài tốt hơn B+ hoặc giúp sinh viên học tiến bộ hơn.** B+ luôn chọn từ candidate set theo định nghĩa, nên đối chiếu tỷ lệ hợp lệ không phải phép so sánh chất lượng. Mức trùng lựa chọn 15/150 cũng không xếp hạng hai chính sách. Năm cạnh tiên quyết của graph đều là giả định prototype chưa được xác nhận bằng học liệu/giáo viên; chưa có điểm rubric mù của hai người chấm. Latency là quan sát trên máy dùng NVIDIA RTX 3050 Laptop GPU và không đại diện cho môi trường triển khai khác.

Nguồn máy đọc được: `artifacts/tables/rq2_test_summary.json` (chỉ số tổng hợp) và `configs/protocol_c.json` (giao thức/phiên bản/hash đã khóa). Scenario, ID sinh viên và nhật ký từng lượt ở `data/processed/rq2_test_scenarios/`, bị Git bỏ qua. Kiểm toán độc lập xác nhận 24 hash của Lock C còn khớp, Lock C đã được push trước dấu mốc chạy TEST, và các chỉ số tổng hợp tính lại từ nhật ký riêng trùng khớp. Không điều chỉnh graph, policy, prompt hay model theo kết quả TEST.
