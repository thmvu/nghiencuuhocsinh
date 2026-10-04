# RQ2: Agent chọn bài độc lập — protocol phát triển v2

Ngày 04/10/2026. Trạng thái: chuẩn bị VALIDATION, chưa thực thi batch mới, chưa Lock C, không truy cập TEST. RQ1 và split đã khóa giữ nguyên.

## Câu hỏi và vai trò

Nhánh chính trở lại mục tiêu ban đầu: BKT ước lượng trạng thái kỹ năng → tạo danh sách ứng viên từ TRAIN → Agent chọn một bài và giải thích ngắn. Agent được cân nhắc các tín hiệu đầu vào, không phải sao chép thứ tự chấm điểm của B+. B+ là baseline theo luật; random-uniform-by-ID và always-first là hai baseline đơn giản. Cả bốn dùng cùng trạng thái, membership, graph variant và thứ tự trình bày.

Nhánh B+ chọn/Agent giải thích ngày 03/10 giữ làm kết quả phụ và lịch sử. Kết quả 21/144 là vượt toàn bộ hợp đồng dẫn chứng; 132/144 (91,67%) là xác định đúng yếu tố quyết định. Hai số này không phải điểm chất lượng ngữ nghĩa. Template đạt 144/144 theo thiết kế; renderer ghép catalog và không hiển thị draft Qwen, nên chưa chứng minh lời viết của AI hữu ích hơn template. Các model nhỏ đã thử chưa thực hiện luật tốt; điều đó không bác bỏ mọi Agent chọn độc lập.

## Đầu vào và giới hạn kết luận

Agent chỉ thấy estimated mastery, skill ID, curriculum links tùy biến thể, problem ID, TRAIN success rate và support. Không có đề bài, đáp án, nhãn tương lai, B+ winner, reference graph đánh giá hoặc ranking objective bắt buộc trong prompt. TRAIN success rate không phải xác suất đúng của học sinh cụ thể; BKT mastery không phải thiếu hụt kiến thức đã xác nhận.

Graph vẫn author-proposed, chưa expert-validated, không có nghĩa quan hệ nhân quả. Nhiều ID cùng standard vẫn là các BKT state riêng; không tự gộp hoặc áp điều kiện AND. Biến thể no_edges loại mọi thông tin cạnh và thứ tự topo khỏi đầu vào theo compact graph contract đã kiểm thử.

Metadata-only chỉ cho phép kết luận về hành vi lựa chọn vận hành. Muốn đánh giá phù hợp sư phạm phải review graph và nội dung các bài thực sự surfaced; muốn kết luận learning gain phải có thí nghiệm học tập khác. Không công khai student ID, đề bài hoặc output theo dòng.

## Batch chuẩn bị

Config: `configs/foundationalassist_v4_rq2_selection_v2.json`; entrypoint: `scripts/prepare_foundational_rq2_selection_v2.py`. Mặc định chỉ chuẩn bị, không gọi model. Cờ `--run-agent` dành cho bước thực thi tiếp theo.

Tái sử dụng subset đã kiểm tra: 12 học sinh pilot và 12 học sinh challenge, ba permutation, hai graph variant, một arm độc lập: 144 study calls, cộng bốn context probes ngoài study. Seed/display/enum order giữ như subset revision1; không thay membership để Agent dễ thành công. B+/random/always-first được tính lại và kiểm tra ID khớp baseline reference cũ trên đúng đầu vào. Random tái tạo các lần bốc độc lập theo seed cũ, không bốc lại để chọn kết quả đẹp. Latency baseline đo mới chỉ phần tính toán policy; không tái sử dụng latency lịch sử và không so trực tiếp với latency Agent gồm transport/runtime checks. Challenge được báo riêng; không gộp với pilot để suy rộng cho toàn bộ học sinh.

Đây là các scenario VALIDATION đã được quan sát trong phát triển. Batch này là exploratory, không phải holdout mới hoặc đăng ký trước thí nghiệm xác nhận. Chỉ một batch đã định nghĩa, không sweep prompt/model. Model/runtime digest và input/source hashes được ghi; thay runtime phải xử lý bằng protocol mới thay vì bỏ qua mismatch.

Ollama v2 dự kiến 0.35.1, khác lượt Qwen chọn bài ngày 02/10 (0.34.4); so kết quả lịch sử phải ghi yếu tố runtime này. Trước Lock C có thể thiết kế một nhóm VALIDATION chưa từng chạy policy/Agent, khóa seed và tiêu chí trước; không gọi là hoàn toàn chưa xem vì coverage đã kiểm tra cả 750 học sinh. Bước đó chưa được thực hiện hoặc khóa trong batch này.

## Metric đã định nghĩa trước batch

