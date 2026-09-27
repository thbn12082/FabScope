import hashlib
import json
import math
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "demo.json"


def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not config.get("machine_id") or not isinstance(config.get("seed"), int):
        raise ValueError("Invalid machine_id/seed in config")
    durations = [config["telemetry_interval_s"]]
    keys = set()
    for recipe in config["recipes"]:
        key = (recipe["recipe_id"], recipe["recipe_version"])
        if key in keys:
            raise ValueError("Duplicate recipe/version")
        keys.add(key)
        durations.extend([recipe["prepare_s"], recipe["process_s"]])
        if not math.isfinite(recipe["demo_level"]):
            raise ValueError("Invalid demo level")
    if not keys or any(isinstance(x, bool) or not math.isfinite(x) or x < 0.001 for x in durations):
        raise ValueError("Durations must be finite and >= 0.001 s")
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return config, digest
