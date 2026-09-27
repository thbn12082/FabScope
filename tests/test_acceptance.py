import json

import pytest

from fabscope.config import DEFAULT_CONFIG
from fabscope.scenarios.runner import CATALOG, run_scenario


@pytest.mark.parametrize("scenario_id", list(CATALOG))
def test_acceptance_over_real_http(scenario_id, tmp_path):
    report = run_scenario(scenario_id, DEFAULT_CONFIG, tmp_path / "reports")
    failures = [c for c in report["checks"] if c["status"] != "PASS"]
    assert report["status"] == "PASS", json.dumps(failures, ensure_ascii=False, indent=2)
    stored = json.loads((tmp_path / "reports" / (report["report_id"] + ".json")).read_text(encoding="utf-8"))
    assert stored == report
    assert report["session_id"]
    assert report["steps"]
    assert report["evidence"]
    html = (tmp_path / "reports" / (report["report_id"] + ".html")).read_text(encoding="utf-8")
    assert "MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH" in html
    assert "Mong đợi" in html and "Thực tế" in html
