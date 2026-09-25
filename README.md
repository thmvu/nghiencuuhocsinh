# NCKH — Knowledge Tracing và Local LLM

Kế hoạch chính: `NCKH_Knowledge_Tracing_AI_Agent_Plan_v3_Consolidated.md`.

## Chạy EDA (PowerShell, tại thư mục dự án)

```powershell
.\.venv\Scripts\python.exe scripts/run_eda.py
```

Notebook đã chạy được lưu cùng output tại `notebooks/01_eda.ipynb`.
Báo cáo: `reports/eda_summary.md`. Biểu đồ: `artifacts/plots/`.
Nếu mở notebook bằng VS Code, chọn interpreter `.venv/Scripts/python.exe`.

## Tạo lại môi trường

Python đã dùng cho giai đoạn EDA: 3.10.11.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe scripts/run_eda.py
```

CSV gốc do người dùng cung cấp; bản copy xác thực SHA-256 ở `data/raw/`.
Manifest nguồn tại `data/raw/manifest.json`; split student tại `data/processed/student_split.json`.
Không chia lại student trong các notebook sau. Không public raw data hoặc student IDs.

## Trạng thái

EDA, Gate A và RQ1 đã hoàn thành. Kết quả TEST RQ1 đã được đánh giá một lần sau Lock B;
xem `reports/rq1_test_results.md` và `configs/protocol_b.json`.
RQ2 đã qua Lock C và một lượt đánh giá TEST vận hành theo giao thức đã khóa.
Xem `reports/rq2_test_results.md`. Chưa có bằng chứng Agent tốt hơn B+ về sư phạm;
graph hiện chỉ là prototype và chưa có điểm người chấm mù.
Tổng quan 10 công trình liên quan: `reports/literature_review.md`.

## Preprocessing / Gate A

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/run_preprocessing.py
```

Notebook `notebooks/02_preprocessing.ipynb` chạy test trước khi chuẩn bị dữ liệu.
Có thể chạy riêng `scripts/prepare_data.py` để tái tạo parquet; lệnh đó không thay thế gate kiểm thử.
Artifacts local: `data/processed/train.parquet`, `validation.parquet`, `test.parquet`.
Không dùng test parquet để tuning hoặc báo cáo model metrics trước Gate B.

## Global/Problem baseline và PFA (TRAIN/VALIDATION)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/train_baselines_pfa.py
```

Kết quả phát triển: `reports/baselines_pfa_validation.md` và
`notebooks/03_baselines_pfa.ipynb`. Script chỉ đọc train/validation;
checkpoint và dự đoán từng dòng được giữ cục bộ. TEST chỉ dùng sau Lock B/Gate B.

## RQ2 — phát triển trên VALIDATION

Các script dưới đây chỉ dùng TRAIN và VALIDATION. Graph có 5 cạnh tiên quyết giả định,
chưa được xác nhận bằng học liệu hoặc giáo viên. Scenario và kết quả từng sinh viên
được lưu trong `data/processed/rq2_validation_scenarios/` và bị Git bỏ qua.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/prepare_rq2_validation.py
```

Agent dùng Ollama cục bộ và Pydantic. Sau khi cài [Ollama trên Windows](https://ollama.com/download/windows)
và tải `gemma3:1b`, chạy pilot giả lập rồi chạy một lượt VALIDATION:

```powershell
ollama pull gemma3:1b
.\.venv\Scripts\python.exe scripts/smoke_rq2_agent.py
.\.venv\Scripts\python.exe scripts/run_rq2_validation_agent.py
```

Số liệu phát triển tại `reports/rq2_validation_progress.md`; pilot giả lập không phải
kết quả nghiên cứu. TEST RQ2 đã được chạy **một lần** sau Lock C/Gate C;
không chạy lại `scripts/evaluate_rq2_test.py` hoặc dùng kết quả TEST để đổi hệ thống.

## Demo RQ2 cục bộ

Demo tạo trạng thái học sinh **giả lập**, giữ cùng graph và tập 8 bài ứng viên
cho B+ và Agent. Đầu ra chỉ minh họa cách chạy, không phải quan sát nghiên cứu.

```powershell
.\.venv\Scripts\python.exe scripts/demo_rq2.py --bplus-only
.\.venv\Scripts\python.exe scripts/demo_rq2.py
```

Lệnh thứ hai cần Ollama và `gemma3:1b` đang sẵn sàng trên máy.
