# Knowledge Tracing và AI gợi ý bài học

Kho mã cho một đề tài nghiên cứu khoa học sinh viên về dự đoán kết quả làm bài và xây dựng prototype gợi ý bài luyện tập từ trạng thái kiến thức ước lượng.

> **Trạng thái ngày 05/10/2026: tạm gác để ưu tiên chuẩn bị đề tài mới theo định hướng giảng viên về AI hỗ trợ ra quyết định trong doanh nghiệp.** Những kết quả, split và thí nghiệm trong kho này được giữ làm hồ sơ nghiên cứu. README ghi tình trạng thật để có thể quay lại sau; không có TEST RQ2 hay đánh giá chất lượng sư phạm nào đã được thực hiện.

## Tổng quan hiện tại

- **Dataset chính:** FoundationalASSIST tại snapshot `82b29188dffd2fd6bd3abc5a3de0db1ef1df12b9`. ASSIST09 là tài liệu lịch sử/fallback, không có workload mới.
- **RQ1 — dự đoán kết quả interaction:** đã hoàn thành training và đánh giá một lần trên TEST sau các khóa cấu hình đã lưu. Kết quả là dự đoán `discrete_score`, không phải đo trực tiếp mastery thật hay chất lượng gợi ý học tập.
- **RQ2 — prototype chọn bài:** đã hoàn thành một lượt phát triển cuối v3 trên VALIDATION với BKT state, danh sách ứng viên metadata, policy B+, Agent Qwen và hai baseline đơn giản. Agent chạy hợp lệ nhưng chưa đạt tiêu chí ổn định và rationale đã khóa trước lượt chạy.
- **Giao diện tác giả tự rà soát:** đã tạo cho 40 lời giải thích; bước chọn bài được làm trước khi xem lựa chọn và lời giải thích của Agent. Đây là self-review, không phải expert review.
- **RQ2 TEST, Lock C và kết luận về lợi ích học tập:** chưa có. Knowledge graph là giả định tác giả đề xuất, chưa được chuyên gia curriculum xác nhận.

Không dùng split TEST để chọn hoặc chỉnh mô hình, prompt hay policy. Không đưa dữ liệu gốc, ID học sinh, checkpoint hoặc output theo từng dòng lên Git. Các lần chạy mới phải tuân thủ các khóa và giới hạn trong [plan v4](NCKH_Knowledge_Tracing_AI_Agent_Plan_v4_FoundationalASSIST.md).

## RQ1: kết quả dự đoán đã hoàn thành

Năm mô hình được so sánh trên cùng tập interaction TEST. Tập chính dùng các interaction single-skill sau cleaning và student-disjoint split. Chỉ số chính là Brier score; thấp hơn tốt hơn.

| Mô hình | Số interaction TEST | Brier | ROC-AUC | Log loss |
|---|---:|---:|---:|---:|
| Global | 238.330 | 0,235420 | 0,500000 | 0,663701 |
| Problem | 238.330 | 0,209004 | 0,697131 | 0,605033 |
| PFA | 238.330 | 0,210532 | 0,690395 | 0,609967 |
| BKT | 238.330 | 0,210158 | 0,686573 | 0,609358 |
| XGBoost | 238.330 | **0,178223** | **0,788408** | **0,531971** |

XGBoost đạt kết quả dự đoán tốt nhất trong các mô hình đã thử. Điều này không chứng minh XGBoost là bộ ước lượng mastery tốt nhất, cũng không chứng minh một recommendation giúp học sinh tiến bộ. Xem [báo cáo RQ1 TEST](reports/foundationalassist_v4_rq1_test.md) và [plan v4](NCKH_Knowledge_Tracing_AI_Agent_Plan_v4_FoundationalASSIST.md).

## RQ2: trạng thái thí nghiệm cuối trên VALIDATION

Luồng prototype: lịch sử VALIDATION đến cutoff → BKT tạo ước lượng mastery theo skill ID → Python tạo trước tám candidate từ TRAIN → Agent nhận metadata và chọn một candidate. B+ là policy theo luật; random-uniform-by-ID và always-first là baseline. Các baseline so sánh hành vi, không phải đáp án vàng.

Thí nghiệm v3 chạy 328 lượt cục bộ: 48 lượt chẩn đoán contract, 4 context probes, 240 lượt chọn bài trên 40 học sinh VALIDATION mới và 36 lượt gửi lại nguyên request. Kết quả quan trọng:

