# Kế hoạch triển khai và bàn giao

## 1. Kết quả cần có

Người dùng cài dependencies, chạy một lệnh mở server và dùng trình duyệt tại `http://127.0.0.1:8770`. Họ thấy một máy ảo xử lý wafer, thử mất mạng/lỗi máy và xem một báo cáo giải thích phần mềm xử lý đúng hay sai.

Một lệnh khác chạy toàn bộ acceptance scenarios không cần UI và xuất báo cáo. Không cần tài khoản, khóa API, cloud hoặc dữ liệu thật.

## 2. Cấu trúc gợi ý

```text
FabScope-Simulator/
├── AGENTS.md
├── README.md
├── PROJECT_SPEC.md
├── INTERFACES.md
├── ACCEPTANCE_TESTS.md
├── IMPLEMENTATION_PLAN.md
├── PROJECT_STATUS.md       # Tạo/cập nhật khi triển khai
├── pyproject.toml
├── requirements.lock
├── configs/               # Cấu hình giả định có version
├── src/fabscope/
│   ├── domain/            # State machine, command, event, run
│   ├── clock.py
│   ├── storage.py         # SQLite và transaction boundary
│   ├── gateway.py         # Fault injection trên giao tiếp
│   ├── api.py
│   └── scenarios/         # Client, runner, independent assertions, reporting
├── ui/                    # HTML/CSS/JS, SVG
├── scripts/               # Lệnh khởi động và chạy demo/test
├── tests/
└── runtime/               # SQLite/log/report cục bộ, bỏ qua trong Git
```

Có thể tổ chức khác nếu gọn hơn; không tạo lớp trừu tượng hoặc microservice chỉ để đúng sơ đồ. Tách domain khỏi framework web là yêu cầu thực sự.

## 3. Thứ tự triển khai

### Bước 1 — Một lượt chạy đầu-cuối

- Tạo môi trường, package và config demo.
- Implement state machine EMPTY/LOADED/PREPARING/PROCESSING/COMPLETED, clock điều khiển được và event schema.
- Lưu SQLite; cung cấp LOAD/START/UNLOAD và đọc state/events qua HTTP.
- Client headless thực hiện một lượt; test A01, A02, A05 và cơ chế advance lớn.

**Mốc đạt:** có một lệnh chạy demonstration bằng terminal, đọc lại lịch sử từ SQLite được. Chưa làm UI đẹp trước mốc này.

### Bước 2 — Tính đúng khi có lỗi

- Thêm ABORT, machine fault, CLEAR_FAULT và vô hiệu hóa các lịch của run đã kết thúc.
- Implement idempotency bền vững, điều phối lệnh đồng thời.
- Thêm disconnected, lost ack once, duplicate event delivery và client cursor.
- Kiểm tra các kịch bản nhóm A/B.

**Mốc đạt:** lỗi máy và lỗi truyền thông được phân biệt, retry không làm máy chạy hai lần.

### Bước 3 — Restart và báo cáo

- Hoàn thiện transaction, khôi phục clock/schedule/state và kiểm tra config khi restart.
- Viết test restart qua tiến trình mới.
- Scenario runner tạo session tách biệt, xác minh kết quả theo oracle và xuất JSON + bản đọc được.
- Có test âm để chứng minh bộ đánh giá phát hiện sai, không chỉ tạo report xanh.

**Mốc đạt:** chạy lại scenario tái hiện được kết quả; đủ bằng chứng truy nguyên từng lỗi.

### Bước 4 — UI trực quan

Thiết kế nền tối, chữ dễ đọc, tiếng Việt, hạn chế thuật ngữ. Không tái sử dụng bố cục bảng chỉ số học máy của EtchScope.

Màn hình chính:

