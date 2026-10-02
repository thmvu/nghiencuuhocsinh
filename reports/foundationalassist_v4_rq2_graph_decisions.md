# Graph curriculum đề xuất cho RQ2 FoundationalASSIST v4

Ngày quyết định: 02/10/2026. Người dùng muốn tiếp tục project giáo dục riêng sau khi giảng viên đề nghị hướng doanh nghiệp. Graph do tác giả đề xuất với hỗ trợ AI, dùng cho VALIDATION development; chưa expert-validated, chưa Lock C, chưa TEST RQ2.

## Phạm vi và cách hiểu

Giữ 15 mã chuẩn/18 skill ID trong TRAIN inventory. Có 9 cạnh chuẩn, mở rộng thành 13 cạnh skill. Các chuẩn con `6.RP.A.3a–d` và `7.RP.A.2a–c` song song. CCSS mô tả nội dung chuẩn; hướng cạnh dưới đây là suy luận tác giả, không phải prerequisite mastery hoặc quan hệ nhân quả đã kiểm chứng. IM hỗ trợ một liên hệ ở chuẩn cha; chọn cặp chuẩn con vẫn là suy luận riêng.

Các skill ID trùng `node_code` giữ BKT state riêng, không gộp hay lấy trung bình. Mở rộng cạnh tạo liên kết metadata, không đặt điều kiện phải mastery tất cả các ID nguồn. B+ hiện ưu tiên kỹ năng nguồn yếu theo luật xếp hạng; chưa kiểm chứng readiness đầy đủ của mỗi đích. Cách diễn giải readiness cần khóa riêng nếu thêm sau này.

## Nguồn đọc ngày 02/10/2026

- S1: [CCSS lớp 6 Number System](https://www.thecorestandards.org/Math/Content/6/NS/).
- S2: [CCSS lớp 6 Ratios](https://www.thecorestandards.org/Math/Content/6/RP/).
- S3: [CCSS lớp 7 Ratios](https://www.thecorestandards.org/Math/Content/7/RP/).
- S4: [CCSS lớp 6 Equations](https://www.thecorestandards.org/Math/Content/6/EE/).
- S5: [CCSS lớp 7 Equations](https://www.thecorestandards.org/Math/Content/7/EE/).
- S6: [CCSS lớp 8 Equations](https://www.thecorestandards.org/Math/Content/8/EE/).
- S7: [IM lớp 7 Unit 2 Lesson 7](https://im.kendallhunt.com/MS/teachers/2/2/7/preparation.html): Building On `6.RP.A.3`, Addressing `7.RP.A.2`, không trực tiếp xác nhận cạnh chuẩn con.

Config lưu URL, tiêu đề, ngày đọc và nguồn từng cạnh. Chỉ diễn giải ý, không sao chép bài toán; license trang curriculum không tự xác định license từng problem.

## Cạnh đề xuất

| Nguồn → đích | Lý do diễn giải | Căn cứ |
|---|---|---|
| `6.NS.A.1 → 7.RP.A.1` | Chia phân số hỗ trợ unit rate với đại lượng phân số. | S1, S3; suy luận tác giả. |
| `6.RP.A.3b → 7.RP.A.1` | Unit rate mở rộng sang đại lượng phân số. | S2, S3; suy luận tác giả. |
| `6.RP.A.3a → 7.RP.A.2a` | Bảng tỉ số tương đương hỗ trợ nhận diện quan hệ tỉ lệ. | S2, S3, S7; IM ở chuẩn cha, cặp con do tác giả suy luận. |
| `6.RP.A.3b → 7.RP.A.2b` | Unit rate hỗ trợ nhận diện hằng số tỉ lệ. | S2, S3; suy luận tác giả. |
| `6.RP.A.3c → 7.RP.A.3` | Phần trăm cơ bản mở rộng sang bài nhiều bước. | S2, S3; suy luận tác giả. |
| `6.EE.B.5 → 6.EE.B.7` | Hiểu nghiệm/thế giá trị hỗ trợ giải phương trình. | S4; suy luận tác giả. |
| `6.EE.B.6 → 6.EE.B.7` | Biến biểu diễn đại lượng hỗ trợ viết phương trình. | S4; suy luận tác giả. |
| `6.EE.B.7 → 7.EE.B.4a` | Phương trình một phép toán mở rộng sang hai bước. | S4, S5; suy luận tác giả. |
| `7.EE.B.4a → 8.EE.C.7b` | Mở rộng sang phương trình cần khai triển và thu gọn. | S5, S6; suy luận tác giả. |

Không ép chia phân số thành prerequisite mọi chuẩn tỉ số; không nối chuẩn con thành chuỗi; không nối toàn nhóm tỉ số lớp 7 về toàn nhóm phương trình lớp 6. `6.RP.A.3d` và `7.RP.A.2c` tạm không có cạnh. Biểu diễn tỉ lệ bằng phương trình liên quan tới `6.EE.C.9` ngoài pilot, nên không nối tắt cho graph liên thông. Các prerequisite ngoài pilot là giới hạn, không có cạnh không chứng minh không có prerequisite.

## Kiểm tra và bước sau

Cập nhật sau review 02/10/2026: đã có compact graph, B+ v4 xét nguồn–đích và runner `scripts/prepare_foundational_rq2_validation.py`; xem `reports/foundationalassist_v4_rq2_review_response.md` để biết quy tắc nhiều ID, context budget và kết quả development. Agent chưa chạy thật; runtime token chưa xác minh. Graph không kích hoạt luật remediation trong 50 scenario hiện tại, nên chưa Lock C.

Chạy `.venv/Scripts/python.exe scripts/prepare_foundational_rq2_graph.py`: chỉ đọc TRAIN sau khi kiểm tra SHA-256 với Lock B v4. Artifact graph không chứa student ID, nhãn theo dòng hoặc text bài. Script `prepare_rq2_validation.py` cũ vẫn thuộc ASSIST09; runner v4 mới dùng tên riêng ở trên.

Metadata-only development có thể tiếp tục với graph giả định. Human review vẫn cần trước khi gọi graph là chuyên gia xác nhận hoặc đánh giá chất lượng nội dung sư phạm. Trên VALIDATION, so biến thể graph thưa và bỏ cạnh (cùng node, state, candidate membership và seed). Đây là độ nhạy đối với giả định, không xác nhận cạnh về giáo dục. Khóa biến thể/metrics trước TEST, không chọn graph bằng TEST; nếu giữ nhiều biến thể thì báo cáo tất cả.

## Prompt để đưa Astra phản biện

> Phản biện graph trong config và báo cáo này bằng nguồn curriculum chính chủ. Với từng cạnh, chọn accept as hypothesis, reject hoặc uncertain và nêu lý do. Phân biệt nội dung CCSS, thứ tự curriculum và prerequisite mastery; không tự nhận nguồn xác nhận cạnh. Kiểm tra chuẩn con song song, node cô lập và nguy cơ biến nhiều skill ID thành điều kiện AND. Đề xuất bỏ cạnh trước khi thêm; không đổi scope/split/RQ1 hay dùng TEST. Không cần raw data, student ID hoặc text bài.

Chưa phản biện Astra. Ý kiến AI không đổi `expert_validated=false`; không gửi tự động sang chat khác.
