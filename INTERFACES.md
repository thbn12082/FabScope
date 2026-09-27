# Hợp đồng giao tiếp và dữ liệu

MVP dùng HTTP/JSON và polling sự kiện. Đây là giao diện thử nghiệm của FabScope, không phải SECS/GEM hoặc EDA. Không cần WebSocket/SSE để hoàn thành bản đầu.

**Đã triển khai trong v0.1.0:** giữ nguyên các route đề xuất bên dưới. OpenAPI có tại `/docs` khi chạy localhost.

`/health` có `process_id` của tiến trình thực sự phục vụ HTTP để kiểm chứng restart (phân biệt với launcher Python trên Windows).

## 1. Phân biệt hai mặt giao tiếp

- `/equipment/*`: phần mềm khách dùng để gửi lệnh, đọc trạng thái và đồng bộ sự kiện. Các lỗi mạng giả lập áp dụng tại đây.
- `/sim/*`: mặt điều khiển môi trường test và quan sát trạng thái bên trong. Dùng để advance clock, inject fault và xem ground truth; không đóng vai máy thật.

UI phải thể hiện rõ “trạng thái thật trong mô phỏng” và “trạng thái gần nhất khách nhận được”. Khi mất mạng, không dùng cổng observer để lặng lẽ cập nhật góc nhìn khách như thể kết nối vẫn tốt.

## 2. API tối thiểu

| API đề xuất | Hành vi |
|---|---|
| `GET /health` | Dịch vụ đang chạy; không đồng nghĩa đường giao tiếp máy đang thông |
| `POST /equipment/commands` | Nhận LOAD, START, UNLOAD, ABORT, CLEAR_FAULT |
| `GET /equipment/state` | Trạng thái mà khách đọc qua gateway |
| `GET /equipment/events?after_sequence=...&limit=...` | Đọc các event sau cursor, có phân trang |
| `GET /sim/state` | Trạng thái nội bộ, sim time, kết nối gateway, run hiện tại |
| `POST /sim/clock/advance` | Advance số giây mô phỏng không âm, hữu hạn |
| `POST /sim/faults` | Bật/tắt các lỗi mô phỏng đã định nghĩa |
| `GET /sim/runs` | Lịch sử run và trạng thái cuối |
| `POST /sim/scenarios/{scenario_id}/run` | Chạy một kịch bản trong session/database độc lập |
| `GET /sim/reports/{report_id}` | Báo cáo machine-readable và liên kết bản đọc được |

Có thể đổi tên route nếu có lý do kỹ thuật; giữ semantics và cập nhật tài liệu/test trong cùng thay đổi.

## 3. Envelope lệnh

```json
{
  "schema_version": "1.0",
  "command_id": "cmd-demo-002",
  "machine_id": "SIM-ETCH-01",
  "type": "START",
  "parameters": {
    "recipe_id": "DEMO_A",
    "recipe_version": "1"
  }
}
```

Kết quả có `command_id`, `accepted`, `code`, `message`, `run_id` khi liên quan và thời điểm mô phỏng xử lý lệnh. Phân biệt lỗi schema, machine không tồn tại, recipe không tồn tại, sai trạng thái và BUSY.

### Idempotency

- Khóa là `(machine_id, command_id)` và phải tồn tại qua restart.
- Cùng ID + cùng nội dung nghiệp vụ chuẩn hóa: trả lại kết quả nghiệp vụ đã lưu, không tạo run hoặc domain event lần nữa.
- Cùng ID + nội dung khác: trả `IDEMPOTENCY_CONFLICT`; không thực hiện lệnh mới.
- Kết quả từ chối nghiệp vụ cũng được lưu theo ID. Muốn thử một yêu cầu mới sau khi điều kiện đã thay đổi, khách dùng ID mới.
- Retry một START từng thành công vẫn trả đúng `run_id` cũ, kể cả máy hiện đã hoàn tất. Khách muốn trạng thái mới phải đọc state/events.
- Hai request đồng thời phải đi qua cơ chế serialize hoặc transaction đủ chặt để không tạo hai run trên một buồng.

## 4. Envelope sự kiện

```json
{
  "schema_version": "1.0",
  "event_id": "session-demo:17",
  "sequence": 17,
  "machine_id": "SIM-ETCH-01",
  "sim_time_s": 3.0,
  "type": "ProcessingStarted",
  "wafer_id": "W-DEMO-001",
  "run_id": "run-demo-001",
  "payload": {
    "state": "PROCESSING",
    "recipe_id": "DEMO_A",
    "recipe_version": "1"
  }
}
```

`sequence` tăng theo nhật ký của session/máy và được giữ qua restart; `event_id` không đổi khi truyền lại. Run ID duy nhất cho mỗi lần thực hiện. Một wafer chạy lại vẫn giữ wafer ID nhưng có run ID khác.

Danh mục tối thiểu: WaferLoaded, RunStarted, PreparationStarted, ProcessingStarted, TelemetrySampled, RunCompleted, RunAborted, MachineFaultRaised, FaultCleared, WaferUnloaded. Có thể gộp RunStarted/PreparationStarted nếu contract rõ và test thống nhất. Không phát một RunCompleted sau khi run đó đã ABORTED/FAILED.

Thời gian máy tính thực chỉ dùng cho log/audit; `sim_time_s` là cơ sở của domain. Kết quả tái hiện so sánh phần xác định, không so wall-clock hoặc ID session ngẫu nhiên giữa hai lần chạy.

## 5. Các lỗi gateway bắt buộc

