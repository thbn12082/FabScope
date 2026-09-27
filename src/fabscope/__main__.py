import argparse
from pathlib import Path

from .config import DEFAULT_CONFIG


def main():
    parser = argparse.ArgumentParser(description="FabScope: local simulation only")
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8770)
    serve.add_argument("--db", type=Path, default=Path("runtime/manual.sqlite3"))
    serve.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    serve.add_argument("--reports", type=Path, default=Path("runtime/reports"))
    scenarios = sub.add_parser("scenarios")
    scenarios.add_argument("--id", default="all")
    scenarios.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    scenarios.add_argument("--output", type=Path, default=Path("runtime/reports"))
    args = parser.parse_args()
    if args.action == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(args.db, args.config, args.reports), host="127.0.0.1", port=args.port, log_level="info")
    else:
        from .scenarios.runner import CATALOG, run_scenario
        if args.id != "all" and args.id not in CATALOG:
            parser.error("Unknown scenario ID")
        ids = list(CATALOG) if args.id == "all" else [args.id]
        passed = True
        for sid in ids:
            report = run_scenario(sid, args.config, args.output)
            print(f"{sid}: {report['status']} - {report['report_id']}")
            passed &= report["status"] == "PASS"
        raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
