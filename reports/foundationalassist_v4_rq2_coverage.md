# Độ phủ graph trong RQ2 VALIDATION v4

Ngày 02/10/2026. Đây là development trên VALIDATION, chưa Lock C hoặc TEST RQ2. Không train lại RQ1. Graph là giả định tác giả có nguồn curriculum, chưa được chuyên gia xác nhận.

## Pilot ban đầu được giữ riêng

50 học sinh, mỗi người một prefix có seed cố định, 8 ứng viên và 3 hoán vị. Pilot có 24 học sinh với skill nguồn yếu và 8 với skill đích graph yếu được trình bày, nhưng không có cặp nguồn–đích yếu tương ứng trong candidate set. B+ vì thế không đổi lựa chọn giữa hai biến thể graph.

Đây không phải bằng chứng graph vô dụng hoặc được xác nhận. Cần phân biệt dữ liệu không tạo ra tình huống kích hoạt với policy không sử dụng cạnh.

## Chẩn đoán các prefix cố định

Giữ nguyên BKT checkpoint, split, graph, ngưỡng nguồn/đích 0,5 và support TRAIN tối thiểu 5. Script `scripts/audit_foundational_rq2_coverage.py` xem cả 750 học sinh tại mốc 5, 10, 20, 50 tương tác. Không dùng lựa chọn policy để tính coverage.

| Prefix | Học sinh đủ lịch sử | Có liên kết nguồn–đích cùng yếu và có bài TRAIN | Trong đó cả hai skill đã quan sát | Generator ban đầu giữ được tín hiệu nguồn–đích |
|---|---:|---:|---:|---:|
| 5 | 750 | 3 | 3 | 0 |
| 10 | 750 | 5 | 5 | 0 |
| 20 | 750 | 13 | 13 | 0 |
| 50 | 750 | 33 | 33 | 4 |

Có hai giới hạn: tình huống liên kết cùng yếu hiếm và generator dàn trải mastery thường bỏ mất một endpoint. Không đồng nhất prior của skill chưa quan sát với điểm yếu thực sự. BKT mastery cũng không phải kiến thức thật được đo độc lập.

Artifact công khai chỉ chứa số tổng hợp và hash: `artifacts/tables/foundationalassist_v4_rq2_coverage_audit.json`.

## Nhóm kiểm tra bổ sung mang tính thăm dò

Thiết kế này được thêm **sau khi xem coverage**, trước lượt policy của nhóm bổ sung. Đây không phải thiết kế tiền đăng ký hoặc mẫu đại diện. Mốc 50 giúp kiểm tra hành vi trên nhóm có endpoint đã quan sát; toàn bộ các mốc khác vẫn được báo cáo, không tìm seed/ngưỡng nhằm tăng hiệu quả.

- Chọn tất cả học sinh tại đúng prefix 50, có ít nhất một cạnh mà cả nguồn và đích đã xuất hiện, mastery từng ID dưới 0,5 và có bài TRAIN đủ support. Không đọc response sau cutoff để tạo state hoặc chọn học sinh.
- Chọn đều theo cặp mã chuẩn, rồi đều theo cặp skill ID hợp lệ. Các ID cùng chuẩn giữ state riêng; không gộp hoặc áp AND. Nhiều ID không tự làm một cạnh chuẩn được chọn thường xuyên hơn.
- Lấy ngẫu nhiên một bài TRAIN của mỗi endpoint, rồi bổ sung 6 bài bằng generator hiện tại. Không chọn endpoint problem theo ranking B+, không loại ứng viên cạnh tranh theo kết quả policy.
- Cùng state, thành viên và thứ tự ứng viên cho B+, random, always-first và Agent. `no_edges` chỉ bỏ cạnh khỏi input policy; không dựng lại candidate set.
- Đánh giá soft remediation bằng cùng graph tham chiếu cho cả hai biến thể. Dùng graph rỗng làm nhãn sẽ khiến `no_edges` bằng 0 theo định nghĩa. Đây là chỉ số tuân theo giả định tác giả, không phải nhãn đúng về sư phạm.

Kết quả deterministic: 33 học sinh, 97 ID bài surfaced, 594 lựa chọn (33 × 3 permutation × 2 biến thể × 3 policy). Tất cả candidate hợp lệ. B+ ổn định qua permutation, đổi bài giữa có/không cạnh ở 29/33 học sinh (87,88%). Random và always-first giữ nguyên lựa chọn giữa hai biến thể khi order/draw được giữ nguyên.

Kết quả xác nhận **policy phản ứng với cạnh khi có tình huống kích hoạt**. Không chứng minh graph đúng hoặc giúp học tốt hơn. Do candidate set dùng graph để đưa vào hai endpoint, đây là **ablation có điều kiện trên cùng candidate set**, không phải so sánh hệ thống có graph với hệ thống hoàn toàn không graph. Không suy rộng 87,88% sang toàn bộ 750 học sinh hoặc pilot ban đầu.

Output tách riêng: `artifacts/tables/foundationalassist_v4_rq2_challenge_summary.json`; scenario, student ID và từng lựa chọn chỉ ở đường dẫn ignored `data/processed/foundationalassist_v4/rq2_validation/challenge/`. Không gộp hai cohort thành một sample độc lập; có thể trùng học sinh nên không cộng số học sinh để tính CI.

## Tiếp tục chạy

```powershell
.\.venv\Scripts\python.exe scripts\prepare_foundational_rq2_validation.py --cohort challenge
.\.venv\Scripts\python.exe scripts\prepare_foundational_rq2_validation.py --run-agent
.\.venv\Scripts\python.exe scripts\prepare_foundational_rq2_validation.py --cohort challenge --run-agent
```

Hai lệnh Agent chỉ chạy sau preflight runtime/context thật. Hiện Ollama chưa hoạt động nên chưa có Agent study results. Runner checkpoint từng call vào file private và báo tiến độ mỗi 10 call; không tự resume/mix lượt chạy dở vào kết quả hoàn tất. 145 kiểm thử tích hợp đạt, gồm future-outcome perturbation, endpoint chưa quan sát, ablation đầu vào chung và nhãn đánh giá tham chiếu chung.

Trước Lock C còn phải đo context và chạy Agent VALIDATION thật, quyết định vai trò cuối của từng cohort, khóa runtime/prompt/policy/metric và phạm vi phát biểu. TEST RQ2 vẫn đóng.
