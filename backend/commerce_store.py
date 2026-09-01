from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Protocol

from .record_store import JsonObject


EXPERT_STATUSES = {"online", "offline", "hidden"}
SCHEDULE_STATUSES = {"available", "booked", "closed"}
SERVICE_STATUSES = {"pending", "confirmed", "completed", "cancelled"}


class StoreHost(Protocol):
    def connect(self) -> sqlite3.Connection: ...
    @staticmethod
    def now() -> str: ...
    @staticmethod
    def make_id(prefix: str) -> str: ...


def _row(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _required_text(payload: JsonObject, key: str, label: str, limit: int) -> str:
    value = str(payload.get(key, "")).strip()
    if not value or len(value) > limit:
        raise ValueError(f"{label}不能为空且不能超过 {limit} 个字符")
    return value


def _status(value: object, allowed: set[str], label: str) -> str:
    status = str(value or "").strip()
    if status not in allowed:
        raise ValueError(f"{label}状态只允许：{'、'.join(sorted(allowed))}")
    return status


def _price(value: object) -> int | None:
    if value is None or value == "":
        return None
    price = int(value)
    if price <= 0:
        raise ValueError("专家价格必须为正整数分")
    return price


def _iso_time(value: object, label: str) -> str:
    text = str(value or "").strip()
    try:
        datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{label}必须是 ISO 8601 时间") from error
    return text


class CommerceStoreMixin:
    def list_experts(self: StoreHost) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, display_name, bio, avatar_url, status, price_cents FROM experts "
                "WHERE status != 'hidden' ORDER BY display_name"
            ).fetchall()
        return [_row(row) for row in rows]

    def list_ops_experts(self: StoreHost) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, display_name, bio, avatar_url, status, price_cents, created_at, updated_at "
                "FROM experts ORDER BY display_name"
            ).fetchall()
        return [_row(row) for row in rows]

    def get_expert(self: StoreHost, expert_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, display_name, bio, avatar_url, status, price_cents, created_at, updated_at "
                "FROM experts WHERE id = ?", (expert_id,),
            ).fetchone()
        if row is None:
            raise KeyError(expert_id)
        return _row(row)

    def create_expert(self: StoreHost, payload: JsonObject) -> dict[str, object]:
        expert_id = self.make_id("expert")
        timestamp = self.now()
        values = (
            expert_id, _required_text(payload, "display_name", "专家名称", 40),
            str(payload.get("bio", "")).strip()[:500], str(payload.get("avatar_url", "")).strip()[:500],
            _status(payload.get("status", "offline"), EXPERT_STATUSES, "专家"),
            _price(payload.get("price_cents")), timestamp, timestamp,
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO experts (id, display_name, bio, avatar_url, status, price_cents, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values,
            )
        return self.get_expert(expert_id)

    def update_expert(self: StoreHost, expert_id: str, payload: JsonObject) -> dict[str, object]:
        current = self.get_expert(expert_id)
        display_name = current["display_name"] if "display_name" not in payload else _required_text(
            payload, "display_name", "专家名称", 40,
        )
        bio = current["bio"] if "bio" not in payload else str(payload["bio"]).strip()[:500]
        avatar = current["avatar_url"] if "avatar_url" not in payload else str(payload["avatar_url"]).strip()[:500]
        status = current["status"] if "status" not in payload else _status(payload["status"], EXPERT_STATUSES, "专家")
        price = current["price_cents"] if "price_cents" not in payload else _price(payload["price_cents"])
        with self.connect() as connection:
            connection.execute(
                "UPDATE experts SET display_name = ?, bio = ?, avatar_url = ?, status = ?, price_cents = ?, "
                "updated_at = ? WHERE id = ?",
                (display_name, bio, avatar, status, price, self.now(), expert_id),
            )
        return self.get_expert(expert_id)

    def delete_expert(self: StoreHost, expert_id: str) -> str:
        self.get_expert(expert_id)
        with self.connect() as connection:
            referenced = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM consultation_orders WHERE expert_id = ?) OR "
                "EXISTS(SELECT 1 FROM expert_schedules WHERE expert_id = ?)", (expert_id, expert_id),
            ).fetchone()[0]
            if referenced:
                connection.execute(
                    "UPDATE experts SET status = 'hidden', updated_at = ? WHERE id = ?", (self.now(), expert_id),
                )
                return "hidden"
            connection.execute("DELETE FROM experts WHERE id = ?", (expert_id,))
        return "deleted"

    def list_schedules(self: StoreHost, expert_id: str = "") -> list[dict[str, object]]:
        sql = "SELECT id, expert_id, starts_at, ends_at, status FROM expert_schedules"
        params: tuple[object, ...] = ()
        if expert_id:
            sql += " WHERE expert_id = ?"
            params = (expert_id,)
        with self.connect() as connection:
            rows = connection.execute(sql + " ORDER BY starts_at", params).fetchall()
        return [_row(row) for row in rows]

    def get_schedule(self: StoreHost, schedule_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, expert_id, starts_at, ends_at, status, created_at, updated_at "
                "FROM expert_schedules WHERE id = ?", (schedule_id,),
            ).fetchone()
        if row is None:
            raise KeyError(schedule_id)
        return _row(row)

    def create_schedule(self: StoreHost, payload: JsonObject) -> dict[str, object]:
        expert_id = _required_text(payload, "expert_id", "专家", 64)
        self.get_expert(expert_id)
        starts_at = _iso_time(payload.get("starts_at"), "开始时间")
        ends_at = _iso_time(payload.get("ends_at"), "结束时间")
        if datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
            raise ValueError("排班结束时间必须晚于开始时间")
        schedule_id = self.make_id("schedule")
        timestamp = self.now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO expert_schedules (id, expert_id, starts_at, ends_at, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (schedule_id, expert_id, starts_at, ends_at,
                 _status(payload.get("status", "available"), SCHEDULE_STATUSES, "排班"), timestamp, timestamp),
            )
        return self.get_schedule(schedule_id)

    def update_schedule(self: StoreHost, schedule_id: str, payload: JsonObject) -> dict[str, object]:
        current = self.get_schedule(schedule_id)
        expert_id = str(payload.get("expert_id", current["expert_id"]))
        self.get_expert(expert_id)
        starts_at = _iso_time(payload.get("starts_at", current["starts_at"]), "开始时间")
        ends_at = _iso_time(payload.get("ends_at", current["ends_at"]), "结束时间")
        if datetime.fromisoformat(ends_at) <= datetime.fromisoformat(starts_at):
            raise ValueError("排班结束时间必须晚于开始时间")
        status = _status(payload.get("status", current["status"]), SCHEDULE_STATUSES, "排班")
        with self.connect() as connection:
            connection.execute(
                "UPDATE expert_schedules SET expert_id = ?, starts_at = ?, ends_at = ?, status = ?, "
                "updated_at = ? WHERE id = ?", (expert_id, starts_at, ends_at, status, self.now(), schedule_id),
            )
        return self.get_schedule(schedule_id)

    def delete_schedule(self: StoreHost, schedule_id: str) -> str:
        self.get_schedule(schedule_id)
        with self.connect() as connection:
            referenced = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM consultation_orders WHERE schedule_id = ?)", (schedule_id,),
            ).fetchone()[0]
            if referenced:
                connection.execute(
                    "UPDATE expert_schedules SET status = 'closed', updated_at = ? WHERE id = ?",
                    (self.now(), schedule_id),
                )
                return "closed"
            connection.execute("DELETE FROM expert_schedules WHERE id = ?", (schedule_id,))
        return "deleted"
