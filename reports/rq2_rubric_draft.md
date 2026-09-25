# RQ2 rubric dự thảo — chưa khóa C

Mục đích là đánh giá **chất lượng khuyến nghị trong scenario**, không đo learning gain. Rubric này được soạn từ VALIDATION và phải được chốt trước khi xem output TEST RQ2. Cạnh graph hiện là giả định prototype; người chấm phải được thông báo điều này và không coi nó là kiến thức chuẩn đã xác nhận.

Mỗi phiếu đưa cùng state BKT, graph, 8 candidate và một lựa chọn đã ẩn tên hệ thống. Hai người chấm (nếu huy động được) chấm độc lập, không thấy lựa chọn của hệ thống kia hoặc thống kê TEST. Mỗi tiêu chí 0–2 điểm:

| Tiêu chí | 0 | 1 | 2 |
|---|---|---|---|
| Phù hợp với state | Mục tiêu mâu thuẫn rõ với mức mastery | Có lý do nhưng chưa chắc phù hợp | Mục tiêu phù hợp rõ với mức mastery và nhu cầu luyện tập |
| Phù hợp cấu trúc tiên quyết | Bỏ qua một tiên quyết yếu quan trọng mà không có lý do | Quan hệ tiên quyết chưa rõ | Khuyến nghị xử lý hoặc tôn trọng quan hệ tiên quyết trong graph |
| Độ khó và hướng luyện tập | Quá dễ/khó theo proxy TRAIN và state | Có thể chấp nhận nhưng chưa tối ưu | Độ khó hợp lý cho ôn tập hoặc tiến lên, có xét proxy TRAIN |

Nếu đánh giá lý do của Agent, dùng tiêu chí riêng 0–2: **0** sai hoặc bịa thông tin không có trong input; **1** có phần đúng nhưng chung chung; **2** nêu chính xác state/graph/candidate liên quan. Không cộng tiêu chí lý do vào điểm so sánh B+–Agent trừ khi B+ cũng có lời giải thích theo giao thức khóa trước TEST.

Báo cáo số người chấm, số scenario, phân phối điểm từng tiêu chí và mức nhất trí giữa người chấm. Giữ các lần chạy lặp và mọi snapshot của cùng sinh viên trong cùng cụm khi tính bất định. Không dùng điểm từ TEST để sửa prompt, graph, B+ hoặc rubric.
