import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from .. import NOTICE, __version__
from ..config import load_config
from .client import EquipmentClient, Server
from .evaluator import evaluate_normal, normal_run_checks, normalized
from .reporting import save_report

CATALOG = {
    "A01": "Một lượt chạy bình thường", "A02": "Từ chối lệnh và thời gian không hợp lệ",
    "A03": "ABORT hủy lịch cũ", "A04": "Lỗi máy và xử lý lỗi", "A05": "Chạy lại cùng wafer",
    "B01": "Mất phản hồi START rồi gửi lại", "B02": "ID cũ, nội dung khác",
    "B03": "Mất kết nối khi đang chạy", "B04": "Sự kiện lặp và phân trang", "B05": "Hai START đồng thời",
    "C01": "Restart giữa lượt chạy (tiến trình thật)", "C02": "Restart sau mất phản hồi",
    "C03": "Clock và seed tái hiện được", "C04": "Restart khác mất kết nối", "C05": "Kịch bản chạy độc lập",
    "D01": "Báo cáo phát hiện cả trace sai", "D02": "Hợp đồng UI và góc nhìn khách",
}


class Scenario:
    def __init__(self, server, report, config):
        self.server, self.report, self.config = server, report, config
        self.counter = 0
        recipe = next(r for r in config["recipes"] if (r["recipe_id"], r["recipe_version"]) == ("DEMO_A", "1"))
        self.prepare, self.process = recipe["prepare_s"], recipe["process_s"]

    def request(self, method, path, body=None, raw=None):
        kwargs = {"content": raw, "headers": {"Content-Type": "application/json"}} if raw is not None else ({"json": body} if body is not None else {})
        response = self.server.client.request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = response.text
        self.report["steps"].append(dict(method=method, path=path, request=body if raw is None else raw,
                                          http_status=response.status_code, actual=data))
        return response.status_code, data

    def get(self, path):
        status, data = self.request("GET", path)
        if status != 200:
            raise RuntimeError(f"GET {path}: HTTP {status}")
        return data

    def post(self, path, body):
        return self.request("POST", path, body)[1]

    def command_body(self, kind, parameters=None, cid=None):
        self.counter += 1
        return dict(schema_version="1.0", machine_id=self.config["machine_id"],
                    command_id=cid or f"cmd-{self.counter:04d}", type=kind, parameters=parameters or {})

    def command(self, kind, parameters=None, cid=None):
        return self.post("/equipment/commands", self.command_body(kind, parameters, cid))

    def load(self):
        return self.command("LOAD", {"wafer_id": "W-DEMO-001"})

    def start(self, cid=None):
        return self.command("START", {"recipe_id": "DEMO_A", "recipe_version": "1"}, cid)

    def advance(self, seconds):
        return self.post("/sim/clock/advance", {"seconds": seconds})

    def fault(self, kind, enabled=True):
        return self.post("/sim/faults", {"type": kind, "enabled": enabled, "reason": "Lỗi giả định để kiểm thử"})

    def evidence(self, label="final"):
        value = self.get("/sim/evidence")
        self.report["evidence"][label] = value
        return value

    def check(self, name, expected, actual):
        self.report["checks"].append(dict(name=name, expected=expected, actual=actual,
                                         status="PASS" if expected == actual else "FAIL"))

    def normal(self):
        states = [self.get("/equipment/state")["state"]]
        self.load()
        states.append(self.get("/equipment/state")["state"])
        self.start()
        states.append(self.get("/equipment/state")["state"])
        states.append(self.advance(self.prepare)["state"])
        states.append(self.advance(self.process)["state"])
        self.command("UNLOAD")
        states.append(self.get("/equipment/state")["state"])
        self.check("Chuỗi trạng thái", ["EMPTY", "LOADED", "PREPARING", "PROCESSING", "COMPLETED", "EMPTY"], states)
        trace = self.evidence()
        for name, expected, actual in normal_run_checks(trace):
            self.check(name, expected, actual)
        return trace

    def restart(self):
        before = self.server.process.pid
        old_server_pid = self.server.server_pid
        self.server.restart()
        after = self.server.process.pid
        self.report["steps"].append(dict(action="kill_and_restart_real_server", old_launcher_pid=before,
            new_launcher_pid=after, old_server_pid=old_server_pid, new_server_pid=self.server.server_pid,
            old_http_service_stopped=True))
        self.check("Server được thay bằng tiến trình mới", True, before != after)
        self.check("PID phục vụ HTTP thực sự thay đổi", True, old_server_pid != self.server.server_pid)


