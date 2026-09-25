# Hướng dẫn chấm mù RQ2

Đây là phần đánh giá **chất lượng khuyến nghị trên tình huống đã ghi**, không đo tiến bộ học tập. Rubric gốc đã khóa trước TEST nằm ở `reports/rq2_rubric_lock_c.md`; tài liệu này chỉ hướng dẫn thao tác, không đổi tiêu chí.

## Chuẩn bị và bàn giao

Chạy `python scripts/prepare_rq2_human_review.py` từ thư mục dự án sau khi có hai người chấm độc lập. Script dùng đúng seed 43 để lấy 20/50 tình huống TEST, lấy **lượt Agent đầu tiên** của mỗi tình huống và không thay bằng lượt sau nếu không hợp lệ. Nó tạo `data/processed/rq2_human_review/rater_1.csv`, `rater_2.csv` và `sealed_key.json`. Thư mục này bị Git bỏ qua. Không gửi `sealed_key.json` cho người chấm và không commit bất kỳ phiếu đã điền hay dữ liệu theo từng tình huống nào.

Mỗi người chỉ nhận CSV của mình và rubric đã khóa. Hai người chấm độc lập, không trao đổi điểm trước khi nộp. Trên mỗi dòng, xem cùng `mastery_estimates`, `graph_edges_prototype`, `candidates` và bài `selected_problem_id`. Hai lựa chọn của một tình huống có cùng `case_code`, nhưng thứ tự dòng được trộn. Các mã kỹ năng/bài là mã dữ liệu; nếu người chấm không thể nhận biết nội dung thực của bài từ mã, cần ghi rõ hạn chế này trong `notes` và không suy diễn chất lượng nội dung bài. `difficulty_proxy` là tỷ lệ đúng trên TRAIN, không phải độ khó đã chuẩn hóa sư phạm. Các cạnh graph chỉ là giả định.

Điền ba cột `state_score_0_2`, `graph_score_0_2`, `difficulty_score_0_2` bằng số nguyên 0, 1 hoặc 2 theo rubric. Giữ nguyên các cột khác và mã dòng. Nếu không đủ căn cứ để chấm, để trống điểm đó và giải thích ở `notes`; không đoán. Gửi lại file riêng qua kênh an toàn cho nhóm nghiên cứu, không đưa vào Git. Chỉ sau khi nhận đủ hai phiếu mới mở `sealed_key.json` để ghép B+/Agent và tính chênh lệch cặp, tỷ lệ thiếu điểm, mức nhất trí giữa người chấm. Nếu không huy động đủ hai người, không công bố điểm rubric.

Sau khi đặt lại hai CSV đã chấm vào thư mục riêng, chạy `python scripts/summarize_rq2_human_review.py`. Script yêu cầu đúng mã dòng, điểm 0–2 hoặc bỏ trống, tính trung bình chênh lệch Agent trừ B+ trên các cặp đủ điểm và Cohen kappa có trọng số tuyến tính trên các lựa chọn đủ hai điểm. Kết quả `private_summary.json` vẫn ở thư mục bị Git bỏ qua. Kiểm tra định tính ghi chú bất đồng trước khi viết báo cáo công khai chỉ có số liệu tổng hợp.

## Rà soát graph

Dùng `reports/rq2_graph_review_template.csv` cho người hiểu học liệu. Với từng cạnh, ghi nguồn học liệu hoặc bằng chứng chuyên môn, quyết định `accept/reject/uncertain`, tên/vai trò người rà soát và ngày. Bảng này là biểu mẫu trống, **không phải** xác nhận graph. Nếu có cạnh cần sửa, lưu bản graph mới cho nghiên cứu tiếp theo; không sửa graph đã khóa rồi diễn giải lại TEST hiện tại.

## Diễn giải

Đánh giá mù có thể hỗ trợ nhận xét về độ hợp lý của khuyến nghị dưới các proxy và graph hiện có. Nó không phải thử nghiệm ngẫu nhiên với học sinh và không cho phép kết luận về learning gain hoặc hiệu quả nhân quả. Muốn kiểm tra tiến bộ học tập phải thiết kế một nghiên cứu triển khai mới với phép đo trước/sau và đồng ý tham gia phù hợp.
