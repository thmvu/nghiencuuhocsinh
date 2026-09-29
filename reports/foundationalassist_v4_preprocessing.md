# FoundationalASSIST v4 — cleaning và split

Đã chạy preprocessing trên snapshot đã audit, không train và không tính model metrics trên TEST. Raw không thay đổi. Lock ở `configs/foundationalassist_v4_preprocessing.json`.

| Bước | Còn lại | Loại tại bước này |
|---|---:|---:|
| Raw | 1.753.384 | 0 |
| Exact dedup gồm interaction ID | 1.721.943 | 31.441 |
| Label nhị phân hợp lệ | 1.712.991 | 8.952 |
| Thời gian hợp lệ | 1.709.601 | 3.390 |
| Skill mapping hợp lệ | 1.709.601 | 0 |
| Single-skill | 1.611.613 | 97.988 |

Các counts tuần tự, không cộng double-count. 194 skill IDs có mặt trong tập chính. Hai interaction khác ID nhưng giống trường nghiệp vụ không bị gộp trong dedup; mọi dòng vẫn phải qua điều kiện label/time độc lập.

| Split | Học sinh | Tương tác |
|---|---:|---:|
| TRAIN | 3.500 | 1.127.951 |
| VALIDATION | 750 | 241.582 |
| TEST | 750 | 242.080 |

Seed 42, split theo học sinh và lưu manifest riêng. Kiểm tra artifact xác nhận học sinh không giao nhau, interaction ID/source row duy nhất, không chứa answer_text/hint_count/saw_answer. Chạy lại script chỉ xác minh hash/split, không chia lại.

## Metadata và content RQ2

Một problem có hai phiên bản khác nhau ở Fill-in Options và Fill-in Answers; cả hai được giữ trong hồ sơ review cục bộ, problem bị quarantine khỏi RQ2. Có 495 interaction của problem này đủ điều kiện RQ1 và được giữ.

3.368 problem IDs được kiểm tra. 2.233 problem vượt screen sơ bộ; 871 problem có tín hiệu media/external asset trong body/options, 355 multi-skill, 2 có answer type hỗn hợp/chưa hỗ trợ, 5 body rỗng hoặc không có văn bản, 1 conflict. Các lý do có thể chồng nhau. Con số 871 khác 835 dòng có `<img>` ở audit vì phép screen mới xét nhiều loại asset, cả options và đếm problem ID duy nhất.

**Chưa có bài nào được chứng nhận `rq2_text_eligible=True`.** Bộ review giữ nguyên HTML/LaTeX, lưu variants và các ô xác nhận parse/đủ nội dung/math/dependency/skill. Không coi thiếu `<img>` là bằng chứng text-complete. Đây là danh sách chờ rà soát, chưa phải candidate bank được phép dùng cho Agent.

## Kiểm chứng và bước tiếp

111 kiểm thử tích hợp đạt; reviewer độc lập không phát hiện lỗi quan trọng trong preprocessing/split/screen. Raw, split, parquet và nội dung theo từng bài nằm ngoài Git. Lock pin SHA-256 của raw, code, split, parquet và summary.

Cleaning/split đã khóa. Trước train phải hoàn thiện lock feature/model/evaluation và kiểm thử causal histories/OOF trên đường chạy v4. Không dùng script ASSIST09 để vô tình train hoặc đánh giá lại bộ cũ. Content review RQ2 có thể tiến hành độc lập với chuẩn bị RQ1.