Primary: số lựa chọn hoàn tất, telemetry hợp lệ và ID thuộc candidate set chia cho toàn bộ study calls đã lên lịch, chỉ trên batch vượt runtime-integrity gate. Lựa chọn khác B+ vẫn hợp lệ. Không sửa ID, fallback hoặc retry để tăng tỷ lệ thành công. Batch lỗi integrity không nhận là kết quả hoàn tất; giữ log và số lượt đã nhận.

Validity là primary về độ tin cậy kỹ thuật, không tự chứng minh lựa chọn có ích; enum có thể khiến tỷ lệ gần 100%. So sánh hành vi dùng cùng bộ metric dưới đây cho Agent/B+/random/always-first, riêng từng cohort × graph variant; không chọn metric sau khi thấy Agent output. Báo các giá trị cạnh nhau, không gộp thành điểm chất lượng giáo dục.

Secondary:

- ID-stable: cùng problem ID qua ba lượt; skill-stable: cùng skill ID qua ba lượt. Báo stable/complete valid triplets, số complete/thiếu và số học sinh đổi ID. Random không ổn định do bốc độc lập không tự chứng minh order bias. Với membership cố định gồm m ID, kỳ vọng ID-stable là 1/m² (1/64 khi m=8), skill-stable là tổng (n_s/m)³; báo cả lý thuyết và kết quả random đã lưu.
- Xếp hạng tăng dần mastery BKT trên k kỹ năng phân biệt có trong candidate set; so sánh đồng hạng theo giá trị chính xác, dùng mid-rank. Hạng chuẩn hóa r=(rank−1)/(k−1). Bài cùng skill nhận cùng hạng; k=1 không xác định, báo số lượt hợp lệ bị loại. Mean r dùng lượt hợp lệ có k>1, cùng coverage trên toàn bộ planned calls. Khi mọi skill đồng hạng và k>1, r=0,5; giá trị 0 là đáy không đồng hạng. Không nhận mastery thấp hơn luôn là bài tốt hơn.
- Báo tỷ lệ chọn skill thuộc nhóm mastery thấp nhất trong các lượt hợp lệ; đồng hạng đáy đều được tính. Random chọn đều theo ID nên kỳ vọng r và xác suất chọn đáy phải trọng số n_s/m, không mặc định mean r=0,5. Reference kỳ vọng tính trên planned inputs, không lọc theo Agent thành công; do đó báo rõ khác biệt coverage khi diễn giải.
- Phân bố vị trí display và enum, cùng tỷ lệ chọn vị trí đầu trong các lượt hợp lệ. Tham chiếu random 1/m (1/8 hiện tại) chỉ là kỳ vọng, không phải kiểm định. Always-first display 0 theo định nghĩa; B+ không phụ thuộc permutation, phân bố vị trí phản ánh các permutation đã tạo.
- Latency tất cả lượt gồm failures; failure stages và count rõ ràng.
- Mastery ước lượng của skill được chọn, TRAIN success rate, support; đây là mô tả, không tự coi chọn mastery thấp nhất là tối ưu.
- Soft source-remediation trên cùng full reference graph chỉ dành cho evaluator; graph không cạnh không được nhận reference này. Chỉ số là proxy dưới giả định tác giả.
- Số cặp có/không cạnh đổi lựa chọn ở cùng học sinh và permutation, cùng số cặp đầy đủ/thiếu; phản ứng với graph không xác nhận graph đúng.

Agreement với B+ là supplementary. Luật B+ ưu tiên weak source liên kết weak target, gần TRAIN success rate 0,7, support rồi ID; đó là một heuristic cụ thể, không phải đáp án vàng. Không dùng disagreement làm lỗi hoặc bằng chứng kém sư phạm.

Lưu ý diễn giải trước inference v2: prompt Agent yêu cầu cân nhắc kỹ năng yếu, trong khi B+ chỉ ưu tiên nguồn yếu khi có liên kết tới đích yếu được trình bày; nếu không, B+ ưu tiên TRAIN success rate gần 0,7. Vì hai policy có mục tiêu khác nhau, Agent có hạng mastery thấp hơn B+ chỉ thể hiện xu hướng lựa chọn theo mục tiêu prompt, không chứng minh tốt hơn. Nếu mỗi ứng viên thuộc một skill khác nhau, ID-stable và skill-stable trùng nhau; hai metric chỉ bổ sung thông tin khi có nhiều bài cùng skill.

Random dùng chung lần bốc theo seed/scenario/repetition giữa hai graph variant trên cùng membership, nên graph sensitivity bằng 0 theo thiết kế; always-first cũng không đọc graph. Các giá trị 0 này là kiểm tra đối chứng bất biến, không phải mức phản ứng graph tối ưu để Agent phải vượt. So có/không cạnh ở đây chỉ là thay thông tin cạnh trong đầu vào policy trên cùng candidate set, không phải loại graph khỏi toàn bộ hệ thống sinh ứng viên.

