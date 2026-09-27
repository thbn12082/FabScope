import asyncio
import json
import math
import os
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import NOTICE, __version__
from .config import DEFAULT_CONFIG, load_config
from .gateway import Gateway, GatewayError
from .storage import Store


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Command(StrictModel):
    schema_version: Literal["1.0"]
    command_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    machine_id: str = Field(min_length=1, max_length=128)
    type: Literal["LOAD", "START", "UNLOAD", "ABORT", "CLEAR_FAULT"]
    parameters: dict

    @field_validator("parameters")
    @classmethod
    def parameters_match(cls, value, info):
        keys = {"LOAD": {"wafer_id"}, "START": {"recipe_id", "recipe_version"}}.get(info.data.get("type"), set())
        if set(value) != keys or any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", v) for v in value.values()):
            raise ValueError("Parameters must match the command, with non-empty identifier strings")
        return value


class Advance(StrictModel):
    seconds: float = Field(ge=0, le=86400, allow_inf_nan=False)


class Fault(StrictModel):
    type: Literal["disconnected", "lost_ack_once", "duplicate_delivery", "machine"]
    enabled: bool = True
    reason: str = Field(default="Lỗi máy giả lập do người dùng tạo", min_length=1, max_length=500)


class ClockMode(StrictModel):
    playing: bool


def create_app(db_path="runtime/manual.sqlite3", config_path=DEFAULT_CONFIG, report_dir="runtime/reports"):
    config, config_hash = load_config(config_path)
    store = Store(db_path, config, config_hash)
    gateway = Gateway(store)
    reports = Path(report_dir).resolve()
    reports.mkdir(parents=True, exist_ok=True)

    async def ticker():
        while True:
            await asyncio.sleep(0.25)
            await asyncio.to_thread(store.transact, lambda e, f, db: e.advance(0.25) if f["playing"] else None)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(ticker())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="FabScope Simulator — dữ liệu giả định", version=__version__, lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def strict_json(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if body:
                def invalid(value):
                    raise ValueError("Non-finite JSON number")
                def unique(pairs):
                    obj = {}
                    for key, value in pairs:
                        if key in obj:
                            raise ValueError("Duplicate JSON key")
                        obj[key] = value
                    return obj
                def finite_float(value):
                    number = float(value)
                    if not math.isfinite(number):
                        raise ValueError("Non-finite JSON number")
                    return number
                try:
                    json.loads(body, parse_constant=invalid, parse_float=finite_float, object_pairs_hook=unique)
                except (ValueError, UnicodeDecodeError):
                    return JSONResponse(status_code=422, content={"code": "SCHEMA_ERROR", "message": "JSON không hợp lệ hoặc số không hữu hạn."})
        response = await call_next(request)
        response.headers["X-FabScope-Data"] = "simulated-assumed-config"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"code": "SCHEMA_ERROR", "message": "Yêu cầu sai schema.",
            "details": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]})

    @app.exception_handler(GatewayError)
    async def gateway_error(request, exc):
        return JSONResponse(status_code=503, content={"code": exc.code, "message": exc.message, "simulation_notice": NOTICE})

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "process_id": os.getpid(), "simulation_notice": NOTICE}

    @app.post("/equipment/commands")
    def command(body: Command):
        return gateway.command(body.model_dump())

    @app.get("/equipment/state")
    def state():
        return gateway.state()

    @app.get("/equipment/events")
    def events(after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
        return gateway.events(after_sequence, limit)

    @app.get("/sim/state")
    def observer():
        return store.transact(lambda e, f, db: {**e.view(), "gateway": f, "config_hash": config_hash, "config": config})

    @app.post("/sim/clock/advance")
    def advance(body: Advance):
        def apply(e, f, db):
            if f["playing"]:
                raise HTTPException(409, detail={"code": "CLOCK_PLAYING", "message": "Pause trước khi advance thủ công."})
            return e.advance(body.seconds)
        return store.transact(apply)

    @app.post("/sim/clock/mode")
    def mode(body: ClockMode):
        def apply(e, f, db):
            f["playing"] = body.playing
            return {"playing": f["playing"], "sim_time_s": e.state["sim_time_s"]}
        return store.transact(apply)

    @app.post("/sim/faults")
    def fault(body: Fault):
        def apply(e, f, db):
            if body.type == "machine":
                return e.fault(body.reason) if body.enabled else {"accepted": False, "code": "USE_CLEAR_FAULT"}
            f[body.type] = body.enabled
            return {"accepted": True, "gateway": f}
        return store.transact(apply)

    @app.get("/sim/runs")
    def runs():
        return store.transact(lambda e, f, db: {"runs": list(e.runs.values()), "simulation_notice": NOTICE})

    @app.get("/sim/evidence")
    def evidence():
        return store.evidence()

    @app.get("/sim/scenarios")
    def scenarios():
        from .scenarios.runner import CATALOG
        return {"scenarios": [{"id": sid, "name": name} for sid, name in CATALOG.items()], "simulation_notice": NOTICE}

    @app.post("/sim/scenarios/{scenario_id}/run")
    def scenario(scenario_id: str):
        from .scenarios.runner import CATALOG, run_scenario
        if scenario_id not in CATALOG and scenario_id != "all":
            raise HTTPException(404, "Unknown scenario")
        ids = list(CATALOG) if scenario_id == "all" else [scenario_id]
        return {"reports": [run_scenario(sid, Path(config_path), reports) for sid in ids], "simulation_notice": NOTICE}

    @app.get("/sim/reports/{report_id}")
    def report(report_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}(\.html)?", report_id):
            raise HTTPException(404, "Report not found")
        target = reports / (report_id if report_id.endswith(".html") else report_id + ".json")
        if not target.is_file():
            raise HTTPException(404, "Report not found")
        return FileResponse(target)

    ui = Path(__file__).parent / "ui"
    if ui.exists():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")
    return app
