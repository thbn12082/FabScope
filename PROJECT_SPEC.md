# Đặc tả sản phẩm

## 1. Bài toán

Trước khi kết nối thiết bị vào phần mềm nhà máy, cần biết phần mềm có xử lý đúng lệnh, trạng thái, dữ liệu và những tình huống gián đoạn hay không. Thiết bị thật có thể chưa sẵn sàng hoặc không phù hợp để liên tục tạo lỗi thử nghiệm.

FabScope cung cấp máy ảo và kịch bản có thể lặp lại để kiểm tra các hành vi đó. Giá trị đo bằng số lỗi tích hợp tìm được, khả năng tái hiện, tính nhất quán của hồ sơ và thời gian xác định nguyên nhân lỗi phần mềm. Chưa đo cải thiện yield hay độ chính xác dự báo sản phẩm.

## 2. Người dùng và thao tác chính

- Kỹ sư tích hợp: gửi lệnh, đọc trạng thái/sự kiện, tạo gián đoạn và kiểm tra phục hồi.
- Kỹ sư kiểm thử: chạy kịch bản, đọc expected/actual và xuất bằng chứng.
- Người xem không chuyên: quan sát wafer, trạng thái máy và câu giải thích điều vừa xảy ra.

Người dùng mở UI, nạp wafer giả, chọn recipe giả, START, xem tiến trình. Họ có thể giả lập mất mạng rồi nối lại, quan sát máy và góc nhìn phần mềm khách. Một nút riêng chạy bộ kịch bản trong môi trường độc lập, không làm hỏng lượt chạy thủ công.

## 3. Phạm vi MVP

Một loại thiết bị giả định, một buồng, mỗi lần xử lý một wafer. Một hoặc hai recipe giả chỉ quy định thời lượng bước và thông số sinh tín hiệu mẫu. Mỗi wafer có thể có nhiều lượt chạy; mỗi lượt có `run_id` riêng.

Có hai thành phần sử dụng cùng lõi:

- Server/API và UI để thao tác thủ công.
- Scenario runner/headless client để kiểm thử tự động qua giao tiếp.

Chưa có điều phối toàn nhà máy, nhiều buồng/robot, thiết bị đo thứ hai, sửa recipe online, mô phỏng plasma, dự đoán chất lượng, thuật toán AI hoặc xác nhận chuẩn giao tiếp công nghiệp. Có thể mở rộng sau khi MVP thật sự hoạt động.

## 4. Kiến trúc

| Thành phần | Trách nhiệm |
|---|---|
| Domain engine | Chuyển trạng thái, kiểm tra điều kiện lệnh, quản lý wafer/run, tạo sự kiện |
| Simulation clock | Thời gian mô phỏng có thể bước nhanh; test không phụ thuộc sleep dài |
| Persistence | SQLite lưu trạng thái, lệnh đã xử lý, sự kiện và lịch sử run |
| Equipment gateway | Giao diện khách; tạo các tình huống lỗi truyền thông theo cấu hình |
| Scenario runner | Điều khiển đồng hồ, gửi lệnh như khách, kiểm tra oracle và xuất báo cáo |
| Observer API/UI | Quan sát trạng thái thật của simulator, diễn giải góc nhìn khách và kết quả test |

Domain engine là nguồn trạng thái duy nhất. Tín hiệu, sơ đồ và sự kiện phải bắt nguồn từ engine/journal. Các bộ chuyển tiếp tương lai ánh xạ giao diện mới vào cùng lệnh nghiệp vụ.

## 5. Trạng thái và lệnh

Đây là state machine **giả định cho MVP**, không phải bản mô tả một máy khắc thật.

| Trạng thái | Ý nghĩa |
|---|---|
| EMPTY | Không có wafer, không có run đang hoạt động |
| LOADED | Có wafer, sẵn sàng nhận START hợp lệ |
| PREPARING | Run đã được tạo, đang chuẩn bị |
| PROCESSING | Đang thực hiện công đoạn giả lập |
| COMPLETED | Run hoàn thành; wafer còn trong máy |
| FAULT | Máy có lỗi giả lập, cần thao tác xử lý |