Enum permutation được tạo có seed nhưng không ép cân bằng vị trí trên mẫu hữu hạn. Always-first hiện chọn enum 0 ở 16,7% (pilot) và 19,4% (challenge); mức này không tự chứng minh toàn bộ enum bị lệch hoặc Agent có thiên lệch. Báo tỷ lệ enum của Agent cạnh các baseline trên cùng permutation và kỳ vọng uniform 1/8, không thay kỳ vọng lý thuyết bằng một baseline như đáp án vàng. Mỗi ô chỉ 12 học sinh/36 lượt; các chênh lệch quan sát được chỉ mô tả, chưa là kiểm định hoặc bằng chứng sư phạm.

Khi có CI/thử nghiệm xác nhận, phải bootstrap paired theo học sinh, giữ các repetition/variant của cùng học sinh cùng cluster; không coi 144 calls là 144 học sinh độc lập. Chưa có CI tự động trong runner chuẩn bị này. Trước Lock C phải khóa estimator, seed, số bootstrap và cách xử lý failure.

## Rà soát lời giải thích riêng biệt

`reason_semantically_verified=false` cho output tự động. Schema/ID đúng không xác minh nội dung. Không yêu cầu một chuỗi citation literal để thay cho chấm ngữ nghĩa.

Rubric dự kiến 0/1/2 cho từng chiều: 0 = sai/thiếu nghiêm trọng; 1 = một phần hoặc còn mơ hồ; 2 = đầy đủ theo đầu vào.

| Chiều | Người chấm kiểm tra |
|---|---|
| Nhất quán bằng chứng | Số liệu, ID, quan hệ đúng với metadata được cung cấp, không bịa |
| Liên quan lựa chọn | Lý do gắn với bài được chọn và giải thích tradeoff hợp lý |
| Nhận biết giới hạn | Không đổi ước lượng thành sự thật; không nhận graph nhân quả hoặc learning gain |
| Dễ hiểu | Diễn đạt rõ, đủ ngắn, giúp người đọc hiểu lựa chọn |

Hiện chỉ Agent có reason: ẩn danh model và xáo thứ tự bằng seed, không nhận là so sánh mù giữa policy. Muốn so rationale với B+ phải chuẩn bị giải thích baseline tương ứng trước khi chấm. Lý tưởng hai người độc lập; ghi đồng thuận và cách xử lý bất đồng. Rationale chỉ chấm ở lượt output hợp lệ, đồng thời báo riêng tất cả lượt lỗi. Chưa có người chấm, chưa chạy rubric hoặc AI judge. AI critique nếu bổ sung báo riêng, không nhận chuyên gia xác nhận. Đây là đánh giá lý do dựa metadata, không thay đánh giá đề bài/sư phạm. Chốt procedure, rater và sample trước Lock C.

## Lưu log và bảo toàn nghiên cứu cũ

Luồng mới ghi request và raw response bằng append/flush/fsync trước mọi truy vấn runtime sau call. Endpoint version lỗi sau khi nhận response vẫn giữ response. Mismatch runtime dừng batch, không fallback; journal tồn tại ngăn chạy lại âm thầm. HTTP error giữ body cho journal và caller.

Journal có nhiều event cho mỗi logical call. Summary/audit đếm riêng scope probe/study, attempts_started, transport_calls và responses_received theo call index, không đếm dòng JSONL. Batch hoàn tất phải có bốn probe và 144 study attempts; transport có thể ít hơn attempts khi runtime mismatch trước call. Mismatch ở study attempt k lưu đúng k partial rows và dừng trước k+1; response đã nhận vẫn nằm trong journal nếu mismatch sau call. Các bài kiểm thử transport đều dùng giả lập, không được báo là inference thật.

Các runner/source đã pin cho thí nghiệm cũ giữ nguyên để không làm sai provenance. Fix có hiệu lực ở entrypoint mới qua `src/rq2/runtime_journal.py`, không viết lại các kết quả cũ. Journal, schedule, baseline records và per-student outputs chỉ lưu trong đường dẫn ignored; Git chỉ lưu protocol/config/code và aggregate manifest.

## Điều kiện bước tiếp theo

Kiểm thử tích hợp và chuẩn bị manifest trước. Batch mới chưa là Lock C. Sau development phải chốt model/runtime/prompt, scenario rules, graph giả định, metrics/rubric, failure handling và CI; commit configuration trước bất kỳ TEST RQ2 nào. Không train lại RQ1 hoặc dùng TEST để điều chỉnh thiết kế.
