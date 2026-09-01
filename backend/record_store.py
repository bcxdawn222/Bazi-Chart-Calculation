from __future__ import annotations

import json
import sqlite3
from typing import Protocol, TypedDict


JsonObject = dict[str, object]


class StoredRecord(TypedDict):
    id: str
    user_id: str
    payload: JsonObject
    status: str
    created_at: str
    updated_at: str


class StoreHost(Protocol):
    def connect(self) -> sqlite3.Connection: ...
    @staticmethod
    def now() -> str: ...
    @staticmethod
    def make_id(prefix: str) -> str: ...


class RecordStoreMixin:
    def _create(self: StoreHost, table: str, prefix: str, user_id: str, payload: JsonObject) -> StoredRecord:
        record_id = self.make_id(prefix)
        timestamp = self.now()
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO {table} (id, user_id, payload, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, user_id, json.dumps(payload, ensure_ascii=False), "active", timestamp, timestamp),
            )
        return self.get(table, record_id)

    def _list(self: StoreHost, table: str, user_id: str) -> list[StoredRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT id, user_id, payload, status, created_at, updated_at FROM {table} "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
                (user_id,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self: StoreHost, table: str, record_id: str) -> StoredRecord:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT id, user_id, payload, status, created_at, updated_at FROM {table} WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return self._row(row)

    def get_for_user(self: StoreHost, table: str, record_id: str, user_id: str) -> StoredRecord:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT id, user_id, payload, status, created_at, updated_at FROM {table} "
                "WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return self._row(row)

    @staticmethod
    def _row(row: sqlite3.Row) -> StoredRecord:
        return {
            "id": str(row["id"]), "user_id": str(row["user_id"]),
            "payload": json.loads(str(row["payload"])), "status": str(row["status"]),
            "created_at": str(row["created_at"]), "updated_at": str(row["updated_at"]),
        }

    def update_record(self: StoreHost, table: str, record_id: str, user_id: str, status: str) -> StoredRecord:
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE {table} SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (status, self.now(), record_id, user_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(record_id)
        return self.get_for_user(table, record_id, user_id)

    def delete_record(self: StoreHost, table: str, record_id: str, user_id: str) -> None:
        with self.connect() as connection:
            cursor = connection.execute(f"DELETE FROM {table} WHERE id = ? AND user_id = ?", (record_id, user_id))
        if cursor.rowcount != 1:
            raise KeyError(record_id)

    def create_chart(self: StoreHost, user_id: str, payload: JsonObject) -> StoredRecord:
        return self._create("charts", "chart", user_id, payload)
    def list_charts(self: StoreHost, user_id: str) -> list[StoredRecord]:
        return self._list("charts", user_id)
    def create_prayer(self: StoreHost, user_id: str, payload: JsonObject) -> StoredRecord:
        return self._create("prayers", "prayer", user_id, payload)
    def list_prayers(self: StoreHost, user_id: str) -> list[StoredRecord]:
        return self._list("prayers", user_id)
    def create_wish(self: StoreHost, user_id: str, payload: JsonObject) -> StoredRecord:
        return self._create("wishes", "wish", user_id, payload)
    def list_wishes(self: StoreHost, user_id: str) -> list[StoredRecord]:
        return self._list("wishes", user_id)
    def create_consultation(self: StoreHost, user_id: str, payload: JsonObject) -> StoredRecord:
        return self._create("consultations", "consult", user_id, payload)
    def list_consultations(self: StoreHost, user_id: str) -> list[StoredRecord]:
        return self._list("consultations", user_id)