def execute(sid, s):
    if sid in {"A01", "D01"}:
        trace = s.normal()
        if sid == "D01":
            missing = copy.deepcopy(trace)
            missing["events"] = [e for e in missing["events"] if e["type"] != "RunCompleted"]
            duplicate = copy.deepcopy(trace)
            duplicate["runs"].append({**duplicate["runs"][0], "run_id": "injected-wrong-run"})
            s.check("Oracle từ chối trace thiếu RunCompleted", False, evaluate_normal(missing))
            s.check("Oracle từ chối hai run cho một START", False, evaluate_normal(duplicate))
            s.report["evidence"].update(negative_missing_completion=missing, negative_duplicate_run=duplicate)
    elif sid == "A02":
        before = s.evidence("empty")
        s.check("START khi EMPTY", "INVALID_STATE", s.start()["code"])
        s.check("Lệnh sai không đổi domain", before, {**s.evidence("rejected"), "commands": before["commands"]})
        s.load()
        s.check("Không LOAD đè", "INVALID_STATE", s.load()["code"])
        s.check("Recipe không tồn tại", "RECIPE_NOT_FOUND", s.command("START", {"recipe_id": "UNKNOWN", "recipe_version": "1"})["code"])
        s.start()
        s.advance(s.prepare)
        s.check("UNLOAD khi PROCESSING", "INVALID_STATE", s.command("UNLOAD")["code"])
        before = s.evidence("before_bad_time")
        for raw in ('{"seconds":-1}', '{"seconds":NaN}', '{"seconds":Infinity}', '{"seconds":1e999}', '{bad json}'):
            status, data = s.request("POST", "/sim/clock/advance", raw=raw)
            s.check(f"Từ chối {raw}", [422, "SCHEMA_ERROR"], [status, data["code"]])
        s.check("Yêu cầu sai không làm tiến clock/domain", before, s.evidence())
    elif sid in {"A03", "A04"}:
        s.load()
        old = s.start()["run_id"]
        s.advance(s.prepare + 1)
        if sid == "A03":
            s.command("ABORT")
        else:
            s.fault("machine")
            s.check("Lỗi máy đưa về FAULT", "FAULT", s.get("/sim/state")["state"])
            s.command("CLEAR_FAULT")
        s.advance(100)
        trace = s.evidence("after_cancel")
        s.check("Giữ wafer và không tự chạy lại", ["LOADED", "W-DEMO-001"], [trace["state"]["state"], trace["state"]["wafer_id"]])
        s.check("Trạng thái cuối run cũ", "ABORTED" if sid == "A03" else "FAILED", trace["runs"][0]["status"])
        s.check("Không có hoàn tất muộn", 0, sum(e["type"] == "RunCompleted" for e in trace["events"]))
        if sid == "A04":
            s.check("Lưu lý do lỗi máy", "Lỗi giả định để kiểm thử", trace["runs"][0]["reason"])
        new = s.start()["run_id"]
        s.check("START mới có run ID khác", True, old != new)
        s.advance(s.prepare + s.process)
        s.check("Run mới hoàn thành", ["ABORTED" if sid == "A03" else "FAILED", "COMPLETED"], [r["status"] for r in s.evidence()["runs"]])
    elif sid == "A05":
        s.normal()
        s.load()
        s.start()
        s.advance(s.prepare + s.process)
        trace = s.evidence()
        s.check("Hai run cùng wafer", ["W-DEMO-001"] * 2, [r["wafer_id"] for r in trace["runs"]])
        s.check("Hai run ID riêng biệt", 2, len({r["run_id"] for r in trace["runs"]}))
        s.check("Mỗi run đúng một hoàn tất", [1, 1], [sum(e["type"] == "RunCompleted" and e["run_id"] == r["run_id"] for e in trace["events"]) for r in trace["runs"]])
        s.check("Telemetry gắn đúng run và wafer", True, all(e["run_id"] in {r["run_id"] for r in trace["runs"]} and e["wafer_id"] == "W-DEMO-001" for e in trace["events"] if e["type"] == "TelemetrySampled"))
    elif sid in {"B01", "C02"}:
        s.load()
        s.fault("lost_ack_once")
        body = s.command_body("START", {"recipe_id": "DEMO_A", "recipe_version": "1"}, "lost-start")
        status, response = s.request("POST", "/equipment/commands", body)
        s.check("Khách không nhận ack", [503, "ACK_LOST"], [status, response["code"]])
        accepted = s.evidence("before_retry")
        s.check("START đã được ghi dù mất phản hồi", [1, True], [len(accepted["runs"]), accepted["commands"][-1]["result"]["accepted"]])
        if sid == "C02":
            s.restart()
        retry = s.post("/equipment/commands", body)
        s.check("Retry nhận nguyên kết quả lưu", accepted["commands"][-1]["result"], retry)
        s.check("Retry không đổi journal hay run", accepted, s.evidence())
    elif sid == "B02":
        original = s.load()
        body = s.command_body("LOAD", {"wafer_id": "OTHER-WAFER"}, original["command_id"])
        s.check("Cùng ID khác payload", "IDEMPOTENCY_CONFLICT", s.post("/equipment/commands", body)["code"])
        start = s.start("same-start")
        reordered = {"parameters": {"recipe_version": "1", "recipe_id": "DEMO_A"}, "type": "START", "command_id": "same-start", "machine_id": s.config["machine_id"], "schema_version": "1.0"}
        before = s.evidence("before_retry")
        s.check("Thứ tự khóa JSON không ảnh hưởng", start, s.post("/equipment/commands", reordered))
        s.check("Không đổi domain/journal", before, s.evidence())
    elif sid in {"B03", "B04"}:
        s.load()
        s.start()
        client = EquipmentClient(s.server)
        client.refresh()
        client.sync(limit=1)
        old_cursor, old_state = client.cursor, client.last_state.copy()
        if sid == "B03":
            s.fault("disconnected")
            s.advance(s.prepare + s.process)
            s.check("Observer vẫn thấy hoàn tất", "COMPLETED", s.get("/sim/state")["state"])
            s.check("Khách báo mất kết nối", 503, client.refresh().status_code)
            s.check("Góc nhìn khách cũ được giữ nguyên", [True, old_state], [client.stale, client.last_state])
            s.check("Request không tới engine khi disconnect", "DISCONNECTED", s.command("ABORT")["code"])
            s.fault("disconnected", False)
        else:
            s.fault("duplicate_delivery")
            s.advance(s.prepare + s.process)
        page = s.get(f"/equipment/events?after_sequence=0&limit=2")
        client.apply(page["events"])
        client.sync(limit=2)
        client.refresh()
        trace = s.evidence()
        s.report["evidence"]["client"] = {"cursor_before": old_cursor, "cursor_after": client.cursor, "received": client.received, "applied": client.applied, "last_state": client.last_state}
        s.check("Replay đầy đủ và đúng thứ tự", trace["events"], client.applied)
        s.check("Cursor liên tục đến cuối", trace["state"]["sequence"], client.cursor)
        s.check("Mỗi event chỉ áp dụng một lần", len(client.applied), len(client.seen))
        s.check("Khách đã đồng bộ COMPLETED", [False, "COMPLETED"], [client.stale, client.last_state["state"]])
        s.check("Một run duy nhất", 1, len(trace["runs"]))
        if sid == "B04":
            s.check("Có giao lặp thực sự", True, client.received > len(client.applied))
    elif sid == "B05":
        for same in (True, False):
            with Server(s.server.directory / ("same" if same else "different"), s.server.config_path) as server:
                child = Scenario(server, s.report, s.config)
                child.load()
                bodies = [child.command_body("START", {"recipe_id": "DEMO_A", "recipe_version": "1"}, "parallel" if same else f"parallel-{i}") for i in range(2)]
                barrier = Barrier(2)
                def send(body):
                    barrier.wait(timeout=5)
                    return child.post("/equipment/commands", body)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(send, bodies))
                s.check(f"START đồng thời, same ID={same}", ["OK", "OK"] if same else ["BUSY", "OK"], sorted(r["code"] for r in results))
                if same:
                    s.check("Cùng ID cùng run", results[0]["run_id"], results[1]["run_id"])
                s.check("Chỉ một run trong buồng", 1, len(child.evidence(f"parallel_{same}")["runs"]))
    elif sid in {"C01", "C04"}:
        s.load()
        old = s.start("restart-start")
        s.advance(s.prepare + 2)
        before = s.evidence("before_restart")
        s.restart()
        s.check("Phục hồi nguyên state, clock, schedule, journal", before, s.evidence("after_restart"))
        s.check("Retry START cũ qua restart", old, s.start("restart-start"))
        if sid == "C04":
            s.fault("disconnected")
        s.advance(s.process - 2)
        trace = s.evidence()
        s.check("Hoàn tất đúng một lần", ["COMPLETED", 1, 1], [trace["state"]["state"], len(trace["runs"]), sum(e["type"] == "RunCompleted" for e in trace["events"])])
        s.check("Thời gian không tính bù wall-clock", s.prepare + s.process, trace["state"]["sim_time_s"])
        if sid == "C04":
            s.check("Disconnect chỉ chặn gateway", 503, s.request("GET", "/equipment/state")[0])
            s.report["limits"] += " Restart dừng clock tại mốc lưu; disconnect vẫn cho clock tiến qua cổng simulator."
    elif sid == "C03":
        traces = []
        for label, increments in [("large", [s.prepare + s.process]), ("small", [1] * int(s.prepare + s.process)), ("repeat", [s.prepare + s.process])]:
            with Server(s.server.directory / label, s.server.config_path) as server:
                child = Scenario(server, s.report, s.config)
                child.load()
                child.start()
                for seconds in increments:
                    child.advance(seconds)
                traces.append(normalized(child.evidence(label)))
        s.check("Advance lớn bằng nhiều bước nhỏ", traces[0], traces[1])
        s.check("Cùng config/seed tái hiện cùng dữ liệu", traces[0], traces[2])
        s.check("Không bỏ qua ProcessingStarted", [s.prepare], [e["sim_time_s"] for e in traces[0]["events"] if e["type"] == "ProcessingStarted"])
        s.check("Hoàn tất tại đúng deadline", [s.prepare + s.process], [e["sim_time_s"] for e in traces[0]["events"] if e["type"] == "RunCompleted"])
        interval = s.config["telemetry_interval_s"]
        expected = [round(i * interval, 6) for i in range(1, int((s.prepare + s.process) / interval) + 1) if i * interval < s.prepare + s.process]
        s.check("Đủ các mốc telemetry trước kết thúc", expected, [e["sim_time_s"] for e in traces[0]["events"] if e["type"] == "TelemetrySampled"])
    elif sid == "C05":
        s.load()
        s.start()
        s.advance(s.prepare + 1)
        before = s.evidence("manual_before")
        result = s.post("/sim/scenarios/A01/run", {})["reports"][0]
        s.check("Kịch bản con đạt", "PASS", result["status"])
        s.check("Session con khác manual", True, result["session_id"] != before["state"]["session_id"])
        s.check("Config kịch bản được ghi đúng", s.report["config_hash"], result["config_hash"])
        s.check("Không thay đổi run manual", before, s.evidence("manual_after"))
        stored = s.get(f"/sim/reports/{result['report_id']}")
        s.check("Báo cáo JSON lưu và đọc lại được", result["report_id"], stored["report_id"])
        status, page = s.request("GET", f"/sim/reports/{result['report_id']}.html")
        s.check("Báo cáo HTML có bằng chứng", [200, True], [status, "RunCompleted" in page])
    elif sid == "D02":
        status, page = s.request("GET", "/")
        s.check("UI được server phục vụ", 200, status)
        s.check("UI nhận diện dữ liệu giả định", True, NOTICE in page)
        s.check("UI phân biệt observer và client", True, "Trạng thái thật trong mô phỏng" in page and "Trạng thái gần nhất khách nhận" in page)
        s.load()
        client = EquipmentClient(s.server)
        client.refresh()
        s.fault("lost_ack_once")
        s.check("Mất ack được báo", "ACK_LOST", s.start("ui-start")["code"])
        s.check("Retry giữ ID nhận kết quả", True, s.start("ui-start")["accepted"])
        s.advance(s.prepare)
        client.refresh()
        s.fault("disconnected")
        s.advance(1)
        client.refresh()
        s.check("Client giữ trạng thái cũ và cờ stale", [True, s.prepare], [client.stale, client.last_state["sim_time_s"]])
        s.fault("machine")
        s.check("Observer thấy FAULT trong khi khách stale", ["FAULT", "PROCESSING"], [s.get("/sim/state")["state"], client.last_state["state"]])
        s.fault("disconnected", False)
        client.refresh()
        s.check("Reconnect đồng bộ lại FAULT", [False, "FAULT"], [client.stale, client.last_state["state"]])
        s.evidence()
        s.report["limits"] += " D02 tự động kiểm tra HTTP/assets và client headless; không thay thế thao tác/kiểm tra trực quan bằng trình duyệt."


