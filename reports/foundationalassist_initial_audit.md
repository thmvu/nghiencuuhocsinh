# FoundationalASSIST: xác minh dữ liệu trước protocol mới

Notebook đã chạy: `notebooks/01_foundationalassist_audit.ipynb`. Thống kê tổng hợp: `artifacts/tables/foundationalassist_initial_audit.json`. Raw tại `adaptive-learning-nckh/data/raw/FoundationalASSIST/Data/` được đọc nguyên văn bằng `dtype=str, keep_default_na=False`, không sửa hoặc ghi đè. Không train, không tạo split và chưa khóa preprocessing.

## Phạm vi

FoundationalASSIST là dataset chính duy nhất cho workload mới. ASSIST09 chỉ là fallback, không chạy thêm trừ khi FoundationalASSIST có vấn đề nghiêm trọng. Repo thực tế đã có kết quả RQ1 TEST và RQ2 TEST vận hành trên ASSIST09; giữ các báo cáo/checkpoint/lock cũ như lịch sử, không gọi đó là kết quả của FoundationalASSIST. V3 và các lock A/B/C cũ chưa được áp dụng cho bộ mới.

## Kết quả xác minh

| Kiểm tra | Kết quả |
|---|---:|
| Interactions raw | 1.753.384 × 9 |
| Problems raw | 3.395 × 10 |
| Skills raw | 3.797 × 4 |
| Lặp cả 9 cột raw | 0 |
| Lặp cả interaction `id` và 7 trường nghiệp vụ, chỉ bỏ `Unnamed: 0` | 31.441 |
| Interaction ID có dữ liệu nghiệp vụ mâu thuẫn | 0 |
| Lặp nếu chỉ xét 7 trường nghiệp vụ, bỏ qua ID | 31.443 |
| Nhóm có cùng 7 trường nhưng khác interaction ID | 2 |
| Số dòng duy nhất theo ID + nghiệp vụ trong phép đếm chẩn đoán | 1.721.943 |
| Chênh so với con số 1.722.169 của README | 226 |
| `discrete_score` trống thật trong raw | 8.952 |
| Nhãn không trống nhưng không phải số / nhãn số ngoài 0–1 | 0 / 0 |
| Thời gian trống sau phép đếm loại lặp chẩn đoán | 3.390 |
| Thời gian không trống nhưng parse thất bại | 0 |
| Trùng thời gian hợp lệ trong cùng học sinh sau loại lặp chẩn đoán | 0 |
| Mã bài tương tác thiếu Problems / Skills | 0 / 0 |
| Dòng Problems lặp hoàn toàn / mã bài mâu thuẫn metadata | 26 / 1 |
| Bài có nhiều skill | 355 |
| Skill ID / node code duy nhất | 224 / 164 |
| Dòng Problems chứa `<img` | 835 |

Bảy trường kiểm tra là `user_id`, `problem_id`, `end_time`, `discrete_score`, `answer_text`, `hint_count`, `saw_answer`. File thực tế dùng `user_id`, dù README mô tả `user_xid`. Kiểm tra giữ nguyên chuỗi nên không gộp nhầm câu trả lời như `NA` với ô trống do cách parse missing mặc định.

31.441 dòng là bằng chứng mạnh về trùng kỹ thuật vì cả interaction ID và nội dung nghiệp vụ đều giống nhau. Tuy nhiên đây mới là kiểm toán; quy tắc preprocessing chưa được chốt. Hai nhóm khác ID phải giữ nguyên trong bước này. Chênh lệch 226 với README không chứng minh file tải thiếu; chưa biết nguyên nhân và không bù/xóa dòng để làm khớp số mô tả.

## Nguồn và tái lập

Metadata Hugging Face cục bộ cho cả ba file ghi revision `82b29188dffd2fd6bd3abc5a3de0db1ef1df12b9`. SHA-256 Interactions là `671e97d320d0cf9b7e2bd75830d531cfbd95d307a1a9a590531934ad0d3d8ba4`, khớp ETag 64 ký tự trong metadata tải. SHA-256 từng file được lưu trong JSON. Đây là kiểm tra file với metadata cục bộ, chưa phải đối chiếu độc lập với remote. README đi kèm có cảnh báo lỗi LFS ngày 19/3 và vẫn ghi 1.722.169 interactions.

## Điều kiện trước khi viết và khóa protocol v4

- Ghi rõ quy tắc loại bản sao cùng ID, xử lý missing label/time và metadata bài mâu thuẫn; không coi interaction ID là thứ tự thời gian khi chưa có căn cứ.
- Quyết định cách xử lý nhiều kỹ năng và skill ID cùng node code, tránh nhân bản một tương tác làm tăng trọng số khi join Skills.
- Skills là mapping, không chứa cạnh prerequisite. RQ2 cần nguồn curriculum hoặc ghi rõ giả định riêng.
- `has_image` là cờ sàng lọc, không phải chứng nhận text-complete. Bài không có ảnh vẫn có thể phụ thuộc biểu đồ, markup hoặc nội dung liên quan; cần rà soát trước khi vào RQ2.
- Dự đoán `discrete_score[t]` không được dùng `answer_text[t]`, `hint_count[t]`, `saw_answer[t]`. Phân biệt nhãn hoàn thành độc lập theo ASSISTments với mức thông thạo thật.
- Các thống kê lần này phục vụ kiểm tra toàn vẹn raw. Sau khi khóa split mới, mọi thống kê dùng để fit đặc trưng/policy phải tính đúng trên TRAIN, tuning trên VALIDATION và giữ TEST riêng.
