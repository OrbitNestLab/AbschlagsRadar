"""Bounded local snapshots; live contracts remain authoritative in Home Assistant."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class SnapshotStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, stamp TEXT, digest TEXT UNIQUE, payload TEXT)"
            )
        self.path.chmod(0o600)

    def save(self, contracts):
        payload = json.dumps(contracts, ensure_ascii=False, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            latest = db.execute("SELECT digest FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
            if latest and latest[0] == digest:
                return
            db.execute(
                "INSERT OR REPLACE INTO snapshots(stamp,digest,payload) VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), digest, payload),
            )
            db.execute("DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT 24)")

    def latest(self):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT stamp,payload FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        return {"saved_at": row[0], "contracts": json.loads(row[1])} if row else None
