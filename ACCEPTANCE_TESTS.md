# Kịch bản nghiệm thu MVP

Các kịch bản dùng dữ liệu giả và config demo cố định. Đây là nghiệm thu **phần mềm simulator**, không phải chứng nhận thiết bị thật. Mỗi scenario có session/database độc lập, seed, tập lệnh và oracle định trước.

## Nhóm A — Hành vi và dữ liệu

### A01. Một lượt chạy bình thường

Từ EMPTY, LOAD W-DEMO-001, START recipe DEMO_A v1. Advance clock tới hết chuẩn bị rồi hết xử lý; UNLOAD.

**Đạt khi:**

- Đi đúng EMPTY → LOADED → PREPARING → PROCESSING → COMPLETED → EMPTY.
- Chỉ một run được tạo, đúng wafer và recipe/version.
- Có đúng một kết thúc RunCompleted; event theo sequence và sim time nhất quán.
- Sau UNLOAD vẫn truy được lịch sử run.

### A02. Lệnh không hợp lệ

START khi EMPTY; LOAD đè khi đang có wafer; UNLOAD trong PROCESSING; START với recipe không tồn tại; thời gian advance âm/NaN/infinity.

**Đạt khi:** mỗi yêu cầu bị từ chối đúng code, không tạo hoặc thay đổi domain trái phép. Những giá trị không phải JSON hợp lệ cũng phải bị từ chối ở API.

### A03. ABORT và lịch sự kiện cũ

ABORT trong PROCESSING rồi advance vượt xa thời điểm dự kiến hoàn thành ban đầu.

**Đạt khi:** run ABORTED, máy LOADED giữ wafer, không phát RunCompleted cho run cũ. START mới tạo run ID mới và chạy bình thường.

### A04. Lỗi máy và xử lý lỗi

Inject machine fault trong PROCESSING, sau đó CLEAR_FAULT.

**Đạt khi:** run FAILED, máy FAULT; có lý do lỗi. CLEAR_FAULT đưa về LOADED, không tự chạy tiếp run thất bại. Advance qua lịch cũ không phát kết thúc thành công. Phải START bằng yêu cầu mới để có run mới.

### A05. Một wafer được xử lý lại

Hoàn thành run 1, UNLOAD, LOAD cùng wafer ID, START run 2.

**Đạt khi:** cùng wafer ID có hai run khác nhau; event/telemetry không ghép nhầm; lịch sử đầu tiên không bị ghi đè.

## Nhóm B — Giao tiếp

### B01. Mất phản hồi sau khi lệnh đã được nhận

LOAD bình thường. Bật lost-ack-once rồi gửi START với command ID C. Gateway trả lỗi. Retry cùng C và cùng payload.

**Đạt khi:** kết quả retry trả accepted và run ID ban đầu; chỉ một RunStarted/run được tạo. Có bằng chứng journal rằng lệnh đầu đã thực hiện dù khách không nhận được ack.

### B02. Dùng lại ID cho nội dung khác

Sau một lệnh có ID C đã được xử lý, gửi cùng C nhưng thay nội dung nghiệp vụ.

**Đạt khi:** IDEMPOTENCY_CONFLICT; không thực hiện nội dung thay thế. Kiểm tra cả payload có cùng khóa nhưng thứ tự JSON khác: không được coi khác nội dung nếu giá trị tương đương.

### B03. Mất kết nối khi máy đang chạy

START, đọc một phần event, ghi cursor, disconnect gateway, advance clock qua thời điểm hoàn thành.

**Đạt khi:** observer thấy máy COMPLETED, khách thấy không kết nối/stale chứ không giả vờ đang nhận dữ liệu. Reconnect rồi lấy bù đủ event từ cursor cũ; lịch sử kết quả có đúng một run hoàn tất.

### B04. Event bị gửi trùng và phân trang

Bật duplicate delivery; client lấy event bằng các trang nhỏ, nhận lại một phần dữ liệu đã xử lý.

**Đạt khi:** mỗi event ID chỉ được áp dụng một lần ở client, không mất event chưa nhận; trạng thái cuối và số run đúng như journal nguồn. Journal nguồn không bị nhân đôi vì lỗi truyền.

### B05. Hai yêu cầu START đồng thời

Máy LOADED. Gửi hai START đồng thời, kiểm tra hai biến thể: cùng command ID và khác command ID.

