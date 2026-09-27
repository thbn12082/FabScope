"""Oracles examine externally observed output, never the engine implementation."""
import json


def normal_run_checks(evidence):
    events, runs = evidence["events"], evidence["runs"]
    kinds = [e["type"] for e in events]
    return [
        ("Một START chỉ tạo một run", 1, len(runs)),
        ("Đúng một RunStarted", 1, kinds.count("RunStarted")),
        ("Đúng một RunCompleted", 1, kinds.count("RunCompleted")),
        ("Run kết thúc COMPLETED", ["COMPLETED"], [r["status"] for r in runs]),
        ("Sequence liên tục", list(range(1, len(events) + 1)), [e["sequence"] for e in events]),
        ("Thời gian sự kiện không lùi", sorted(e["sim_time_s"] for e in events), [e["sim_time_s"] for e in events]),
        ("Wafer đúng", ["W-DEMO-001"], [r["wafer_id"] for r in runs]),
        ("Recipe/version đúng", [["DEMO_A", "1"]], [[r["recipe_id"], r["recipe_version"]] for r in runs]),
        ("Các sự kiện domain đúng thứ tự", ["WaferLoaded", "RunStarted", "PreparationStarted", "ProcessingStarted", "RunCompleted", "WaferUnloaded"],
         [k for k in kinds if k != "TelemetrySampled"]),
    ]


def evaluate_normal(evidence):
    return all(expected == actual for _, expected, actual in normal_run_checks(evidence))


def normalized(evidence):
    # Only session identity is nondeterministic. All telemetry, times and run ordinals remain.
    session = evidence["state"]["session_id"]
    return json.loads(json.dumps({"events": evidence["events"], "runs": evidence["runs"]}, sort_keys=True).replace(session, "SESSION"))
