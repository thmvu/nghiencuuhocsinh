# Dạy Agent nhỏ: hướng mở rộng, chưa phải thí nghiệm đã khóa

Ngày 04/10/2026. Người dùng muốn tận dụng laptop GPU4GB/RAM16GB bằng đầu vào tốt hơn và ví dụ do Sol tạo. Tài liệu này giải thích lựa chọn; chưa tải base model training, cài stack GPU, gọi teacher API, tạo teacher labels hoặc train adapter. Thí nghiệm v3/kết quả âm được giữ nguyên; TEST RQ2 đóng. Huấn luyện Agent là nhánh mới cần protocol/holdout riêng, không đổi tên thành v3 đã thành công.

## Dạy bằng ví dụ, không chuyển trọng số của Sol

Có thể tạo các cặp đầu vào/đầu ra mẫu: snapshot kỹ năng + danh sách bài + lựa chọn có lý do bằng tiếng Việt, dựa trên đúng số liệu. Sol là teacher tạo bản nháp; người có chuyên môn hoặc quy trình review kiểm tra trước khi nhận làm label. Model nhỏ học hành vi trên nhiệm vụ hẹp, không nhận toàn bộ năng lực của teacher. Không có quyền truy cập hoặc xuất trọng số nội bộ của Sol 6.1 trong workspace này.

[OpenAI Docs về supervised fine-tuning](https://developers.openai.com/api/docs/guides/supervised-fine-tuning) mô tả cách dùng output model lớn tạo dữ liệu dạy model nhỏ. Đây là căn cứ cho quy trình chung, không xác nhận Sol 6.1 có sẵn endpoint fine-tuning hoặc rằng Qwen sẽ đạt tương đương Sol. Dùng Sol soạn ví dụ trong phiên hiện tại vẫn tiêu thụ hạn mức của phiên; tự động gọi teacher qua API là một workflow và chi phí khác, chưa được triển khai ở đây.

## Ba cách khác nhau

| Cách | Thay đổi gì | Giới hạn |
|---|---|---|
| Quy tắc và số liệu được chuẩn bị trước | Python tính số thống kê/đánh dấu độ thiếu dữ liệu, Agent đọc input ngắn hơn | Không học trọng số; ràng buộc hẹp có thể thay đổi RQ, phải ghi rõ |
| Vài ví dụ trong prompt | Agent nhìn mẫu tốt trong mỗi request | Không cập nhật trọng số; context tăng; không bảo đảm hết sensitivity |
| Supervised fine-tuning bằng LoRA/QLoRA | Học một adapter từ tập ví dụ đã review | Cần tập training riêng, stack training/base checkpoint và benchmark bộ nhớ thực tế |

[Hugging Face PEFT](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora) giải thích LoRA giữ trọng số gốc và học các ma trận cập nhật nhỏ; [Transformers/bitsandbytes](https://huggingface.co/docs/transformers/main/quantization/bitsandbytes) nêu training4/8bit chỉ hỗ trợ học tham số bổ sung. LoRA giảm nhu cầu bộ nhớ, nhưng inference được trên GPU4GB không chứng minh training vừa bộ nhớ. Cần thử đo với base/model, context, batch và optimizer cụ thể; chưa khẳng định laptop này train Qwen1.5B bằng QLoRA thành công. Không dùng file GGUF đang chạy Ollama như một checkpoint Transformers training có sẵn.

## Phân tách dữ liệu nếu triển khai sau

Chọn scenario training từ học sinh TRAIN của split đã lưu; không dùng TEST. 40 phiếu VALIDATION v3 dành cho đánh giá đã xem, không tự đổi thành training data. Mỗi học sinh giữ một partition; các permutation/lượt lặp không được rơi vào cả train và holdout. Nếu chọn hoặc tune bằng VALIDATION đã dùng, báo exploratory và khóa một protocol mới trước lượt đánh giá tiếp theo; không gọi nhóm đã dùng là unseen.

Ví dụ teacher cần số liệu đủ kiểm tra và kết luận có giới hạn; nếu người chấm không đủ căn cứ để chọn bài thì giữ nhãn uncertain thay vì bịa một đáp án đúng duy nhất. Review teacher output không thay review graph/item content. Kiểm tra hallucination, tiếng Việt, ID hợp lệ, consistency qua permutation và không đưa thông tin tương lai vào input. Không nhận agreement với teacher/B+ là bằng chứng sư phạm hoặc learning gain.

Mọi request/output theo học sinh, ví dụ training, adapter và reviewer notes chỉ local/ignored. Trước bất kỳ gửi dataset-derived scenario lên teacher bên ngoài, phải kiểm tra quyền/điều khoản/provenance; giao diện hiện tại không có chức năng gửi hay export training. Các ví dụ synthetic không chứa dữ liệu học sinh thật có thể dùng để thử quy trình trước, nhưng phải ghi rõ nguồn giả lập và không thay cho đánh giá trên dữ liệu thật.
