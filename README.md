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

Đang thực hiện mốc EDA. Chưa train và chưa mở test để đánh giá mô hình.
Gate A cần preprocessing, leakage/cross-fit/sequential tests và cấu hình A hoàn chỉnh.
Các thư mục model/recommender/app là cấu trúc chuẩn bị, chưa phải tính năng đã triển khai.
Ollama chưa có trong PATH hoặc vị trí cài mặc định; LLM smoke test còn pending.