1. **Thiết bị:** SVG máy và vị trí wafer, trạng thái hiện tại, bước đang chạy, tiến độ.
2. **Điều khiển demo:** LOAD/START/ABORT/UNLOAD theo điều kiện, chọn recipe giả, advance/play/pause thời gian.
3. **Kết nối:** trạng thái gateway và góc nhìn phần mềm khách; nút tạo mất mạng, nối lại, mất ack một lần.
4. **Diễn biến:** timeline command/event; bấm vào xem ID, sim time và lời giải thích.
5. **Kịch bản kiểm thử:** danh sách dễ hiểu, nút chạy, expected/actual và mở báo cáo.

Có một kịch bản hướng dẫn nổi bật: **“Mất phản hồi sau START: gửi lại có làm máy chạy hai lần không?”** Người xem thấy kết quả chứ không phải tự đọc JSON để hiểu.

Play/pause chỉ điều khiển clock; advance thủ công và chạy tự động phải được serialize để không tiến thời gian hai lần. Khi play đang bật, khóa hoặc phối hợp advance thủ công một cách nhất quán. Polling UI không tự làm clock tiến.

Không bắt buộc mô hình 3D. Sơ đồ 2D, wafer, timeline và đồ thị đủ để minh họa tiến trình. Mọi hành vi phải lấy từ API, có trạng thái loading/error/stale rõ ràng.

**Mốc đạt:** người mới nhìn được “máy đang làm gì”, “khách đang biết gì” và “vì sao test đạt/sai”.

### Bước 5 — Bàn giao dùng được

- Chạy kiểm thử phù hợp, kiểm tra clean install và startup từ hướng dẫn.
- Dùng trình duyệt được phép để xác minh nếu khả dụng; nếu bị chặn, báo rõ giới hạn, không vượt chặn bằng kênh khác.
- Cập nhật README: mục đích, quickstart, URL/cổng, lệnh chạy scenarios, lệnh test, vị trí report, giới hạn.
- Tạo PROJECT_STATUS.md: đã làm, test đã chạy, còn thiếu; không ghi “chuẩn SEMI” hoặc “sẵn sàng Viettel” khi chưa có bằng chứng.
- Lưu dependencies đã chốt, cấu hình giả định và ví dụ report không chứa đường dẫn cá nhân/token.
- Không tự tạo repository remote hoặc push lên GitHub.

## 4. Các quyết định đã được phép tự xử lý

Codex tự chọn cấu trúc class/module, thư viện frontend nhỏ nếu thật sự cần, màu sắc/bố cục, validation codes chi tiết, cách lock SQLite và định dạng báo cáo. Giữ behavior contract. Không hỏi lại người dùng về từng lựa chọn thông thường.

Nếu thấy yêu cầu mâu thuẫn, ưu tiên: không phát sinh lệnh hai lần → giữ lịch sử chính xác → phục hồi rõ ràng → tái hiện kịch bản → giao diện. Nêu quyết định và cập nhật tài liệu để các phần thống nhất.

## 5. Cách đánh giá giá trị của bản đầu

- Các tình huống đã thiết kế có phát hiện đúng lỗi tích hợp không?
- Có tái hiện được cùng lỗi từ config/seed/scenario không?
- Có truy từ một kết quả về command, run và event liên quan không?
- Retry, event lặp và restart có làm sai lịch sử wafer không?
- Người xem có hiểu điều gì đã xảy ra và vì sao hệ thống kết luận PASS/FAIL không?

Những chỉ số này đánh giá công cụ kiểm thử. Không suy từ chúng thành tỷ lệ giảm phế phẩm, tăng công suất hoặc độ chính xác trên máy thật.

## 6. Điều kiện mở rộng

Sau MVP, muốn áp dụng vào thiết bị thật cần một định dạng xuất/bộ đặc tả được phép sử dụng và người kỹ thuật xác nhận behavior. Chọn một máy cụ thể, ánh xạ commands/events, chạy kiểm thử tương thích, rồi mới mở rộng. Nếu chưa có các điều kiện đó, hoàn thiện chất lượng MVP thay vì xây thêm nhiều máy giả với giả định chưa kiểm chứng.
