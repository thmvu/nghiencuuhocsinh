# Gate A — báo cáo tích hợp

**Gate A đạt cho bước fit/tuning RQ1. Chưa train model; Gate B và C chưa đạt.**

## Đã triển khai

- Cleaning giữ single-skill, không tự xóa cặp student–problem lặp hợp lệ; reject encoding skill lạ và identity lỗi.
- Dùng lại split manifest của EDA; kiểm tra SHA-256 raw, split và ghi hash config vào artifacts.
- Feature lịch sử shifted theo student/skill; accuracy khi chưa có lịch sử là 0.5.
- Problem success probability (tên code `problem_difficulty`, số lớn = dễ hơn): 5-fold OOF theo student, smoothing alpha 10; validation/test dùng thống kê full-train.
- Evaluator predict → observe → update, reset mỗi student, cùng warm-up 5; prediction không nhận correct/hint/attempt hiện tại.
- Configuration Lock A machine-readable; không chọn cấu hình từ nhãn test.
- Parquet chỉ chứa danh sách cột được phép, lưu local và Git-ignore.

## Bằng chứng kiểm tra

- `python -m unittest discover -s tests -v`: 21 tests PASS.
- Bao gồm 8 test độc lập: đảo nhãn hiện tại/tương lai; đảo nhãn cả sinh viên; đảo nhãn validation/test; fallback đúng fold; isolation/reset/mask và freeze tham số.
- Test bổ sung phát hiện cleaning âm thầm bỏ skill encoding lạ và chấp nhận source identity lỗi: đã quan sát FAIL, sửa, chạy lại PASS.
- `02_preprocessing.ipynb` đã chạy toàn bộ; kiểm tra mask evaluator khớp preprocessing trên trajectory train bằng adapter giả 0.5.
- Read-back parquet được so sánh chính xác với DataFrame trước khi ghi.
- Không tính metric hoặc phân phối nhãn test; chỉ thống kê số dòng/sinh viên và scoring mask.

| Partition | Rows | Students | Scored rows | Students không có scored rows |
|---|---:|---:|---:|---:|
| train | 168,431 | 2,802 | 155,418 | 492 |
| validation | 35,135 | 600 | 32,382 | 119 |
| test | 32,502 | 601 | 29,751 | 118 |

## Trách nhiệm và giới hạn

Hai tác nhân tạo preprocessing và protocol/evaluator; tác nhân kiểm thử viết test độc lập. Hai tác nhân bị giới hạn sử dụng trước khi hoàn tất báo cáo; root tiếp quản chạy test, sửa lỗi bổ sung và review tích hợp. Không tuyên bố đã có một vòng review độc lập hoàn chỉnh sau sửa.

Freeze global parameters được kiểm tra khi adapter cung cấp snapshot hook; adapter thật cần kiểm thử riêng. BKT fitter/PFA/XGBoost chưa triển khai. Lock A chọn SciPy likelihood có bounds thay pyBKT: phải xác minh bằng chuỗi nhỏ tính tay trước train.

CSV có schema corrected nhưng chưa xác minh byte-for-byte với bản tải chính thức. CP1252 được chọn từ strict roundtrip, không sửa raw bytes. Làm trên feature branch trong workspace hiện có để giữ chung dataset và môi trường giữa các tác nhân.

## Bước kế tiếp

Triển khai Global/Problem baseline và PFA trên TRAIN/VALIDATION theo config A; giữ TEST cho Gate B. Ollama smoke test và literature review vẫn còn pending, không phải kết quả RQ1/RQ2 đã hoàn thành.