def run_scenario(scenario_id, config_path, output_dir):
    config, config_hash = load_config(config_path)
    report_id = uuid.uuid4().hex
    output = Path(output_dir).resolve()
    directory = output / "sessions" / report_id
    report = dict(report_id=report_id, scenario_id=scenario_id, name=CATALOG[scenario_id],
        software_version=__version__, config_version=config["config_version"], config_hash=config_hash,
        seed=config["seed"], session_id=None, simulation_notice=NOTICE, config=config,
        steps=[], checks=[], evidence={}, status="FAIL",
        limits="Chỉ kiểm thử hành vi phần mềm theo cấu hình giả định. Không chứng nhận máy thật, vật lý khắc, SECS/GEM/EDA hoặc yêu cầu Viettel.",
        html_url=f"/sim/reports/{report_id}.html", json_url=f"/sim/reports/{report_id}")
    try:
        with Server(directory, config_path) as server:
            scenario = Scenario(server, report, config)
            report["session_id"] = scenario.get("/sim/state")["session_id"]
            execute(scenario_id, scenario)
            report["process_ids"] = server.pids
    except Exception as exc:
        # No stack paths or user-specific locations in exported reports.
        report["checks"].append(dict(name="Scenario thực thi đầy đủ", expected="Không có lỗi thực thi",
            actual=type(exc).__name__, status="FAIL"))
        (directory / "error.txt").write_text(str(exc), encoding="utf-8")
    report["status"] = "PASS" if report["checks"] and all(c["status"] == "PASS" for c in report["checks"]) else "FAIL"
    save_report(report, output)
    return report
