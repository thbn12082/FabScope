import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


class Server:
    """Owns only the localhost child process it creates; never touches a manual server."""
    def __init__(self, directory, config_path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config_path = Path(config_path).resolve()
        self.process = self.client = self.log = None
        self.pids = []
        self.server_pid = None

    def start(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.log = (self.directory / "server.log").open("ab")
        self.process = subprocess.Popen([sys.executable, "-m", "fabscope", "serve", "--port", str(port),
            "--db", str(self.directory / "session.sqlite3"), "--config", str(self.config_path),
            "--reports", str(self.directory / "reports")], stdout=self.log, stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.pids.append(self.process.pid)
        self.client = httpx.Client(base_url=self.url, timeout=60, trust_env=False)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                health = self.client.get("/health", timeout=0.5)
                if health.status_code == 200:
                    self.server_pid = health.json()["process_id"]
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        self.stop()
        raise RuntimeError("Scenario server failed to start; see its local server.log")

    def stop(self, crash=False):
        was_ready = self.server_pid is not None
        if self.client:
            self.client.close()
            self.client = None
        if self.process and self.process.poll() is None:
            self.process.kill() if crash else self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log:
            self.log.close()
            self.log = None
        if was_ready:
            # Windows venv launchers may have a child interpreter. Verify the
            # HTTP service disappeared too, not merely that its launcher exited.
            with httpx.Client(timeout=0.3, trust_env=False) as probe:
                deadline = time.monotonic() + 3
                while True:
                    try:
                        probe.get(self.url + "/health")
                    except httpx.HTTPError:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Owned scenario HTTP server still responds after process stop")
                    time.sleep(0.05)
            self.server_pid = None

    def restart(self):
        self.stop(crash=True)
        return self.start()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


class EquipmentClient:
    """Cursor advances only over contiguous sequence; duplicates never reapply."""
    def __init__(self, server):
        self.server = server
        self.cursor = 0
        self.applied = []
        self.seen = set()
        self.pending = {}
        self.last_state = None
        self.stale = True
        self.received = 0

    def refresh(self):
        response = self.server.client.get("/equipment/state")
        self.stale = response.status_code != 200
        if not self.stale:
            self.last_state = response.json()
        return response

    def apply(self, events):
        for event in events:
            self.received += 1
            if event["event_id"] not in self.seen:
                self.pending[event["sequence"]] = event
        while self.cursor + 1 in self.pending:
            event = self.pending.pop(self.cursor + 1)
            if event["event_id"] not in self.seen:
                self.applied.append(event)
                self.seen.add(event["event_id"])
            self.cursor += 1
        for seq in list(self.pending):
            if seq <= self.cursor:
                del self.pending[seq]

    def sync(self, limit=3):
        for _ in range(10000):
            response = self.server.client.get("/equipment/events", params={"after_sequence": self.cursor, "limit": limit})
            if response.status_code != 200:
                self.stale = True
                return response
            page = response.json()
            before = self.cursor
            self.apply(page["events"])
            if not page["has_more"]:
                return response
            if before == self.cursor:
                raise ValueError("EVENT_GAP: missing contiguous event; cursor did not jump")
        raise ValueError("Event pagination exceeded safety bound")
