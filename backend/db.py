from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .commerce_store import CommerceStoreMixin
from .order_store import OrderStoreMixin
from .record_store import JsonObject, RecordStoreMixin
from .security import create_token, hash_token


class Database(RecordStoreMixin, CommerceStoreMixin, OrderStoreMixin):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)
            for column, definition in (
                ("prepay_id", "TEXT"), ("transaction_id", "TEXT"),
                ("paid_at", "TEXT"), ("payment_notify_id", "TEXT"),
            ):
                try:
                    connection.execute(f"ALTER TABLE consultation_orders ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError as error:
                    if "duplicate column name" not in str(error):
                        raise
            timestamp = self.now()
            defaults = {
                "consultation.enabled": True,
                "consultation.channel": "wechat-contact",
                "payment.enabled": False,
                "payment.reason": "待配置微信支付参数",
                "ai.enabled": False,
                "ai.reason": "待确认 AI 接入范围和密钥",
            }
            for key, value in defaults.items():
                connection.execute(
                    "INSERT OR IGNORE INTO runtime_config (key, value, is_public, updated_at) VALUES (?, ?, 1, ?)",
                    (key, json.dumps(value, ensure_ascii=False), timestamp),
                )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def make_id(prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(10)}"

    def upsert_user(self, openid: str, unionid: str = "") -> dict[str, object]:
        timestamp = self.now()
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM users WHERE openid = ?", (openid,)).fetchone()
            if row is None:
                user_id = self.make_id("user")
                connection.execute(
                    "INSERT INTO users (id, openid, unionid, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, openid, unionid or None, timestamp, timestamp),
                )
            else:
                user_id = str(row["id"])
                connection.execute(
                    "UPDATE users SET unionid = COALESCE(NULLIF(?, ''), unionid), updated_at = ? WHERE id = ?",
                    (unionid, timestamp, user_id),
                )
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, nickname, avatar_url, created_at, updated_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            raise KeyError(user_id)
        return {key: row[key] for key in row.keys()}

    def get_user_openid(self, user_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute("SELECT openid FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise KeyError(user_id)
        return str(row["openid"])

    def update_user(self, user_id: str, nickname: str, avatar_url: str) -> dict[str, object]:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET nickname = ?, avatar_url = ?, updated_at = ? WHERE id = ?",
                (nickname, avatar_url, self.now(), user_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(user_id)
        return self.get_user(user_id)

    def create_session(self, user_id: str, secret: str, days: int = 30) -> tuple[str, str]:
        token = create_token()
        expires = datetime.now(timezone.utc) + timedelta(days=days)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (hash_token(token, secret), user_id, expires.isoformat(timespec="seconds"), self.now()),
            )
        return token, expires.isoformat(timespec="seconds")

    def resolve_session(self, token: str, secret: str) -> str | None:
        now = self.now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
                (hash_token(token, secret), now),
            ).fetchone()
        return str(row["user_id"]) if row else None

    def public_config(self) -> dict[str, object]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM runtime_config WHERE is_public = 1 ORDER BY key"
            ).fetchall()
        return {str(row["key"]): json.loads(str(row["value"])) for row in rows}

    def set_config(self, key: str, value: object, is_public: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runtime_config (key, value, is_public, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, is_public = excluded.is_public, "
                "updated_at = excluded.updated_at",
                (key, json.dumps(value, ensure_ascii=False), int(is_public), self.now()),
            )
