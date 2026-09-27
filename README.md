# FabScope Simulator

**MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH**

MVP mô phỏng một thiết bị xử lý wafer, giao tiếp HTTP/JSON và kiểm thử tự động các tình huống vận hành/gián đoạn. Giao diện **nhà xưởng 3D**, ít chữ, tiếng Việt, chạy trên localhost. Không cần tài khoản, cloud, Node hay thiết bị thật.

Kéo để xoay, cuộn để zoom; chọn **Toàn cảnh / Máy / Từ trên**, bật/tắt **Mở vỏ máy** để nhìn wafer. Một máy SIM-ETCH-01 nhận trạng thái thật từ API; các máy và nhà xưởng còn lại chỉ minh họa bố trí, không phải mô phỏng nhiều thiết bị. Three.js được lưu trong dự án, không tải CDN khi chạy; cần trình duyệt có WebGL 2. Xem [THIRD_PARTY.md](THIRD_PARTY.md).

Đã có lõi trạng thái, SQLite, retry/idempotency bền vững, ba lỗi gateway, lỗi máy, phục hồi qua tiến trình mới và báo cáo JSON/HTML. Hiện trạng kiểm chứng xem [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Cài và chạy trên Windows

Mở PowerShell tại thư mục dự án. Cần Python 3.11+; môi trường đã kiểm chứng là Python 3.12 trên Windows. Lần cài đầu cần Internet để tải package; chạy simulator và test không cần Internet.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m fabscope serve
```

Mở **http://127.0.0.1:8770**. API tương tác: http://127.0.0.1:8770/docs. Dừng server bằng `Ctrl+C` trong terminal chạy server. Không cần activate môi trường hoặc đổi PowerShell execution policy.

Đổi cổng hoặc tạo session mới mà không xóa lịch sử cũ:

```powershell
.\.venv\Scripts\python.exe -m fabscope serve --port 8771 --db runtime/session-moi.sqlite3 --config configs/demo.json --reports runtime/reports
```

Chỉ bind `127.0.0.1`; không có tùy chọn mở ra Internet. Mỗi database chỉ dùng bởi một server. Restart với cùng `--db` và config khôi phục session cũ; thay config phải dùng database mới. Nếu database hỏng hoặc config không khớp, server báo lỗi thay vì tự reset.

Các script tiện dụng trong `scripts/` gọi đúng `.venv` của dự án; lệnh Python trực tiếp ở trên vẫn là cách dùng chính.

## Thử trong khoảng một phút

1. Bấm **Nạp wafer**, chọn `DEMO_A v1`, bấm **START**.
2. Bấm **Chạy** để xem PREPARING → PROCESSING → COMPLETED trong cảnh 3D. Có thể pause rồi dùng **+1s** / **+15s**. Advance bị khóa khi play.
3. Bấm **Lấy wafer ra**. Lịch sử run và sự kiện vẫn còn.
4. Mở **Thử lỗi & kết nối**, nạp lại wafer, bật **Mất phản hồi**, bấm START. Khi thấy `ACK_LOST`, bấm **Gửi lại cùng ID**; kết quả phải trỏ về cùng run.
5. Thử **Ngắt kết nối**, advance clock rồi **Nối lại gateway**. Vùng trái là sự thật trong simulator; vùng khách giữ lần nhận cuối và nhãn **DỮ LIỆU CŨ** cho tới khi đồng bộ lại.
6. Mở **Kiểm thử tự động**, bấm **Thử mất phản hồi START** để chạy B01 trên server/database riêng. Nhật ký, tín hiệu và giải thích được thu gọn, bấm để mở.

ABORT kết thúc run bằng ABORTED và giữ wafer. Lỗi máy kết thúc run bằng FAILED; CLEAR_FAULT chỉ về LOADED, không tự chạy lại. Đây là trạng thái phần mềm, không đánh giá lỗi vật lý của wafer.

## Kiểm thử và báo cáo

```powershell
# Unit/integration và 17 kịch bản qua HTTP localhost thật
.\.venv\Scripts\python.exe -m pytest -q

# Chạy tất cả acceptance scenarios, lưu bằng chứng ngoài thư mục test tạm
.\.venv\Scripts\python.exe -m fabscope scenarios --id all

# Chạy riêng restart sau mất phản hồi
.\.venv\Scripts\python.exe -m fabscope scenarios --id C02
```

CLI trả exit code 0 khi tất cả kịch bản yêu cầu đạt; 1 nếu có FAIL. Runner tự tạo/dừng tiến trình con trên cổng localhost tạm; không dừng server thủ công ở 8770. C01/C02/C04 thực sự kill server và tạo tiến trình mới dùng lại SQLite.

- `runtime/reports/<report_id>.json`: expected/actual, config/hash, seed, session và trace bằng chứng.
- `runtime/reports/<report_id>.html`: bản dễ đọc, mở trực tiếp hoặc qua `/sim/reports/<report_id>.html`.
- `runtime/reports/sessions/<report_id>/`: SQLite và log từng lần chạy; `error.txt` khi có lỗi thực thi scenario.
- [examples/reports](examples/reports/README.md): báo cáo B01 thật lúc nghiệm thu, chỉ có dữ liệu giả.

Không tự gán PASS: oracle kiểm tra state, số run, sự kiện, thời gian, trace qua restart và dữ liệu client. D01 có hai trace bị sửa chủ đích (thiếu RunCompleted, hai run cho một START) để chứng minh oracle trả FAIL.

## Cấu trúc

```text
configs/demo.json             Máy, recipe, thời lượng, telemetry, seed, giả định
src/fabscope/domain.py         Lõi trạng thái độc lập với HTTP/SQLite
src/fabscope/storage.py        Transaction state + command + run + event
src/fabscope/gateway.py        Disconnect, lost ack once, duplicate delivery
src/fabscope/api.py            Equipment API và cổng observer/test
src/fabscope/scenarios/        HTTP client, process runner, oracle, report
src/fabscope/ui/               HTML/CSS/JavaScript, cảnh 3D và biểu đồ SVG
src/fabscope/ui/vendor/        Three.js + OrbitControls + MIT license, chạy offline
scripts/                      Lệnh PowerShell tiện dụng
tests/                        Kiểm thử đầu-cuối và guard bổ sung
runtime/                      Dữ liệu cục bộ sinh ra; bỏ qua trong Git
```

SQLite lưu clock và deadline. Advance lớn vẫn đi qua từng mốc; seed và sim time quyết định tín hiệu. Tắt dịch vụ thì clock dừng; mất gateway không dừng xử lý. Poll UI không tiến clock. Play dùng tick 0.25 giây mô phỏng, không cam kết tốc độ thời gian thực.

MVP giữ toàn bộ journal; timeline UI hiển thị 100 sự kiện gần nhất, đồ thị tối đa 60 mẫu của **đúng run hiện tại**. Xem run cũ trong lịch sử/journal/báo cáo. Client dùng cursor liên tục, loại trùng theo event ID; không lấy observer để cập nhật góc nhìn khách.

## Giới hạn bản đầu

- Một máy, một buồng, một wafer; hai recipe minh họa DEMO_A/DEMO_B. Acceptance dùng DEMO_A v1 và config demo cố định.
- Mô phỏng chức năng/giao tiếp; không mô phỏng plasma, độ sâu khắc, chất lượng wafer hoặc độ an toàn thiết bị thật.
- HTTP/JSON thử nghiệm; chưa chứng nhận SECS/GEM/EDA, chưa đáp ứng hoặc được xác nhận theo yêu cầu Viettel.
- Chưa có authentication, multi-server, retention/archiving hoặc kiểm thử tải lâu dài. `/sim` là công cụ demo localhost.
- `requirements.lock` chốt dependency runtime/test từ môi trường thực tế. Cài source theo chế độ editable; chưa có bộ cài độc lập/wheel chứa config mặc định.
- Không dùng dữ liệu EtchScope/BOSCH hoặc tài liệu mật; không kết nối thiết bị công nghiệp. Công bố mã nguồn chỉ theo chỉ dẫn của chủ dự án; repo được chỉ định là [thbn12082/FabScope](https://github.com/thbn12082/FabScope).
- Workspace trong OneDrive; `.gitignore` không chặn đồng bộ. Chỉ dùng dữ liệu giả hoặc nội dung được phép chia sẻ.

## Tài liệu thiết kế

Đọc: [AGENTS.md](AGENTS.md) → README → [PROJECT_SPEC.md](PROJECT_SPEC.md) → [INTERFACES.md](INTERFACES.md) → [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md) → [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Đặc tả là hợp đồng; [PROJECT_STATUS.md](PROJECT_STATUS.md) ghi kiểm chứng thực tế và phần còn thiếu.

Nguồn định hướng từ bản bàn giao ban đầu: [PEER Group PFAT](https://www.peergroup.com/products-services/test-applications/pfat/), [SEMI Information and Control](https://www.semi.org/en/products-services/standards/information_and_control), [NIST Digital Twins](https://www.nist.gov/programs-projects/digital-twins-advanced-manufacturing). Đây là bối cảnh tham khảo, không phải chứng nhận simulator.
