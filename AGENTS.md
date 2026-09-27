# Hướng dẫn cho Codex triển khai FabScope Simulator

## Nhiệm vụ đã chốt

Xây một MVP chạy được, kết hợp:

1. Mô phỏng hành vi một thiết bị xử lý wafer.
2. Giả lập giao tiếp giữa thiết bị đó và phần mềm khách.
3. Kiểm thử tự động các tình huống vận hành/giao tiếp và cung cấp bằng chứng đạt/sai.
4. Giao diện web nền tối, trực quan, dễ hiểu cho người mới.

Đọc theo thứ tự: `README.md` → `PROJECT_SPEC.md` → `INTERFACES.md` → `ACCEPTANCE_TESTS.md` → `IMPLEMENTATION_PLAN.md`. Khi người dùng yêu cầu bắt đầu, thực hiện triển khai; không dừng ở việc tóm tắt tài liệu hoặc vẽ kế hoạch.

## Cách làm việc

- Chủ động quyết định các chi tiết triển khai thông thường. Chỉ hỏi khi thiếu thông tin thực sự làm thay đổi phạm vi hoặc hành vi sản phẩm.
- Báo tiến độ bằng tiếng Việt, giải thích đã làm được gì và vấn đề tiếp theo cần giải quyết.
- Làm theo lát cắt đầu-cuối: một lượt chạy bình thường qua API và nhật ký trước; rồi mở rộng lỗi mạng, idempotency, phục hồi và UI.
- Tách lõi mô phỏng khỏi HTTP, lưu trữ và giao diện. UI không tự tạo một bản trạng thái khác.
- Test phải kiểm tra hành vi/đầu ra bằng oracle nêu trong ACCEPTANCE_TESTS, không chỉ so các hàm với chính dữ liệu do chúng tạo.
- Không huấn luyện AI hoặc tải dataset lớn chỉ để làm giao diện có vẻ đầy đủ.
- Không sửa dự án EtchScope hoặc các thư mục lân cận; workspace dự án mới là thư mục chứa file này.

## Nền tảng kỹ thuật mặc định

- Python 3.11+, FastAPI/Uvicorn, SQLite, pytest.
- HTML/CSS/JavaScript thuần, SVG cho sơ đồ thiết bị và timeline; chưa cần Node build hoặc framework frontend lớn.
- Windows/PowerShell là môi trường ưu tiên. Dùng `pathlib`, UTF-8 và hỗ trợ đường dẫn có dấu.
- Tạo `.venv` riêng; chọn phiên bản thư viện tương thích, ghi lockfile từ môi trường thực tế. Không dùng môi trường của EtchScope.
- Server chỉ bind `127.0.0.1`, cổng mặc định **8770** để tránh xung đột EtchScope ở 8765; có tham số đổi cổng.
- Chưa cần Docker, Kafka, Kubernetes, đăng nhập, tài khoản đám mây hoặc dịch vụ trả phí.

## Những giới hạn phải giữ

- Mọi màn hình/kết quả phải nhận diện rõ **dữ liệu mô phỏng, cấu hình giả định**.
- Không nhận định máy thật sẽ có cùng hành vi, không tuyên bố đạt SECS/GEM/EDA hoặc yêu cầu Viettel.
- Không mở kết nối tới thiết bị công nghiệp thật. START/ABORT chỉ tác động simulator.
- Không lấy trace BOSCH để làm bằng chứng simulator mô phỏng đúng vật lý.
- Không tự đăng lên GitHub, đưa dịch vụ ra Internet hoặc kết nối plugin bên ngoài chứa dữ liệu dự án. Người dùng mới chỉ yêu cầu chuẩn bị workspace; việc công bố dự án mới cần chỉ dẫn riêng.
- Không đọc tài liệu mật để “ẩn danh giúp” trong phiên cloud. Chỉ dùng dữ liệu giả hoặc nội dung đã được phép chia sẻ.

## Khi gặp công cụ bị chặn

Tôn trọng quyền công cụ. Không chuyển sang Playwright/CDP/shell hoặc kênh khác để vượt một lệnh từ chối truy cập trình duyệt. Có thể tiếp tục unit/integration tests và báo rõ chưa kiểm tra trực quan. Không tuyên bố đã xem UI nếu chưa xem được.

## Hoàn thành và bàn giao

MVP chỉ được coi hoàn thành khi chạy được UI, chạy được các kịch bản bắt buộc, lưu được báo cáo và vượt qua kiểm thử phục hồi. Báo rõ phạm vi đã hoàn thành, test đã chạy, phần chưa kiểm chứng. Cập nhật README và PROJECT_STATUS.md bằng hiện trạng thật.

Khi user chỉ yêu cầu đọc hoặc đánh giá tài liệu, làm đúng yêu cầu đó; không tự triển khai chỉ vì file này chứa hướng dẫn triển khai.
