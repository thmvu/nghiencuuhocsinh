# Hướng dẫn chấm 40 tình huống gợi ý bài

Cập nhật giao diện ngày 09/10/2026 để dễ đọc. Đây vẫn là 40 tình huống đã chọn trước đó, với cùng số liệu, thứ tự bài và lời giải thích gốc. Thay đổi cách viết hướng dẫn không tạo lại thí nghiệm hoặc xóa điểm đã lưu.

## Mở để bắt đầu

Chạy trong thư mục project:

```powershell
.\scripts\start_rq2_review_ui.ps1
```

Mở http://127.0.0.1:9411. Nhập tên hoặc bí danh để lưu nhận xét. Điểm chỉ lưu trên máy; giao diện không gọi AI.

## Bước 1: bạn chọn bài

Mỗi tình huống có 8 bài. Bạn chưa xem AI chọn gì. Đọc tên kỹ năng và ba cột:

| Cột | Hiểu như thế nào? |
|---|---|
| Mức nắm vững ước tính | Hệ thống ước tính học sinh đã hiểu kỹ năng đến đâu. Số thấp gợi ý học sinh còn cần luyện; đây là ước tính có thể sai. |
| Tỷ lệ làm đúng của nhóm tham khảo | Ví dụ 80% nghĩa là khoảng 80 trong 100 lượt của nhóm tham khảo được ghi nhận đúng. Số cao thường gợi ý bài dễ hơn với nhóm đó; chưa biết học sinh này làm đúng được không. |
| Số lượt làm bài tham khảo | Số lượt được dùng để tính tỷ lệ làm đúng. Không phải số lần học sinh này đã làm bài. |

Mã bài chỉ giúp nhận biết bài bạn chọn. Mã kỹ năng và mã chương trình giúp đối chiếu; bạn không cần nhớ chúng. Tên kỹ năng là diễn giải ngắn để dễ hình dung, chưa xác nhận nội dung của từng bài.

Bạn có thể cân nhắc kỹ năng cần luyện và độ vừa sức, nhưng không có quy tắc bắt buộc chọn số thấp nhất hay bài dễ nhất. Phiếu chưa cung cấp đề bài, đáp án hoặc số lần học sinh đã luyện từng kỹ năng. Nếu chưa đủ thông tin, chọn **Không đủ căn cứ để chọn một bài** và nói bạn còn thiếu gì.

Nếu mở phần gợi ý thứ tự học, mũi tên A → B có nghĩa người làm nghiên cứu đề xuất cân nhắc học A trước B. Các gợi ý này chưa có giáo viên toán xác nhận; bạn có thể không đồng ý hoặc chưa chắc.

Ghi lý do của bạn, rồi bấm **Lưu và sang phiếu tiếp**. Bạn có thể sửa lựa chọn cho đến khi hoàn tất cả 40 tình huống và mở bước 2.

## Bước 2: bạn nhận xét lời giải thích của AI

Bấm **Bắt đầu chấm lời giải thích** sau khi làm xong bước 1. Lựa chọn riêng của bạn được giữ lại. Đọc bài AI chọn và lời giải thích gốc, rồi trả lời bốn câu hỏi:

1. **AI có dùng đúng thông tin không?** So mã bài, kỹ năng và con số với bảng.
2. **AI có giải thích vì sao chọn bài này không?** Lý do có gắn với bài được chọn và tình trạng học sinh không?
3. **AI có nói quá chắc chắn không?** Điểm cao nghĩa là biết thận trọng, nhận ra thông tin chỉ là ước tính hoặc còn hạn chế.
4. **Bạn có hiểu lời giải thích không?** Có đọc được và hiểu AI đang cân nhắc gì không?

Mỗi câu có hướng dẫn riêng trên màn hình. Nhìn chung: **0** là sai hoặc thiếu rõ; **1** là đúng một phần hoặc còn mơ hồ; **2** là đáp ứng đầy đủ theo thông tin có trong phiếu.

Nếu không đọc được ngôn ngữ của lời giải thích, chọn **Không đánh giá được** ở các câu về độ đúng, lý do chọn và mức thận trọng; đừng đoán. Bạn vẫn có thể cho điểm về việc lời giải thích có dễ hiểu với mình không. “Không đánh giá được” không được đổi thành điểm 0.

Ghi một nhận xét ngắn để giải thích điểm. Điểm không được tự điền. Có thể sửa điểm; mỗi lần lưu đều có lịch sử. Mở lại trang để tiếp tục tình huống chưa làm.

## Hiểu kết quả đúng mức

Bạn và AI chọn giống nhau chưa có nghĩa bài đó chắc chắn giúp học sinh tiến bộ. Đây là nhận xét của người làm nghiên cứu, chưa phải đánh giá của giáo viên toán độc lập. Phiếu chỉ có tên kỹ năng và số liệu, nên chưa thể chấm đầy đủ chất lượng dạy học của bài.

Phần tiến độ phân biệt tình huống đã nhận xét với tình huống có đủ cả bốn điểm. Khi chưa chấm được đầy đủ, hệ thống chưa đưa ra điểm tổng hợp đầy đủ.

Điểm lưu ở `data/processed/foundationalassist_v4/rq2_validation/selection_v3/author_review/reviews.json`, không đưa lên Git. Giao diện giữ cơ chế lưu và tính điểm đã có; kết quả thí nghiệm được lưu riêng.
