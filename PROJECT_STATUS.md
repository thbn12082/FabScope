# Hiện trạng FabScope Simulator

Ngày kiểm chứng: **27/09/2026** · phiên bản **0.1.0**.

**MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH.** MVP đã triển khai và chạy được tại localhost. Kết quả chỉ áp dụng cho phần mềm/config demo trong workspace này.

## Điều chỉnh theo phản hồi: nhà xưởng 3D, ít chữ

- Thay dashboard/sơ đồ 2D bằng cảnh nhà xưởng WebGL 3D chiếm phần lớn màn hình. Có kéo xoay, cuộn zoom, góc toàn cảnh/cận máy/từ trên, chọn máy và mở vỏ để quan sát wafer.
- Rút ngắn nhãn/nút; đưa nhật ký, kịch bản, lỗi và giải thích vào các mục mở rộng. Giữ nhãn dữ liệu mô phỏng.
- Wafer, đèn trạng thái và mức hiển thị xử lý chỉ cập nhật từ snapshot `/sim/state`. Render/camera không tiến đồng hồ hay phát lệnh nghiệp vụ. Khi pause, trạng thái máy 3D đứng nguyên.
- Vẫn chỉ có một máy nghiệp vụ SIM-ETCH-01. Bốn máy xung quanh, stocker, đường ống và nhân vật là mô hình bố trí tĩnh, ghi nhận là minh họa; chưa có mô phỏng logistics hay điều phối toàn nhà máy.
- Three.js 0.180.0 và OrbitControls được lưu cục bộ kèm MIT license/hash, không cần Node/CDN khi chạy. Hình học tạo bằng mã, không dùng tài sản nhà máy thật. Cần WebGL 2; nếu không khởi tạo được sẽ báo lỗi, các nút/API vẫn sử dụng được.
- D02 qua HTTP/assets đã chạy lại: PASS. Kiểm tra hash thư viện, các ID điều khiển và phục vụ module cục bộ: PASS. Trên Edge đã xem cảnh 3D, chuyển toàn cảnh/cận cảnh, kéo xoay, cuộn zoom, mở/đóng vỏ; bấm +1s cập nhật cả canvas và sidebar từ t=19.75s lên 20.75s, tiến độ 18% lên 28%. Kiểm chứng 44 test/17 scenario của lõi bên dưới vẫn là bằng chứng trước thay đổi giao diện, không tuyên bố đã chạy lại toàn bộ vì không sửa domain/API.

## Đã hoàn thành

- State machine EMPTY/LOADED/PREPARING/PROCESSING/COMPLETED/FAULT; LOAD, START, ABORT, UNLOAD, CLEAR_FAULT; hủy lịch run khi ABORT/FAILED.
- Clock advance/play/pause; serialize clock và command bằng giao dịch SQLite. Tín hiệu có seed, liên hệ với bước/tiến độ.
- Lưu atomic state, clock/schedule, command fingerprint/result, event journal và runs; retry bền vững qua restart, bao gồm từ chối nghiệp vụ. Config khác và database hỏng không bị âm thầm reset.
- Gateway disconnect, lost acknowledgment once, duplicate event delivery; client giữ cursor liên tục và loại trùng; START đồng thời chỉ tạo tối đa một run.
- API equipment tách observer/test; server bind 127.0.0.1, mặc định 8770. UI không dùng observer để cập nhật góc nhìn khách.
- 17 scenario A01–D02 dùng server/SQLite riêng; JSON + HTML có config/hash, seed, session, expected/actual, command ID, event sequence, run ID và trace.
- Giao diện tiếng Việt nền tối, nhà xưởng 3D, tín hiệu đúng run, timeline, lịch sử, các nút thử lỗi, retry, play/pause, kịch bản và liên kết báo cáo.
- `.venv` riêng, dependency lock thực tế, script PowerShell, README hướng dẫn cài/chạy/kiểm thử.

## Bằng chứng đã chạy

| Kiểm tra | Kết quả |
|---|---|
| `python -m pytest -q` trong `.venv` | **44 passed**, không skip; lần cuối 54.43 giây, gồm kiểm tra server con đã dừng |
| `python -m fabscope scenarios --id all` | **17/17 PASS**; JSON/HTML trong `runtime/reports/` |
| C01, C02, C04 | Kill tiến trình server, xác nhận HTTP cũ đã dừng, PID phục vụ HTTP mới khác PID cũ; khôi phục đúng clock/state/schedule/ID và hoàn tất đúng một lần |
| B05 | Hai START đồng thời: cùng ID trả cùng run; khác ID có một OK và một BUSY |
| D01 | Oracle từ chối trace thiếu hoàn tất và trace hai run cho một START |
| Guard bổ sung | Strict JSON/schema, clock hữu hạn, rollback transaction, config mismatch, DB hỏng, cursor bị hổng, retry lệnh bị từ chối, retry sau hoàn tất, advance đồng thời, đường dẫn report |
| Cài sạch | Tạo `runtime/clean-install-venv`, cài từ lockfile + editable source; `pip check` không có dependency hỏng |
| Startup môi trường sạch | A01 PASS qua HTTP server thật từ môi trường vừa cài |
| Kiểm tra trình duyệt | Đã mở và thao tác trực tiếp trên **Microsoft Edge**, đã xem ảnh giao diện |

