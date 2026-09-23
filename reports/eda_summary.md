# EDA — kết quả khởi động

- Raw: 346,860 dòng, 31 cột; 4,217 sinh viên.
- Thiếu skill: 63,755 dòng.
- Sau lọc missing skill: 283,105 dòng.
- Multi-skill: 47,037 dòng, separator `_`.
- Single-skill: 236,068 dòng (68.06%).
- Duplicate semantic rows: 0; duplicate student/order: 0.
- Repeated student/problem rows: 4779 (không tự động xóa).
- Single-skill subset: 4,003 students, 14,734 problems, 105 skills.
- Split student counts: {'train': 2802, 'validation': 600, 'test': 601}.
- Train: 168,431 dòng; 105 skills; success rate 0.6580.
- Train students ≤5 interactions: 492.
- Skill IDs với nhiều tên trong train: 0.
- Raw SHA-256: `162ef8d2d28bcbfea6591a282994062bd8d5eaa00636544292a0d268dca6e5da`.

## Quyết định và giới hạn

EDA chi tiết dùng train; chưa tính metric mô hình hoặc dùng nhãn test để tuning.
Raw gốc không thay đổi. File người dùng cung cấp phù hợp schema corrected collapsed; chưa xác nhận checksum với bản tải chính thức.
Split manifest lưu tại data/processed/student_split.json; các bước sau phải dùng lại.
Gate A chưa đạt: còn preprocessing/features, leakage tests, sequential evaluator và Configuration Lock A.
Chưa train model, chưa hoàn thành RQ1/RQ2.

## Bước tiếp theo

Implement preprocessing và kiểm thử lịch sử shifted/OOF theo student; chọn cấu hình A từ support train.
Kiểm tra BKT dependency và Local LLM runtime trước các thí nghiệm tương ứng.
