from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("CV_LICENSE_DB", ROOT / "licenses.db"))
SECRET = os.getenv("CV_LICENSE_SECRET", "change-this-secret-before-production").encode()
MAX_DEVICES = int(os.getenv("CV_MAX_DEVICES", "2"))


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS licenses (
      id INTEGER PRIMARY KEY,
      email TEXT NOT NULL,
      key_hash TEXT NOT NULL UNIQUE,
      plan TEXT NOT NULL CHECK(plan IN ('monthly','annual')),
      status TEXT NOT NULL DEFAULT 'active',
      expires_at TEXT NOT NULL,
      provider TEXT NOT NULL DEFAULT 'manual',
      provider_ref TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS devices (
      id INTEGER PRIMARY KEY,
      license_id INTEGER NOT NULL REFERENCES licenses(id),
      device_id TEXT NOT NULL,
      name TEXT,
      last_seen TEXT NOT NULL,
      UNIQUE(license_id, device_id)
    );
    """)
    return db


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()


def create_license(email: str, plan: str, days: int | None = None, provider: str = "manual", provider_ref: str = "") -> str:
    if plan not in {"monthly", "annual"}:
        raise ValueError("plan must be monthly or annual")
    days = days or (31 if plan == "monthly" else 366)
    key = "CVPRO-" + "-".join(secrets.token_hex(3).upper() for _ in range(4))
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    with connect() as db:
        db.execute(
            "INSERT INTO licenses(email,key_hash,plan,status,expires_at,provider,provider_ref,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (email.strip().lower(), _hash_key(key), plan, "active", expires.isoformat(), provider, provider_ref, now.isoformat()),
        )
    return key


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def issue_token(row: sqlite3.Row, device_id: str) -> str:
    payload = {
        "license_id": row["id"], "device_id": device_id,
        "exp": int(time.time()) + 7 * 86400,
    }
    encoded = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(SECRET, encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_token(token: str) -> dict | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64(hmac.new(SECRET, encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["exp"] < time.time():
            return None
        with connect() as db:
            row = db.execute("SELECT * FROM licenses WHERE id=?", (payload["license_id"],)).fetchone()
            device = db.execute("SELECT 1 FROM devices WHERE license_id=? AND device_id=?", (payload["license_id"], payload["device_id"])).fetchone()
            if not row or not device or row["status"] != "active" or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                return None
            db.execute("UPDATE devices SET last_seen=? WHERE license_id=? AND device_id=?", (datetime.now(timezone.utc).isoformat(), row["id"], payload["device_id"]))
            return {"active": True, "email": row["email"], "plan": row["plan"], "expires_at": row["expires_at"]}
    except Exception:
        return None


def activate(email: str, key: str, device_id: str, device_name: str = "") -> dict:
    email = email.strip().lower()
    with connect() as db:
        row = db.execute("SELECT * FROM licenses WHERE email=? AND key_hash=?", (email, _hash_key(key))).fetchone()
        if not row or row["status"] != "active":
            raise ValueError("Licence invalide ou inactive")
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            raise ValueError("Licence expirée")
        existing = db.execute("SELECT 1 FROM devices WHERE license_id=? AND device_id=?", (row["id"], device_id)).fetchone()
        count = db.execute("SELECT COUNT(*) FROM devices WHERE license_id=?", (row["id"],)).fetchone()[0]
        if not existing and count >= MAX_DEVICES:
            raise ValueError("Nombre maximal d'appareils atteint")
        db.execute(
            "INSERT INTO devices(license_id,device_id,name,last_seen) VALUES(?,?,?,?) ON CONFLICT(license_id,device_id) DO UPDATE SET name=excluded.name,last_seen=excluded.last_seen",
            (row["id"], device_id, device_name[:80], datetime.now(timezone.utc).isoformat()),
        )
        return {"token": issue_token(row, device_id), "plan": row["plan"], "expires_at": row["expires_at"]}


def authorization_token(headers) -> str:
    value = headers.get("Authorization", "")
    return value[7:].strip() if value.startswith("Bearer ") else ""

