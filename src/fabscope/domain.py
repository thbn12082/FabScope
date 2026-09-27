"""Deterministic equipment model. No HTTP, SQLite or wall clock dependencies."""
import hashlib


ACTIVE = {"PREPARING", "PROCESSING"}


def initial_state():
    return dict(state="EMPTY", wafer_id=None, run_id=None, sim_time_s=0.0,
                transition_at=None, telemetry_at=None, run_counter=0,
                sequence=0, signals={"demo_process_level": 0, "step_progress_pct": 0})


class Engine:
    def __init__(self, config, session_id, state, runs):
        self.config, self.session_id, self.state, self.runs = config, session_id, state, runs
        self.events = []

    def emit(self, kind, **payload):
        s = self.state
        s["sequence"] += 1
        event = dict(schema_version="1.0", event_id=f"{self.session_id}:{s['sequence']}",
                     sequence=s["sequence"], machine_id=self.config["machine_id"],
                     sim_time_s=s["sim_time_s"], type=kind, wafer_id=s["wafer_id"],
                     run_id=s["run_id"], payload={"state": s["state"], **payload})
        self.events.append(event)

    def result(self, command, accepted, code, message, run_id=None):
        return dict(command_id=command["command_id"], accepted=accepted, code=code,
                    message=message, run_id=run_id, sim_time_s=self.state["sim_time_s"])

    def command(self, command):
        s, kind, p = self.state, command["type"], command["parameters"]
        def no(code, message):
            return self.result(command, False, code, message, s["run_id"])
        if command["machine_id"] != self.config["machine_id"]:
            return no("MACHINE_NOT_FOUND", "Không có máy mô phỏng này.")
        if kind == "START":
            if s["state"] in ACTIVE:
                return no("BUSY", "Buồng đang có lượt chạy hoạt động.")
            if s["state"] != "LOADED":
                return no("INVALID_STATE", "START cần máy ở LOADED.")
            recipe = next((r for r in self.config["recipes"] if
                           (r["recipe_id"], r["recipe_version"]) ==
                           (p["recipe_id"], p["recipe_version"])), None)
            if recipe is None:
                return no("RECIPE_NOT_FOUND", "Recipe/version giả định không tồn tại.")
            s["run_counter"] += 1
            s["run_id"] = f"{self.session_id}:run-{s['run_counter']:04d}"
            self.runs[s["run_id"]] = dict(run_id=s["run_id"], wafer_id=s["wafer_id"],
                recipe_id=recipe["recipe_id"], recipe_version=recipe["recipe_version"],
                status="RUNNING", started_at=s["sim_time_s"], ended_at=None, reason=None,
                prepare_s=recipe["prepare_s"], process_s=recipe["process_s"], demo_level=recipe["demo_level"])
            s.update(state="PREPARING", transition_at=round(s["sim_time_s"] + recipe["prepare_s"], 6),
                     telemetry_at=round(s["sim_time_s"] + self.config["telemetry_interval_s"], 6))
            self.emit("RunStarted", recipe_id=recipe["recipe_id"], recipe_version=recipe["recipe_version"])
            self.emit("PreparationStarted")
        elif kind == "LOAD":
            if s["state"] != "EMPTY":
                return no("INVALID_STATE", "LOAD cần buồng trống; không thể nạp đè wafer.")
            s.update(state="LOADED", wafer_id=p["wafer_id"], run_id=None)
            self.emit("WaferLoaded")
        elif kind == "UNLOAD":
            if s["state"] not in {"LOADED", "COMPLETED"}:
                return no("INVALID_STATE", "UNLOAD chỉ dùng khi LOADED hoặc COMPLETED.")
            s["state"] = "EMPTY"
            self.emit("WaferUnloaded")
            s.update(wafer_id=None, run_id=None)
        elif kind == "ABORT":
            if s["state"] not in ACTIVE:
                return no("INVALID_STATE", "Không có lượt chạy để dừng.")
            self.finish("ABORTED", "LOADED", "RunAborted", "Người dùng dừng simulator")
        elif kind == "CLEAR_FAULT":
            if s["state"] != "FAULT":
                return no("INVALID_STATE", "Máy không có lỗi mô phỏng cần xóa.")
            s["state"] = "LOADED"
            self.emit("FaultCleared")
        self.update_signals()
        return self.result(command, True, "OK", "Đã thực hiện trong simulator.", s["run_id"])

    def finish(self, status, machine_state, event, reason=None):
        s = self.state
        self.runs[s["run_id"]].update(status=status, ended_at=s["sim_time_s"], reason=reason)
        s.update(state=machine_state, transition_at=None, telemetry_at=None)
        self.emit(event, reason=reason)

    def fault(self, reason):
        if self.state["state"] not in ACTIVE:
            return {"accepted": False, "code": "INVALID_STATE", "message": "Chỉ tạo lỗi máy khi đang chạy."}
        self.finish("FAILED", "FAULT", "MachineFaultRaised", reason)
        self.update_signals()
        return {"accepted": True, "code": "OK"}

    def update_signals(self):
        s = self.state
        progress, level = 0.0, 0.0
        if s["state"] in ACTIVE:
            run = self.runs[s["run_id"]]
            duration = run["prepare_s"] if s["state"] == "PREPARING" else run["process_s"]
            progress = max(0, min(100, 100 * (1 - (s["transition_at"] - s["sim_time_s"]) / duration)))
            # Stable noise uses seed + run ordinal + sim time, never session UUID or wall time.
            key = f"{self.config['seed']}:{s['run_counter']}:{s['sim_time_s']:.6f}"
            noise = (int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 201 - 100) / 100
            level = (10 + progress / 10 if s["state"] == "PREPARING" else run["demo_level"] + progress / 10) + noise
        elif s["state"] == "COMPLETED":
            progress = 100.0
        s["signals"] = {"demo_process_level": round(level, 3), "step_progress_pct": round(progress, 3)}

    def advance(self, seconds):
        s = self.state
        target = round(s["sim_time_s"] + seconds, 6)
        while s["state"] in ACTIVE:
            due = min(s["transition_at"], s["telemetry_at"])
            if due > target:
                break
            s["sim_time_s"] = due
            if s["transition_at"] == due:
                if s["state"] == "PREPARING":
                    s["state"] = "PROCESSING"
                    s["transition_at"] = round(due + self.runs[s["run_id"]]["process_s"], 6)
                    self.emit("ProcessingStarted")
                else:
                    self.finish("COMPLETED", "COMPLETED", "RunCompleted")
            self.update_signals()
            if s["telemetry_at"] == due:
                self.emit("TelemetrySampled", **s["signals"])
                s["telemetry_at"] = round(due + self.config["telemetry_interval_s"], 6)
        s["sim_time_s"] = target
        self.update_signals()
        return self.view()

    def view(self):
        return {**self.state, "machine_id": self.config["machine_id"], "session_id": self.session_id,
                "current_run": self.runs.get(self.state["run_id"]),
                "simulation_notice": self.config["simulation_notice"]}
