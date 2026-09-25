# RQ2 rubric đã khóa trước TEST — đánh giá người chấm có điều kiện

Mục tiêu: chấm chất lượng khuyến nghị trong một scenario, không đo learning gain. Nếu huy động được **2 người chấm độc lập**, chọn cố định **20 trong 50 TEST scenarios** bằng seed 43; mỗi người chấm cả lựa chọn B+ và một lựa chọn Agent hợp lệ của cùng scenario, theo thứ tự trộn và ẩn tên hệ thống. Nếu Agent không có lựa chọn hợp lệ, ghi INVALID và không thay thế bằng lần chạy khác; báo cáo riêng tỷ lệ thiếu điểm và chỉ so sánh cặp có đủ hai lựa chọn. Không dùng điểm TEST để chỉnh graph, prompt, policy hay rubric.

Người chấm nhận cùng BKT state, graph prototype và candidate set, nhưng không thấy hệ thống tạo lựa chọn. Cần thông báo rõ BKT là ước lượng latent mastery và các cạnh graph là giả định chưa được chuyên gia xác nhận. Chấm ba tiêu chí **0–2 điểm** cho mỗi lựa chọn:

| Tiêu chí | 0 | 1 | 2 |
|---|---|---|---|
| Phù hợp với state | Mục tiêu mâu thuẫn rõ với mức mastery | Có lý do nhưng chưa chắc phù hợp | Mục tiêu phù hợp rõ với mức mastery và nhu cầu luyện tập |
| Phù hợp graph tiên quyết | Bỏ qua một tiên quyết yếu quan trọng mà không có lý do | Quan hệ tiên quyết chưa rõ | Khuyến nghị xử lý hoặc tôn trọng quan hệ trong graph |
| Độ khó và hướng luyện tập | Quá dễ/khó theo proxy TRAIN và state | Có thể chấp nhận nhưng chưa tối ưu | Độ khó hợp lý cho ôn tập hoặc tiến lên, có xét proxy TRAIN |

Mỗi người chấm làm độc lập. Báo cáo phân phối điểm từng tiêu chí, chênh lệch ghép cặp B+–Agent theo scenario, tỷ lệ không thể chấm và mức nhất trí giữa hai người chấm (weighted Cohen kappa cho từng tiêu chí). Không thay đổi điểm gốc sau thảo luận; nếu có phần trao đổi để diễn giải bất đồng, báo cáo riêng. Rationale của Agent có thể chấm riêng 0–2 (0 sai/bịa input, 1 chung chung, 2 nêu đúng bằng chứng từ input) nhưng **không cộng vào điểm so sánh B+–Agent** vì B+ chưa có rationale cùng định dạng.

Nếu không có hai người chấm độc lập, không tính điểm rubric và không tuyên bố Agent khuyến nghị tốt hơn về sư phạm. Báo cáo RQ2 khi đó chỉ có các chỉ số vận hành đã khóa: candidate validity (primary), JSON/schema validity, lỗi/timeout, latency và tính ổn định giữa ba lần chạy.