1. **Disconnected:** request equipment không tới engine, trả lỗi kết nối mô phỏng/503. Engine vẫn tiến khi đồng hồ được advance hoặc chạy tự động.
2. **Lost acknowledgment once:** đúng một command được thực hiện/lưu kết quả, sau đó gateway trả lỗi thay vì phản hồi thành công. Retry cùng command ID phải lấy lại kết quả cũ.
3. **Duplicate delivery:** bản tin sự kiện có thể được giao lặp lại với cùng event ID. Client deduplicate; journal nguồn không tự tạo bản sao.

Không dùng lỗi 503 làm tín hiệu tự động gửi lại lệnh với command ID mới. Client giữ ID cho retry cùng yêu cầu. Không cần framework mạng phức tạp để mô phỏng ba lỗi này.

Sau reconnect, client dùng cursor liên tục đã xử lý để lấy bù các trang event. Không chỉ nhảy cursor đến event lớn nhất nếu vẫn còn lỗ hổng. Nếu buffer/retention không đủ để replay, phải trả tình trạng thiếu dữ liệu rõ ràng; MVP có thể giữ toàn bộ journal của session để tránh giới hạn này.

Lỗi machine fault khác lỗi gateway: machine fault có domain event và kết thúc run bằng FAILED; mất mạng không tự làm run FAILED.

## 6. Config và dữ liệu lưu

Config định nghĩa máy, recipes, seed, telemetry interval, chính sách gateway và các giả định. Lưu phiên bản hoặc hash config cùng session/report. MVP có thể không hỗ trợ đổi config trong lúc run đang hoạt động; khi phát hiện config khác lúc khôi phục, từ chối rõ thay vì tiếp tục bằng quy tắc mới.

SQLite lưu session metadata, machine state, command results/fingerprints, event journal, runs và clock/schedule. Giữ giao dịch cho thay đổi domain. Database lỗi phải báo lỗi, không tự xóa/reset để giả vờ phục hồi thành công.

Tách telemetry mô phỏng khỏi các kết luận sản phẩm: không thêm `wafer_pass`, `etch_depth_actual` hoặc nhãn vật lý không có mô hình kiểm chứng.

## 7. Chi tiết bản triển khai v0.1.0

- `POST /sim/clock/advance`: body `{"seconds": 3}`; giới hạn mỗi yêu cầu 0–86400 giây, số hữu hạn; độ phân giải clock 1 microsecond. Muốn đi xa hơn dùng nhiều yêu cầu. Schema sai trả HTTP 422 + `SCHEMA_ERROR`; không chấp nhận NaN/Infinity, số JSON overflow, boolean, string thay số, hoặc khóa JSON trùng.
- `POST /sim/clock/mode`: `{"playing": true}` hoặc `false`. Tick tự động 0.25 giây mô phỏng; chỉ là tốc độ demo, không cam kết thời gian thực. Advance thủ công khi play trả 409 + `detail.code=CLOCK_PLAYING`. Restart luôn pause; polling không làm tiến clock.
- `POST /sim/faults`: `{"type":"disconnected","enabled":true}`; các type khác là `lost_ack_once`, `duplicate_delivery`, `machine`. Lỗi máy có `reason`; chỉ xóa bằng CLEAR_FAULT qua equipment.
- Lỗi nghiệp vụ trả HTTP 200 với `accepted:false` và code; lỗi gateway trả 503 với `DISCONNECTED` hoặc `ACK_LOST`. Lost ack tiêu thụ đúng một command hợp lệ về schema, dù kết quả nghiệp vụ là accepted hay rejected; state/events không tiêu thụ cờ này.
- Parameters bắt buộc: LOAD dùng `wafer_id`; START dùng `recipe_id`, `recipe_version` (đều string); các lệnh khác dùng `{}`. Identifier 1–128 ký tự ASCII: chữ, số, `_ . : -`; không tự sửa identifier. Khóa không nhận diện bị từ chối.
- Page event tính `limit` theo số event nguồn duy nhất; khi duplicate delivery bật, mỗi event của trang được giao hai lần với nguyên ID. `next_cursor` và `has_more` dựa trên journal nguồn. Client chỉ tăng cursor khi đã nhận đủ sequence liên tục. MVP giữ toàn bộ journal.
- Nếu telemetry trùng mốc chuyển bước, chuyển bước trước rồi lấy mẫu trạng thái mới. Tại mốc hoàn tất, phát RunCompleted và hủy lịch; không phát thêm telemetry sau khi run kết thúc.
- `GET /sim/evidence` trả snapshot, commands, runs và toàn bộ events cho debug/báo cáo. UI dùng endpoint này cho nhật ký nguồn; không dùng nó để cập nhật góc nhìn khách.
- `GET /sim/scenarios` liệt kê A01–D02. `POST /sim/scenarios/all/run` chạy tất cả, trả mảng `reports`; mỗi scenario có process/SQLite riêng. Đây là tác vụ đồng bộ, có thể mất khoảng nửa phút trên máy phát triển.
- `GET /sim/reports/{report_id}` trả JSON; thêm `.html` để xem bản đọc được. Report ID là 32 ký tự hex. File lưu trong thư mục `--reports`.
- Một tiến trình server sở hữu một database; SQLite `BEGIN IMMEDIATE` serialize mọi thao tác trong tiến trình. Không chạy nhiều server với cùng database vì mỗi server có ticker riêng.
- Tên run/event chứa session UUID; UUID được lưu qua restart. So sánh tái hiện chỉ chuẩn hóa UUID, giữ nguyên thời gian, ordinal run và telemetry.
