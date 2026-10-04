# Tự rà soát lựa chọn và lời giải thích RQ2 v3

Ngày 04/10/2026. Giao diện local cho tác giả tự đánh giá, không phải expert review hoặc chấm mù giữa các model. Bạn đã biết model/kết quả tổng hợp; chỉ ẩn lựa chọn và reason từng phiếu trong bước chọn. Không mở TEST, không thay protocol/config/run v3 đã khóa.

## Mở giao diện

Từ thư mục project trong PowerShell:

```powershell
.\scripts\start_rq2_review_ui.ps1
```

Hoặc chạy trực tiếp, giữ terminal mở:

```powershell
.venv\Scripts\python.exe scripts/run_foundational_rq2_review_ui.py
```

Mở `http://127.0.0.1:9411`. Không cần Ollama, GPU hoặc thêm package; không gọi API AI. Chỉ bind loopback, không public server. Script mở nhanh dùng cửa sổ nền và trình duyệt mặc định, không đổi execution policy.

## Hai bước

1. Nhập tên/bí danh. 40 phiếu giữ đúng mẫu đã chọn bằng seed trong v3, không bỏ phiếu có cờ. Đọc mastery BKT, TRAIN success rate, support và graph, chọn một bài bạn cho hợp lý hoặc ghi không đủ căn cứ; luôn ghi lý do. Hoàn tất toàn bộ 40 lựa chọn trước khi mở kết quả Agent. Có thể sửa lựa chọn trong bước này.
2. Bấm bắt đầu chấm: khóa toàn bộ lựa chọn bước 1. Đọc nguyên văn reason và bài Agent chọn, chấm bốn chiều 0/1/2 hoặc "không đánh giá được", kèm nhận xét. Điểm không được tự điền; có thể sửa điểm, mỗi lần lưu có version/thời gian/lịch sử. Tải lại giao diện tiếp tục phiếu chưa làm; thay đổi chưa lưu có cảnh báo.

Bốn chiều theo rubric v2/v3: nhất quán bằng chứng; liên quan lựa chọn; nhận biết giới hạn; dễ hiểu. 0 = sai/thiếu nghiêm trọng, 1 = một phần/mơ hồ, 2 = đầy đủ theo input. Nếu không hiểu tiếng Trung, không đoán điểm đúng/sai bằng chứng: ghi không đánh giá được ở chiều chưa đánh giá được và mô tả hạn chế. Giao diện không tự dịch reason. "Không đánh giá được" giữ null, không biến thành 0 hay điểm đạt. Khi chưa đủ 40 phiếu với bốn điểm số, không tính điểm rubric đầy đủ theo protocol.

Phần tiến độ phân biệt số phiếu đã đọc với số phiếu đủ cả bốn điểm. Khi đủ, dùng estimator và bootstrap đã khóa trong v3, lưu rõ provenance tác giả tự chấm. Điểm tự chấm không tự thay kết quả frozen manifest, không làm Agent đạt các chiều ổn định/ngôn ngữ đã thất bại, không khóa Lock C. Trùng lựa chọn của bạn chỉ là mô tả, không phải correctness/gold label; bạn không phải chọn bài thay Agent ở mọi lượt vận hành.

## Giới hạn của nội dung hiển thị

Không có question text, đáp án, current/future outcome hoặc ID học sinh. Số liệu là metadata/state của input gốc; không suy ra đây là chẩn đoán chắc chắn. Một kỹ năng chưa được quan sát có thể dùng BKT prior; phiếu hiện không kèm support riêng theo kỹ năng của học sinh. Support trong bảng là số tương tác TRAIN của bài. TRAIN success rate cao hơn nghĩa là dễ hơn với nhóm TRAIN, không phải xác suất đúng cá nhân.

Nhãn kỹ năng tiếng Việt là diễn giải ngắn các mã CCSS, bổ sung cho người đọc, không được nạp ngược vào prompt hay sửa snapshot. Nó không xác nhận một problem thực sự có nội dung đúng như chuẩn. Nguồn diễn giải: [6.NS](https://www.thecorestandards.org/Math/Content/6/NS/), [6.RP](https://www.thecorestandards.org/Math/Content/6/RP/), [6.EE](https://www.thecorestandards.org/Math/Content/6/EE/), [7.RP](https://www.thecorestandards.org/Math/Content/7/RP/), [7.EE](https://www.thecorestandards.org/Math/Content/7/EE/), [8.EE](https://www.thecorestandards.org/Math/Content/8/EE/), truy cập 04/10/2026. Các ID cùng chuẩn vẫn có state riêng.

Chỉ đánh giá lựa chọn và lời giải thích trên metadata. Muốn đánh giá sư phạm cần nội dung bài đã review cùng người có chuyên môn; không thể dùng giao diện này xác nhận learning gain hay graph chuẩn.

## Lưu trữ và kiểm tra

Điểm, lựa chọn, ghi chú, người chấm và lịch sử được lưu vào `data/processed/foundationalassist_v4/rq2_validation/selection_v3/author_review/reviews.json`, bị Git bỏ qua. Ghi file bằng replace sau flush/fsync; lỗi ổ đĩa không báo lưu thành công hoặc đổi state trong bộ nhớ. Version chống ghi đè từ hai cửa sổ; phiên người chấm được khóa theo bí danh. Source packet/runs chỉ đọc và đối chiếu hash/audit trước khi mở; server không cung cấp đường dẫn file tùy ý. Không gửi dữ liệu lên model lớn hoặc xuất dữ liệu training.

Đã kiểm thử 208 tests tích hợp, gồm 8 tests mới về ẩn lựa chọn cả batch, khóa sau reveal, điểm thiếu, resume/provenance, phiên bản cũ, ghi lỗi, ID ngoài danh sách và HTTP origin/token/path. Browser QA dùng hai phiếu synthetic riêng tại port9412: chọn, reveal, rubric, summary và reload đạt; phiếu thật40 chưa được ghi điểm thử. Bố cục desktop/hẹp kiểm tra được, bảng cuộn nội bộ. Hậu kiểm v3 vẫn đạt, không model calls mới.