| Lệnh / sự kiện | Điều kiện | Kết quả |
|---|---|---|
| LOAD | EMPTY; wafer ID hợp lệ | Sang LOADED |
| START | LOADED; recipe/version tồn tại | Tạo run mới; sang PREPARING |
| Hết thời gian chuẩn bị | PREPARING và đúng run còn hoạt động | Sang PROCESSING |
| Hết thời gian xử lý | PROCESSING và đúng run còn hoạt động | Run COMPLETED; máy COMPLETED |
| UNLOAD | LOADED hoặc COMPLETED | Sang EMPTY, xóa wafer khỏi vị trí máy; không xóa lịch sử |
| ABORT | PREPARING hoặc PROCESSING | Run ABORTED; bỏ lịch bước còn lại; máy LOADED, giữ wafer |
| Inject machine fault | PREPARING hoặc PROCESSING, qua cổng điều khiển test | Run FAILED; bỏ lịch bước còn lại; máy FAULT |
| CLEAR_FAULT | FAULT | Máy LOADED, giữ wafer; không tự khởi động lại run đã FAILED |

Lệnh ngoài điều kiện phải bị từ chối bằng lý do có cấu trúc, không âm thầm bỏ qua. Ví dụ START trong EMPTY trả `INVALID_STATE`; START khi đang chạy với command ID mới trả `BUSY`. Wafer ID khác không được nạp đè wafer đang ở máy.

Mất kết nối là thuộc tính của gateway, **không phải một trạng thái máy**. Chính sách demo: mất liên lạc không dừng quá trình. Khi nhận lại phản hồi, phần mềm khách phải tự đối chiếu trạng thái và các sự kiện đã bỏ lỡ.

## 6. Tín hiệu mô phỏng

Sinh một số tín hiệu dễ quan sát, chẳng hạn `demo_process_level` có đơn vị quy ước và `step_progress_pct`. Giá trị phụ thuộc trạng thái/bước, có seed nếu dùng nhiễu. Không dùng một chuỗi ngẫu nhiên độc lập với tiến trình máy.

Không gán thông số giả thành áp suất/công suất của máy thật. Nếu dùng đại lượng minh họa có đơn vị vật lý, phải ghi rõ mô hình đơn giản và nguồn giả định; không suy ra độ sâu khắc hoặc độ an toàn thiết bị.

## 7. Lặp lại và phục hồi

- Kịch bản có config, seed, thời gian mô phỏng và lịch thao tác xác định.
- Bước chuyển phải thực hiện theo các mốc thời gian tới hạn; advance một khoảng lớn vẫn tạo đủ các bước theo đúng thứ tự.
- Lưu đồng bộ trạng thái, event và kết quả lệnh trong giao dịch SQLite để không có START đã nhận nhưng mất dấu run.
- Lưu trạng thái chấp nhận lệnh trước khi trả phản hồi; retry không được thực hiện nghiệp vụ lần nữa.
- Sau restart dịch vụ simulator, tiếp tục từ thời gian mô phỏng đã lưu. Thời gian mô phỏng tạm dừng khi dịch vụ tắt; không tự tính bù thời gian máy tính đã trôi qua.
- Chính sách restart ở trên là quy ước test có chủ ý, khác với mất kết nối gateway. UI phải giải thích được sự khác nhau.

## 8. Dữ liệu mẫu

Máy `SIM-ETCH-01`, wafer `W-DEMO-001`, recipe `DEMO_A`, version `1`. Tên ETCH chỉ là ngữ cảnh minh họa, không chứng minh mô hình vật lý khắc.

Giá trị khởi đầu có thể dùng prepare 3 giây mô phỏng, process 10 giây mô phỏng, chu kỳ telemetry 1 giây mô phỏng. Đánh dấu mọi giá trị này là **giả định cho demo** và để trong file config, không giấu trong mã.

## 9. Mở rộng sau MVP

Khi có tài liệu được phép sử dụng: bổ sung cấu hình hành vi, danh mục tín hiệu và adapter cho một model máy cụ thể; kiểm thử lại với nguồn tham chiếu hoặc thiết bị. Sau đó mới cân nhắc nhiều máy, mô phỏng hàng chờ hoặc dữ liệu đo chất lượng. Không xây trước toàn bộ nền tảng cho các khả năng chưa có yêu cầu.

## 10. Điều chỉnh giao diện theo yêu cầu người dùng (27/09/2026)

Màn hình chính là **nhà xưởng 3D, ít chữ**: kéo xoay/zoom, góc toàn cảnh/cận máy/từ trên, mở vỏ xem wafer. Nhật ký, kiểm thử và giải thích nằm trong mục mở rộng. Cảnh 3D chỉ chiếu snapshot từ API; không tự tiến clock hoặc duy trì state machine riêng. Vẫn chỉ SIM-ETCH-01 có hành vi nghiệp vụ; các máy/nhà xưởng khác là bố trí minh họa tĩnh. Đây là thay đổi cách trình bày theo phản hồi, chưa mở rộng sang mô phỏng nhiều thiết bị.
