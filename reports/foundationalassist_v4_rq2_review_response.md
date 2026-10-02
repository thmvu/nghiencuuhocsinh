# Phản hồi review graph và runner VALIDATION v4

Ngày 02/10/2026. Xử lý nhận xét graph/policy và chuẩn bị thí nghiệm metadata-only trên VALIDATION. RQ1 không train lại; TEST RQ2 chưa mở; chưa Lock C. Graph vẫn author-proposed, `expert_validated=false`.

**Cập nhật sau lượt study thật:** runtime đã khởi động được theo yêu cầu tiếp theo của người dùng; context probe và 498 Agent calls hoàn tất, hậu kiểm đạt. Xem `reports/foundationalassist_v4_rq2_agent_validation.md`. Mục runtime chưa có phép đo bên dưới ghi lại trạng thái trước lượt study này.

## Những thay đổi đã có code và test

- **B+ v4 xét nguồn–đích:** chỉ ưu tiên ứng viên thuộc skill nguồn yếu (`p < 0.5`) khi có cạnh trực tiếp tới skill đích yếu (`p < 0.5`) có bài trong candidate set. Không dùng transitive closure; không áp hard readiness gate. Policy v4 ở `src/rq2/foundational_validation.py`, không sửa baseline ASSIST09.
- **Ranking draft:** tín hiệu soft remediation; gần TRAIN success-rate mục tiêu cố định 0.7; support lớn hơn; ID bài. TRAIN success rate là proxy độ dễ, không phải xác suất trả lời đúng của học sinh; không đồng nhất BKT mastery với success rate. Config và metrics đã ghi trước lượt development ở `configs/foundationalassist_v4_rq2_validation.json`, chưa phải Lock C.
- **Graph input allowlist:** chỉ có `skills`, `skill_to_standard`, các cặp `edges` và `link_semantics`. Không có URL, rationale, hash, `standard_edges`, thứ tự topo hoặc review status. Hai biến thể giữ cùng state/mapping/candidate membership/permutation; chỉ khác các cạnh. Không xóa mỗi `edges` trên artifact audit.
- **Nhiều skill ID:** giữ riêng mastery từng ID, mỗi nguồn yếu có thể tạo tín hiệu cho bài của chính ID đó. Tín hiệu boolean, không đếm số cạnh làm trọng số, không gộp state, không áp AND. Quy tắc có trong graph input/system prompt và test nguồn mastery thấp/cao khác nhau.
- **Runner v4 riêng:** `scripts/prepare_foundational_rq2_validation.py` kiểm tra hash BKT checkpoint/code, TRAIN, VALIDATION và manifest; partition đúng saved assignments và không trùng học sinh. Không đọc TEST parquet. Pool TRAIN loại metadata conflict, support tối thiểu 5. Replay chỉ prefix, không đổi tham số fitted BKT.
- **Baseline/repetition:** 50 học sinh, 8 ứng viên/scenario, 3 permutation và hai graph variant. Dùng chung order và random-by-ID draw giữa hai variant. RNG permutation/random tách biệt. Aggregate theo học sinh; paired sensitivity có denominator hợp lệ và invalid. Variability của random qua các draw khác nhau không được diễn giải thành position bias.

## Context và Agent chưa có phép đo runtime

Config context 8.192, output reserve 256, template reserve 1.024. Guard độ dài UTF-8 messages/schema cộng reserve chặn request trước khi gửi; **guard theo byte không phải số token tokenizer thực đo**. Guard lớn nhất trong tập request đã chuẩn bị là 4.748 (có cạnh), 4.202 (không cạnh), gồm template reserve, chưa cộng output reserve.

Context preflight dùng model/runtime thật: ghi version/digest, gửi cùng request lớn nhất theo byte ở context cấu hình và gấp đôi; lấy `prompt_eval_count`, kiểm tra hai count bằng nhau và còn output reserve. Model phải hỗ trợ cả hai context. Responses probe không vào study metrics. Mỗi study call kiểm tra token telemetry, `done_reason=stop`, schema và candidate membership; không dùng model ngoài hoặc mock làm kết quả. Token count theo [Ollama Chat API](https://docs.ollama.com/api/chat).

**Hiện tại:** loopback Ollama từ chối kết nối (`URLError`), `context_verified=false`, `agent_status=blocked_context_preflight`. Chưa thực đo token, chưa chạy Agent v4. Automatic approval review từ chối lệnh khởi động Ollama nền: `blocked by policy`, không cung cấp lý do chi tiết.

Khi Ollama hoạt động:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_foundational_rq2_validation.py --probe-context
.\.venv\Scripts\python.exe scripts\prepare_foundational_rq2_validation.py --run-agent
```

Preflight fail trả trạng thái lỗi và không tiến hành study calls. `--run-agent` luôn probe lại; model chưa cài sẽ dừng, không tự tải.

## Kết quả development hiện tại

- 50 scenario/50 học sinh; 1.025 TRAIN problem–skill pairs sau support floor; 69 ID bài thực sự xuất hiện trong candidate lists. Artifact theo scenario và ID chỉ lưu trong `data/` bị Git bỏ qua.
- 900 lựa chọn deterministic: 3 policy × 50 scenario × 3 permutation × 2 variant. Tất cả chọn candidate hợp lệ; đây là kiểm tra vận hành, không chứng minh chất lượng recommendation.
- B+ ổn định qua permutation. Always-first đổi ID ở 49/50 học sinh. Random đổi ở 47/50 theo các draw khác nhau; không gọi đó là position bias.
- B+ paired graph selection-change rate = 0. Coverage: 24/50 scenario có nguồn yếu, 8/50 có đích graph yếu được trình bày, nhưng 0/50 có cặp nguồn yếu–đích yếu thỏa điều kiện liên kết. Luật graph chưa kích hoạt. Không suy ra graph đúng, hữu ích hoặc vô dụng.

Update coverage: giữ pilot ban đầu, đã chẩn đoán cả 750 học sinh tại prefix 5/10/20/50 và bổ sung một cohort thăm dò riêng từ prefix50 có hai endpoint đã quan sát. Không đổi threshold hoặc tìm seed. 33 học sinh/97 surfaced IDs; B+ đổi lựa chọn khi bỏ cạnh ở 29/33. Đây là conditional policy test trên graph-constructed candidates, không phải kết quả đại diện hay hiệu quả giáo dục. Xem `reports/foundationalassist_v4_rq2_coverage.md`. Soft-remediation được chấm bằng cùng graph tham chiếu cho cả hai biến thể, không tự gán no-edge rate = 0.

## Verification và phần còn lại

145 kiểm thử tích hợp PASS; `git diff --check` sạch. Test mới kiểm tra đổi đích vắng candidate, đích đã mạnh, mastery nhiều ID khác nhau, cạnh lặp, không rò audit/topo, input/permutation chung, future-label perturbation, chặn TEST, thiếu telemetry, context quá ngân sách/output cutoff và coverage. Mock transport chỉ dùng unit test, không tạo artifact Agent study.

Chưa hoàn tất: quyết định protocol cuối và hướng xử lý Agent thiên lệch vị trí, Lock C và TEST RQ2. Token runtime, Agent VALIDATION và hậu kiểm đã hoàn tất trong báo cáo cập nhật. Raw, checkpoint, split và kết quả RQ1 giữ nguyên.