**Đạt khi:** cùng ID trả về cùng một run; khác ID chỉ một yêu cầu được chấp nhận, yêu cầu còn lại báo BUSY. Cả hai biến thể đều có tối đa một run hoạt động.

## Nhóm C — Bền vững và khả năng tái hiện

### C01. Restart giữa lượt chạy

START và advance vào PROCESSING, lưu cursor/command ID, dừng tiến trình server, khởi động tiến trình mới dùng cùng SQLite/config.

**Đạt khi:** khôi phục đúng trạng thái, run ID, sim time và lịch còn lại. Retry START cũ không tạo run thứ hai. Advance tiếp hoàn tất đúng một lần. Kiểm tra phải dùng hai tiến trình thật, không chỉ tạo hai object trong cùng RAM.

### C02. Idempotency qua restart sau mất ack

Thực hiện START dưới lost-ack-once; restart trước khi retry. Gửi lại cùng command ID sau restart.

**Đạt khi:** kết quả cũ và cùng run ID được trả; không có lần thực hiện mới.

### C03. Clock và seed xác định

Chạy cùng scenario/config/seed trong hai session độc lập. Thử thêm advance một bước lớn so với nhiều bước nhỏ tới cùng sim time.

**Đạt khi:** phần domain/telemetry xác định giống nhau sau khi chuẩn hóa các ID session/wall-clock không dùng làm kết quả mô phỏng. Advance lớn vẫn tạo đầy đủ các mốc và telemetry đã tới hạn, không nhảy qua PREPARING hoặc phát hoàn tất sai thứ tự.

### C04. Phân biệt restart và disconnect

Trong disconnect gateway, clock vẫn được advance và máy tiến. Khi toàn dịch vụ simulator tắt, clock không tiến; restart không tự tính bù wall-clock.

**Đạt khi:** hành vi khớp hai chính sách riêng; UI/report mô tả được sự khác nhau.

### C05. Cô lập kịch bản

Để một run thủ công ở PROCESSING rồi chạy một scenario tự động.

**Đạt khi:** scenario dùng session khác, không unload/reset hoặc sửa trạng thái của run thủ công. Báo cáo ghi đúng session và config của kịch bản.

## Nhóm D — Báo cáo và UI

### D01. Báo cáo có bằng chứng

Mỗi scenario xuất JSON và một bản HTML hoặc Markdown dễ đọc, gồm:

- Scenario ID, phiên bản phần mềm/config, seed, session.
- Từng bước, kết quả mong đợi, kết quả thực tế, đạt/sai.
- Command ID, event sequence, run ID liên quan; link hoặc trích đoạn bằng chứng.
- Kết luận có giới hạn: những gì đã kiểm tra, những gì chưa kiểm tra.

**Không đạt** nếu report chỉ có cờ PASS do scenario tự gán mà không kiểm tra kết quả độc lập. Phải có test âm: cung cấp trace thiếu RunCompleted hoặc có hai run cho một START, xác nhận bộ đánh giá báo FAIL.

### D02. UI phản ánh đúng dữ liệu

Thử chạy bình thường, lost ack, disconnect, fault và retry. UI hiển thị từ API/journal, không có model trạng thái giả song song.

**Đạt khi:** nêu rõ trạng thái thật của simulator, trạng thái cuối khách biết và kết nối; có hướng dẫn tiếng Việt. Không dùng màu đỏ để khẳng định wafer lỗi vật lý. Hiện nhãn “MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH”.

## Cách tổ chức kiểm thử

- Unit tests cho state transitions, clock và validation.
- Integration tests cho API + SQLite + gateway faults.
- Một suite đầu-cuối dùng client HTTP và server localhost tạm thời, có timeouts và cleanup tiến trình do test tạo.
- Kịch bản restart phải thực sự đổi tiến trình.
- Không phụ thuộc Internet, máy thật hoặc dữ liệu bí mật để test.
- Không dùng sleep dài để chờ toàn bộ quá trình; dùng clock có thể điều khiển. Chờ ngắn có timeout chỉ cho startup/shutdown giao tiếp khi cần.

Nếu môi trường không cho phép một loại test, báo chính xác phần chưa chạy, không đổi tên test unit thành end-to-end. Không tuyên bố đạt tất cả khi có test bị bỏ qua.