Pytest có **một cảnh báo deprecation** từ Starlette TestClient về backend `httpx`; không có test lỗi. Các scenario HTTP thật dùng `httpx.Client` và không phụ thuộc TestClient. Phiên bản đã lock hiện vẫn chạy đầy đủ.

## Kiểm tra UI đã thực hiện trực tiếp

- LOAD → START: sơ đồ có wafer, state/clock/tiến độ lấy từ API.
- Lost ack: UI báo ACK_LOST, retry giữ command ID và trả lại run-0001; nhật ký chỉ có một RunStarted.
- Disconnect: observer COMPLETED tại t=15s, client vẫn PREPARING tại t=0s kèm DỮ LIỆU CŨ. Reconnect cập nhật COMPLETED và cursor từ 3 lên 17.
- Lượt chạy mới → tạo lỗi máy → FAULT → CLEAR_FAULT → LOADED, giữ wafer; không tự chạy lại.
- B01 từ nút nổi bật: UI hiển thị PASS, 4/4 điều kiện; mở expected/actual thấy cùng run ID cho retry. Báo cáo HTML/JSON được kiểm tra trả về qua HTTP trong C05.
- Play làm clock tiến và khóa advance thủ công; pause giữ lượt chạy ở PROCESSING tại t=19.75s. Tab localhost được giữ mở để người dùng tiếp tục.

Các thao tác này là kiểm tra trực tiếp trong phiên làm việc, **không phải** bộ regression browser tự động đã lưu. D02 tự động chỉ kiểm tra assets/HTTP và client headless, riêng với bằng chứng UI trực tiếp ở trên.

Sau chỉnh sửa đồ thị, D02 được kiểm tra riêng và đạt; sau bổ sung kiểm tra vòng đời server trên Windows, toàn bộ 44 test được chạy lại và đạt. Đọc danh sách tiến trình sau test chỉ còn server demo và launcher của nó, không còn server scenario chạy sót.

## Chưa kiểm chứng / giới hạn

- Chưa kiểm tra trực quan trên điện thoại, Firefox, Safari hoặc mọi kích thước màn hình; CSS có breakpoint nhưng chưa là bằng chứng responsive toàn diện.
- Chưa kiểm thử mất điện/ổ đĩa hỏng thật, stress kéo dài, hàng triệu event hoặc nhiều server dùng chung SQLite. Kiểm thử crash hiện dùng kill tiến trình sau giao dịch HTTP đã commit và test rollback trước commit.
- Chưa đóng gói bộ cài độc lập hoặc wheel chứa config mặc định; hướng dẫn chính là editable source. Python 3.12/Windows là tổ hợp đã chạy; chưa kiểm chứng Python 3.11, Linux/macOS.
- Chưa có xác minh vật lý, dữ liệu máy thật, chứng nhận SECS/GEM/EDA hoặc yêu cầu Viettel. Không kết nối máy thật, không dùng dữ liệu EtchScope/BOSCH. Người dùng đã chỉ định công bố mã nguồn tới `https://github.com/thbn12082/FabScope`; dịch vụ demo vẫn chỉ chạy localhost.

## Tiếp tục sử dụng

Mở http://127.0.0.1:8770. Server demo đang chạy ở cuối phiên bàn giao, clock đã pause. Nếu server đã dừng, chạy lại lệnh trong README; trạng thái được khôi phục từ `runtime/manual.sqlite3`.

Lần yêu cầu restart server demo cuối phiên bị xét duyệt tự động chặn với lý do chung “blocked by policy”; không thử kênh khác để vượt chặn. Server demo cũ vẫn chạy các chức năng UI đã kiểm chứng. Trường chẩn đoán `process_id` vừa bổ sung ở `/health` sẽ có sau khi khởi động server mới; các tiến trình test mới đã dùng và kiểm chứng trường này.

Muốn session mới, dùng `--db runtime/session-moi.sqlite3`; không cần xóa journal cũ. Muốn xem bằng chứng, chạy lại scenarios hoặc mở `runtime/reports/` và [examples/reports](examples/reports/README.md).
