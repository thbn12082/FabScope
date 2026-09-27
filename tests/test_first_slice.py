from fastapi.testclient import TestClient

from fabscope.api import create_app


def test_normal_run_through_api_and_journal(tmp_path):
    app = create_app(tmp_path / "simulation.sqlite3", report_dir=tmp_path / "reports")
    with TestClient(app) as client:
        def command(kind, parameters):
            return client.post("/equipment/commands", json={"schema_version": "1.0", "command_id": kind,
                "machine_id": "SIM-ETCH-01", "type": kind, "parameters": parameters}).json()
        states = [client.get("/equipment/state").json()["state"]]
        assert command("LOAD", {"wafer_id": "W-DEMO-001"})["accepted"]
        states.append(client.get("/equipment/state").json()["state"])
        start = command("START", {"recipe_id": "DEMO_A", "recipe_version": "1"})
        assert start["accepted"]
        states.append(client.get("/equipment/state").json()["state"])
        for seconds in (3, 10):
            states.append(client.post("/sim/clock/advance", json={"seconds": seconds}).json()["state"])
        assert command("UNLOAD", {})["accepted"]
        states.append(client.get("/equipment/state").json()["state"])
        assert states == ["EMPTY", "LOADED", "PREPARING", "PROCESSING", "COMPLETED", "EMPTY"]
        evidence = client.get("/sim/evidence").json()
        assert len(evidence["runs"]) == 1
        assert evidence["runs"][0]["status"] == "COMPLETED"
        assert [e["type"] for e in evidence["events"]].count("RunCompleted") == 1
        assert evidence["runs"][0]["run_id"] == start["run_id"]
