"""One SQLite transaction contains domain state, journal, runs and command outcome."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .domain import Engine, initial_state


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


class Store:
    def __init__(self, path, config, config_hash):
        self.path, self.config, self.config_hash = Path(path), config, config_hash
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY CHECK(id=1),
                    session_id TEXT NOT NULL, config_hash TEXT NOT NULL, state TEXT NOT NULL, gateway TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commands (machine_id TEXT, command_id TEXT, fingerprint TEXT NOT NULL,
                    result TEXT NOT NULL, PRIMARY KEY(machine_id,command_id));
            """)
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT config_hash FROM snapshot WHERE id=1").fetchone()
            if row and row[0] != config_hash:
                raise ValueError("CONFIG_MISMATCH: saved session uses a different configuration; use its original config or a new database.")
            if not row:
                db.execute("INSERT INTO snapshot VALUES (1,?,?,?,?)", (uuid.uuid4().hex, config_hash,
                    encode(initial_state()), encode(dict(disconnected=False, lost_ack_once=False,
                                                         duplicate_delivery=False, playing=False))))
            # A service restart never advances time or resumes play implicitly.
            flags = json.loads(db.execute("SELECT gateway FROM snapshot").fetchone()[0])
            flags["playing"] = False
            db.execute("UPDATE snapshot SET gateway=? WHERE id=1", (encode(flags),))
            db.commit()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    def transact(self, action):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                session_id, _, state, flags = db.execute("SELECT session_id,config_hash,state,gateway FROM snapshot").fetchone()
                runs = {rid: json.loads(data) for rid, data in db.execute("SELECT run_id,data FROM runs")}
                engine = Engine(self.config, session_id, json.loads(state), runs)
                gateway = json.loads(flags)
                result = action(engine, gateway, db)
                db.execute("UPDATE snapshot SET state=?,gateway=? WHERE id=1", (encode(engine.state), encode(gateway)))
                db.executemany("INSERT INTO events VALUES (?,?)", [(e["sequence"], encode(e)) for e in engine.events])
                db.executemany("INSERT OR REPLACE INTO runs VALUES (?,?)", [(rid, encode(r)) for rid, r in engine.runs.items()])
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def command(self, command, engine, db):
        fingerprint = encode({k: v for k, v in command.items() if k != "command_id"})
        key = (command["machine_id"], command["command_id"])
        old = db.execute("SELECT fingerprint,result FROM commands WHERE machine_id=? AND command_id=?", key).fetchone()
        if old:
            if old[0] == fingerprint:
                return json.loads(old[1])
            return engine.result(command, False, "IDEMPOTENCY_CONFLICT", "ID này đã gắn với nội dung lệnh khác.")
        result = engine.command(command)
        db.execute("INSERT INTO commands VALUES (?,?,?,?)", (*key, fingerprint, encode(result)))
        return result

    def evidence(self):
        def read(engine, flags, db):
            return dict(state=engine.view(), gateway=flags, runs=list(engine.runs.values()),
                events=[json.loads(row[0]) for row in db.execute("SELECT data FROM events ORDER BY sequence")],
                commands=[dict(machine_id=m, command_id=c, content=json.loads(f), result=json.loads(r))
                          for m, c, f, r in db.execute("SELECT * FROM commands ORDER BY rowid")])
        return self.transact(read)
