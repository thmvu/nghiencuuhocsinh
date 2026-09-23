# Tiến độ — plan v3

Phạm vi khởi động: môi trường local, bảo toàn CSV, notebook EDA chạy được và báo cáo dữ liệu thật.

- Plan: NCKH_Knowledge_Tracing_AI_Agent_Plan_v3_Consolidated.md.
- Ruling: thư mục chưa có Git; làm trực tiếp trong workspace người dùng chỉ định, không tạo worktree.
- Ruling: dùng Python 3.10.11 hiện có cho giai đoạn EDA; v3 không khóa Python version. Kiểm tra tương thích BKT riêng trước Gate A.
- Ruling: giữ nguyên CSV gốc ở thư mục chính, sao chép có kiểm tra SHA-256 vào data/raw.
- CSV người dùng cung cấp; chưa xác minh byte-for-byte với bản tải chính thức.
- Chưa train; Gate A/B/C chưa hoàn thành.

- Ruling: CSV không phải UTF-8; CP1252 strict decode/encode roundtrip thành công. Dùng CP1252 cho EDA, ghi rõ đây là suy luận encoding.

- EDA complete: notebook executed end-to-end; all code cells ran, no error outputs; nbformat validation passed.
- pip check passed; requirements-lock.txt saved.
- Independent review: no blocking leakage issue; added retention counts and dependency snapshot.
- Pending: preprocessing/features/tests + Lock A; Ollama smoke test; RQ1/RQ2 not complete.
