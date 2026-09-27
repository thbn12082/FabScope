import html
import json
from pathlib import Path


def save_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report_id = report["report_id"]
    (directory / f"{report_id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    def esc(value):
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value)
    rows = "".join(f"<tr><td>{esc(c['name'])}</td><td><pre>{esc(c['expected'])}</pre></td><td><pre>{esc(c['actual'])}</pre></td><td>{c['status']}</td></tr>" for c in report["checks"])
    page = f"""<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{esc(report['scenario_id'])} · FabScope report</title><style>
body{{background:#0c1420;color:#e7edf8;font:15px/1.6 system-ui;max-width:1200px;margin:40px auto;padding:0 24px}}
h1{{font-size:30px}} a{{color:#70ddc5}}small{{color:#b3bfce}}table{{width:100%;border-collapse:collapse}}td,th{{padding:12px;border:1px solid #304157;text-align:left;vertical-align:top}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;margin:0;font-size:12px}}details{{background:#162335;padding:16px;margin-top:20px}}.notice{{color:#edcb7b}}</style>
<p class="notice">MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH</p><h1>{esc(report['scenario_id'])} — {esc(report['name'])}</h1>
<h2>{report['status']}</h2><p>Phần mềm {esc(report['software_version'])} · config {esc(report['config_version'])} · seed {report['seed']}</p>
<small>Session: {esc(report['session_id'])}<br>Config SHA256: {esc(report['config_hash'])}</small>
<p>{esc(report['limits'])}</p><table><thead><tr><th>Điều kiện kiểm tra</th><th>Mong đợi</th><th>Thực tế</th><th>Kết quả</th></tr></thead><tbody>{rows}</tbody></table>
<details><summary>Các bước HTTP và kết quả thực tế</summary><pre>{esc(report['steps'])}</pre></details>
<details><summary>Bằng chứng: command ID, run ID, event sequence và trạng thái</summary><pre>{esc(report['evidence'])}</pre></details>
<p><a href="{report_id}">Bản JSON qua API</a> · <a href="{report_id}.json">Bản JSON khi mở file cục bộ</a></p></html>"""
    (directory / f"{report_id}.html").write_text(page, encoding="utf-8")