- Agent trả về lựa chọn hợp lệ **240/240**.
- Cùng problem ID qua ba permutation chỉ **5/40** học sinh khi có graph và **6/40** khi bỏ cạnh; ngưỡng vận hành đã đặt là 32/40.
- Cả **240/240** lý do có chữ CJK; phiếu rationale chưa được người chấm đánh giá.
- Hậu kiểm request, response, hash, runtime, baseline và metric đạt. Theo quy tắc dừng đã khóa, Agent v3 chưa đạt yêu cầu vận hành. Kết quả này không chứng minh từng bài chọn là sai, và cũng không bác bỏ mọi cách kết hợp BKT với Agent.

Thí nghiệm dùng Qwen2.5:1.5b qua Ollama cục bộ trên VALIDATION. Không train lại Agent sau v3. Không có lượt TEST RQ2. Xem [báo cáo v3](reports/foundationalassist_v4_rq2_selection_v3.md), [protocol v3](reports/rq2_selection_protocol_v3.md), [thiết kế RQ2](reports/rq2_validation_design.md) và [progress log](reports/progress.md).

## Giao diện tự rà soát lời giải thích

Server local của giao diện hiện chạy tại [http://127.0.0.1:9411](http://127.0.0.1:9411). Tình trạng đã lưu hiện là 0/40 lựa chọn và 0/40 phiếu rationale.

Để mở lại sau khi server đã dừng, chạy trong PowerShell từ thư mục project:

```powershell
.\scripts\start_rq2_review_ui.ps1
```

Hoặc chạy trực tiếp trong terminal đang mở:

```powershell
.venv\Scripts\python.exe scripts/run_foundational_rq2_review_ui.py
```

Giao diện chạy trên loopback, không cần Ollama, không gọi AI và không gửi điểm lên API. Trình tự:

1. Nhập tên hoặc bí danh.
2. Trên từng phiếu, chọn bài bạn cho là hợp lý dựa trên bảng metadata hoặc chọn “Không đủ căn cứ”; ghi lý do. Lựa chọn Agent được giấu đến khi hoàn thành cả 40 phiếu.
3. Bấm “Bắt đầu chấm lời giải thích”. Sau đó lựa chọn bước 1 bị khóa; chấm bốn tiêu chí rubric và ghi căn cứ.

Chấm mỗi tiêu chí 0/1/2 hoặc “Không đánh giá được”. Nếu không đọc hiểu một lý do, đừng đoán điểm đúng/sai bằng chứng. Phiếu chỉ có mastery BKT, tỷ lệ đúng TRAIN, support, graph và metadata ứng viên; **không có nguyên văn đề bài hoặc đáp án**. Tự chấm được ghi nhận là đánh giá của tác giả, không thay người rà soát curriculum độc lập. Hướng dẫn chi tiết ở [tài liệu self-review](reports/rq2_selection_v3_author_review_guide.md).

Điểm và ghi chú được lưu cục bộ, trong thư mục Git bỏ qua:

```text
data/processed/foundationalassist_v4/rq2_validation/selection_v3/author_review/reviews.json
```

Không commit file review hoặc dữ liệu theo từng phiếu.

## Dạy Agent nhỏ: phương án chưa triển khai

Có thể dùng ví dụ chất lượng cao do teacher tạo để hướng dẫn model nhỏ trong một thí nghiệm mới. Việc đó không chuyển trọng số của Sol sang Qwen; đó là tạo cặp đầu vào/đầu ra, kiểm tra nhãn và có thể fine-tune adapter. Chưa tạo tập teacher data, chưa fine-tune hoặc mở TEST cho hướng này. Không dùng 40 phiếu VALIDATION đang rà soát làm training data.

Xem [các lựa chọn huấn luyện](reports/rq2_small_agent_training_options.md) để phân biệt luật Python, ví dụ trong prompt và LoRA/fine-tuning. Bất cứ nhánh huấn luyện nào quay lại project cũng cần protocol và tập đánh giá riêng; kết quả v3 được giữ nguyên.

## Dataset, split và xử lý dữ liệu

Snapshot FoundationalASSIST có ba CSV: `Interactions.csv`, `Problems.csv` và `Skills.csv`. Tóm tắt số dòng và nguồn nằm trong config/report preprocessing. Dữ liệu được làm sạch theo protocol v4; split student-disjoint 70/15/15, seed 42, được lưu và phải dùng lại. Counts được tính từ snapshot đã pin, có thể chênh README của dataset.

| Split | Học sinh | Interactions |
|---|---:|---:|
| TRAIN | 3.500 | 1.127.951 |
| VALIDATION | 750 | 241.582 |
| TEST | 750 | 242.080 |

RQ1 đánh giá 238.330 interactions TEST sau warm-up/scoring eligibility. Không chia lại split để khớp số liệu mong muốn. Không dùng `answer_text[t]`, `hint_count[t]`, `saw_answer[t]` hoặc nhãn hiện tại làm predictor cho kết quả hiện tại.

CSV, parquet và prediction theo dòng phải có sẵn cục bộ theo quyền truy cập dataset; chúng không nằm trong Git. Xem manifest/hash và quy tắc làm sạch trong [plan v4](NCKH_Knowledge_Tracing_AI_Agent_Plan_v4_FoundationalASSIST.md) cùng `configs/foundationalassist_v4_preprocessing.json`.

## Môi trường phát triển

Workspace hiện được dùng trên Windows/PowerShell với Python 3.10 và môi trường ảo `.venv`. Các lệnh dưới đây là ví dụ cho công việc đã có trong repo; RQ1/RQ2 đã hoàn tất lượt đánh giá được ghi ở trên, không chạy lại để tìm kết quả mới.

Tạo môi trường mới từ file khóa:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Chạy bộ kiểm thử tích hợp hiện có:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Notebook EDA: `notebooks/01_eda.ipynb`; báo cáo EDA: `reports/eda_summary.md`. Script EDA và các artifact ASSIST09/plan v3 được giữ làm lịch sử, không phải bước tiếp theo bắt buộc của đề tài đang tạm gác.

## Bản đồ file chính

| Đường dẫn | Nội dung |
|---|---|
| `NCKH_Knowledge_Tracing_AI_Agent_Plan_v4_FoundationalASSIST.md` | Quy trình dữ liệu và nghiên cứu hiện tại |
| `reports/foundationalassist_v4_rq1_test.md` | Kết quả RQ1 TEST |
| `reports/rq2_selection_protocol_v3.md` | Protocol Agent cuối đã khóa cho lượt phát triển |
| `reports/foundationalassist_v4_rq2_selection_v3.md` | Kết quả, kiểm tra và giới hạn RQ2 v3 |
| `reports/rq2_selection_v3_author_review_guide.md` | Hướng dẫn giao diện 40 phiếu self-review |
| `reports/rq2_small_agent_training_options.md` | Ý tưởng huấn luyện Agent nhỏ, chưa triển khai |
| `artifacts/tables/foundationalassist_v4_rq2_selection_v3_study.json` | Metrics tổng hợp công khai, không chứa output theo dòng |
| `scripts/run_foundational_rq2_review_ui.py` | Server local để mở giao diện chấm |
| `scripts/start_rq2_review_ui.ps1` | Launcher PowerShell cho giao diện |

## Phạm vi nghiên cứu và bản quyền nội dung

Kết quả metadata-only chỉ hỗ trợ phát biểu về hành vi lựa chọn, tính ổn định và việc tuân thủ giao thức. Nó không chứng minh nội dung bài phù hợp với skill, graph đúng về mặt sư phạm hay học sinh tiến bộ. Những đánh giá đó cần nội dung đủ điều kiện, nguồn rõ ràng và người có chuyên môn.

Không commit hoặc chia sẻ CSV, ID học sinh, output theo dòng hoặc nguyên văn đề bài từ dataset. Metadata `Skills.csv` là problem–skill mapping, không tự nó xác nhận quan hệ tiên quyết. ASSISTments ghi license cho nội dung Illustrative Mathematics được phân phối trên nền tảng của họ; không suy license đó cho mọi problem trong FoundationalASSIST. Chi tiết provenance và giấy phép nằm trong tài liệu v4.

## Đề tài giảng viên

Giảng viên đã nêu hướng mới: **AI hỗ trợ ra quyết định trong doanh nghiệp có kiểm chứng bằng chứng và nhận biết độ không chắc chắn**. README này mô tả project Knowledge Tracing đang tạm gác; đề tài mới chưa được mô hình hóa hoặc tạo code trong repo này. Khi tiếp tục, nên làm rõ câu hỏi nghiên cứu, loại quyết định doanh nghiệp, nguồn dữ liệu được phép sử dụng và cách đánh giá trước khi chọn kiến trúc AI.
