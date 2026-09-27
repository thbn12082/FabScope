import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from fabscope.api import create_app
from fabscope.config import DEFAULT_CONFIG, load_config
from fabscope.domain import Engine, initial_state
from fabscope.scenarios.client import EquipmentClient
from fabscope.scenarios.evaluator import evaluate_normal
from fabscope.storage import Store


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "máy giả" / "session.sqlite3", report_dir=tmp_path / "reports")) as client:
        yield client


def cmd(kind, cid, parameters=None, machine="SIM-ETCH-01"):
    return dict(schema_version="1.0", command_id=cid, machine_id=machine, type=kind, parameters=parameters or {})


def start(cid="start"):
    return cmd("START", cid, {"recipe_id": "DEMO_A", "recipe_version": "1"})


def test_business_rejection_is_durable_and_retry_after_completion(client):
    first = client.post("/equipment/commands", json=start()).json()
    assert first["code"] == "INVALID_STATE"
    client.post("/equipment/commands", json=cmd("LOAD", "load", {"wafer_id": "W-001"}))
    assert client.post("/equipment/commands", json=start()).json() == first
    accepted = client.post("/equipment/commands", json=start("new-start")).json()
    client.post("/sim/clock/advance", json={"seconds": 100})
    before = client.get("/sim/evidence").json()
    assert client.post("/equipment/commands", json=start("new-start")).json() == accepted
    assert client.get("/sim/evidence").json() == before


@pytest.mark.parametrize("body", [
    {**start(), "schema_version": "2.0"}, {**start(), "extra": True},
    {**start(), "parameters": {"recipe_id": "DEMO_A"}},
    {**start(), "parameters": {"recipe_id": "DEMO_A", "recipe_version": 1}},
    {**start(), "command_id": ""}, {**start(), "type": "RESET"},
    cmd("LOAD", "load", {"wafer_id": ""}), cmd("LOAD", "load", {"wafer_id": "<script>"}),
    cmd("ABORT", "abort", {"unexpected": 5}),
])
def test_schema_rejections_leave_no_command_or_event(client, body):
    before = client.get("/sim/evidence").json()
    response = client.post("/equipment/commands", json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "SCHEMA_ERROR"
    assert client.get("/sim/evidence").json() == before


@pytest.mark.parametrize("raw", ['{"seconds":true}', '{"seconds":"1"}', '{"seconds":1,"seconds":2}', '{"seconds":NaN}', '{"seconds":-Infinity}', '{"seconds":1e999}', '{"seconds":-0.5}'])
def test_strict_json_and_finite_clock(client, raw):
    response = client.post("/sim/clock/advance", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert client.get("/sim/state").json()["sim_time_s"] == 0


def test_machine_not_found_and_disconnected_do_not_execute(client):
    result = client.post("/equipment/commands", json=cmd("LOAD", "unknown", {"wafer_id": "W"}, "MISSING")).json()
    assert result["code"] == "MACHINE_NOT_FOUND"
    before = client.get("/sim/evidence").json()
    client.post("/sim/faults", json={"type": "disconnected"})
    assert client.get("/health").status_code == 200
    assert client.post("/equipment/commands", json=cmd("LOAD", "valid", {"wafer_id": "W"})).status_code == 503
    after = client.get("/sim/evidence").json()
    assert before["events"] == after["events"] == []
    assert before["commands"] == after["commands"]
    assert after["state"]["state"] == "EMPTY"


def test_manual_clock_rejected_when_playing(client):
    client.post("/sim/clock/mode", json={"playing": True})
    response = client.post("/sim/clock/advance", json={"seconds": 10})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CLOCK_PLAYING"
    client.post("/sim/clock/mode", json={"playing": False})
    before = client.get("/sim/state").json()["sim_time_s"]
    assert client.post("/sim/clock/advance", json={"seconds": 1}).json()["sim_time_s"] == before + 1


def test_concurrent_advances_are_serialized(client):
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: client.post("/sim/clock/advance", json={"seconds": 0.1}).status_code, range(20)))
    assert results == [200] * 20
    assert client.get("/sim/state").json()["sim_time_s"] == 2


def test_config_mismatch_and_corrupt_db_are_not_reset(tmp_path):
    config, digest = load_config()
    path = tmp_path / "session.sqlite3"
    store = Store(path, config, digest)
    store.transact(lambda e, f, db: e.advance(5))
    with pytest.raises(ValueError, match="CONFIG_MISMATCH"):
        Store(path, config, "different")
    assert Store(path, config, digest).evidence()["state"]["sim_time_s"] == 5
    broken = tmp_path / "corrupt.sqlite3"
    broken.write_bytes(b"not a database")
    with pytest.raises(sqlite3.DatabaseError):
        Store(broken, config, digest)
    assert broken.read_bytes() == b"not a database"


def test_transaction_rolls_back_all_domain_changes(tmp_path):
    config, digest = load_config()
    store = Store(tmp_path / "rollback.sqlite3", config, digest)
    before = store.evidence()
    def broken(engine, flags, db):
        store.command(cmd("LOAD", "load", {"wafer_id": "W"}), engine, db)
        raise RuntimeError("Simulated persistence failure before commit")
    with pytest.raises(RuntimeError):
        store.transact(broken)
    assert store.evidence() == before


def test_client_never_skips_gap_or_reapplies_duplicates():
    client = EquipmentClient(None)
    events = [{"event_id": f"session:{i}", "sequence": i} for i in (1, 2, 3)]
    client.apply([events[2], events[0], events[0]])
    assert client.cursor == 1
    assert len(client.applied) == 1
    client.apply([events[1], events[2]])
    assert client.cursor == 3
    assert client.applied == events


def test_domain_large_advance_has_exact_deadlines_and_terminal_cancellation():
    config, _ = load_config()
    engine = Engine(config, "unit", initial_state(), {})
    engine.command(cmd("LOAD", "load", {"wafer_id": "W"}))
    engine.command(start())
    engine.advance(8)
    assert engine.state["state"] == "PROCESSING"
    assert [(e["type"], e["sim_time_s"]) for e in engine.events if e["type"] == "ProcessingStarted"] == [("ProcessingStarted", 3.0)]
    assert engine.state["signals"]["step_progress_pct"] == 50
    engine.command(cmd("ABORT", "abort"))
    engine.advance(100)
    assert engine.state["telemetry_at"] is None
    assert engine.state["transition_at"] is None
    assert not any(e["type"] == "RunCompleted" for e in engine.events)


def test_report_oracle_fails_empty_trace_and_extra_run():
    assert not evaluate_normal({"events": [], "runs": []})


def test_report_path_cannot_escape_directory(client):
    assert client.get("/sim/reports/not-a-report").status_code == 404
    assert client.post("/sim/scenarios/not-a-scenario/run").status_code == 404
