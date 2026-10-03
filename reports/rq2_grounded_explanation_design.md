# Thiết kế RQ2 tiếp tục: B+ chọn, Agent giải thích

Ngày 03/10/2026. Trạng thái: development trên VALIDATION, chưa Lock C. Người dùng đồng ý tiếp tục hướng được đề xuất sau thử nghiệm calculator. Đây là thay đổi vai trò Agent; không phải chứng minh Agent chọn bài độc lập đã được sửa thành công.

## Câu hỏi và giới hạn

Nhánh chọn bài độc lập đã cho kết quả âm trên các cấu hình development, giữ nguyên trong lịch sử nghiên cứu. Nhánh mới hỏi: với bài được B+ chọn và bằng chứng tính từ dữ liệu đã khóa, local Agent có xác định đúng yếu tố quyết định, dẫn đúng bằng chứng và nêu giới hạn không chắc chắn không?

RQ1, split và BKT checkpoint không đổi. Chỉ dùng scenario VALIDATION đã lưu; không train lại. Graph vẫn author-proposed, không được coi là expert-validated. Không dùng đề bài, dữ liệu theo dòng hoặc nội dung chưa có eligibility. Không đo chất lượng sư phạm, causal benefit hay learning gain.

## Vai trò và baseline

B+ là thành phần duy nhất chọn bài, giữ nguyên luật đã triển khai. Bộ tạo bằng chứng ghi số ứng viên trước/sau từng bước: nguồn yếu liên kết với đích yếu được trình bày, gap tới tỷ lệ đúng TRAIN 0,7, support lớn hơn, ID từ điển. Bước đầu tiên còn một ứng viên là yếu tố quyết định; các bước sau không được nhận công đã quyết định lựa chọn. Một ứng viên duy nhất có trường hợp riêng.

Agent nhận ID đã chọn, số liệu của bài và bảng fact catalog cùng trace. Nó không được thay lựa chọn. Agent phải trả decisive factor, evidence IDs và bản diễn giải tiếng Việt ngắn. Một baseline template xác định dùng cùng bảng bằng chứng, không gọi LLM. Template có thể đạt các kiểm tra cấu trúc theo thiết kế; không suy diễn lợi ích của Agent từ việc cũng đạt các kiểm tra đó.

## Kiểm tra và hiển thị

Kiểm tra riêng schema/reason-length, giữ ID lựa chọn, decisive factor đúng, citation không trùng/không ngoài catalog và đủ bằng chứng lựa chọn cùng giới hạn. Các citation bắt buộc: bài đã chọn, bước quyết định, mastery là ước lượng, graph là giả định, không có bằng chứng learning gain.

Nếu đạt tất cả kiểm tra, renderer dựng câu từ chính catalog đã xác minh, theo thứ tự cố định. **Không hiển thị raw draft**. Việc câu hiển thị bám catalog là bảo đảm từ thiết kế renderer, không phải bằng chứng LLM viết đúng hoặc hiểu tri thức. Raw draft vẫn được lưu private để rà soát ngữ nghĩa riêng. Validator cấu trúc không phát hiện đầy đủ hallucination, diễn giải sai hoặc causal claims trong raw draft; không gọi nó là semantic grounding checker hoàn chỉnh.

Nếu explanation bị từ chối, ghi lỗi rõ và giữ bài B+ đã chọn; không sửa nội dung LLM, retry hoặc âm thầm thay bằng template. Template là baseline được đo riêng, không dùng để làm đẹp tỷ lệ thành công của Agent. Chưa gọi renderer này là giao diện sản phẩm hoàn chỉnh.

## Lượt thử hữu hạn trước khi chạy

Config `configs/foundationalassist_v4_rq2_explanation1.json`: Qwen2.5:1.5b đã cài, temperature=0, context 8.192, output 512, draft tối đa 240 ký tự. Dùng đúng subset development trước: 12 pilot + 12 challenge, ba permutation, hai graph variant, tổng 144 calls. Đây là mẫu đã xem trước; không phải xác nhận độc lập. Một prompt, không sweep hoặc tune trên TEST.

Metric khóa cho lượt development này: schema validity, ID consistency, decisive-factor accuracy, citation membership/coverage, tỷ lệ đạt tất cả kiểm tra, latency/token count, lỗi theo stage, template validity và độ ổn định lựa chọn B+. Mỗi cohort/graph có 36 calls, báo riêng. Khi báo accuracy, mẫu số là tất cả lượt dự kiến; không bỏ lượt lỗi. Repetitions thuộc cùng học sinh, không coi là 144 quan sát độc lập. Kiểm tra B+ giữ ID theo permutation; không dùng độ ổn định B+ để nhận công cho Agent.

Hai context probes mỗi graph variant ở 8.192/16.384 được giữ raw response, không tính vào study. Lưu request/response, packet, lỗi, telemetry ở đường dẫn private bị Git ignore; public chỉ tổng hợp và hash. Không ghi đè study completed/partial. Source/config/thiết kế/lịch cũ được pin trước khi chạy và kiểm tra lại cuối lượt.

## Điều kiện để khóa protocol sau development

Chưa tự Lock C dù structural checks đạt. Cần chốt mục đích cuối (prototype explanation hay nghiên cứu so sánh), xác định có đánh giá ngữ nghĩa/human readability không, rubric và người chấm nếu có, cách chọn mẫu và clustering/CI, metric cuối, graph assumptions, runtime/prompt và quy tắc xử lý lỗi. Nếu chỉ báo kỹ thuật, phát biểu giới hạn ở kiểm tra cấu trúc cùng bảo đảm renderer; không kết luận Agent hữu ích hơn template. Không mở TEST để quyết định thiết kế này.
