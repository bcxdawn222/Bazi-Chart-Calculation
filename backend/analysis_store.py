from __future__ import annotations

import json
import re
import sqlite3
from typing import Protocol

from .order_store import ORDER_COLUMNS, PUBLIC_ORDER_FIELDS
from .record_store import JsonObject


CHART_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SECTION_KEYS = ("wealth", "marriage", "career", "personality", "health")
DEFAULT_ANALYSIS_SUBJECT = "命盘详细解读"


class StoreHost(Protocol):
    def connect(self) -> sqlite3.Connection: ...
    @staticmethod
    def now() -> str: ...
    @staticmethod
    def make_id(prefix: str) -> str: ...
    def public_config(self) -> dict[str, object]: ...
    def get_public_order(self, order_id: str, user_id: str) -> dict[str, object]: ...


def parse_chart_key(value: object) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("缺少 chart_key")
    text = str(value).strip()
    if CHART_KEY_RE.fullmatch(text) is None:
        raise ValueError("chart_key 无效")
    return text


def analysis_price_cents(config: dict[str, object]) -> int | None:
    value = config.get("analysis.price_cents")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _public_order(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in PUBLIC_ORDER_FIELDS}


class AnalysisStoreMixin:
    def create_analysis_order(self: StoreHost, user_id: str, payload: JsonObject) -> dict[str, object]:
        chart_key = parse_chart_key(payload.get("chart_key"))
        subject = payload.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            subject = DEFAULT_ANALYSIS_SUBJECT
        else:
            subject = subject.strip()
        price = analysis_price_cents(self.public_config())
        if price is None or price <= 0:
            raise RuntimeError("支付或售价未配置")
        order_id = self.make_id("order")
        timestamp = self.now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            paid = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE user_id = ? "
                "AND IFNULL(kind,'consultation')='analysis' AND chart_key = ? "
                "AND payment_status = 'paid' LIMIT 1",
                (user_id, chart_key),
            ).fetchone()
            if paid is not None:
                return _public_order(paid)
            unpaid = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE user_id = ? "
                "AND IFNULL(kind,'consultation')='analysis' AND payment_status != 'paid' "
                "AND service_status != 'cancelled' LIMIT 1",
                (user_id,),
            ).fetchone()
            if unpaid is not None:
                if str(unpaid["chart_key"] or "") == chart_key:
                    return _public_order(unpaid)
                raise ValueError("已有待支付解读单")
            connection.execute(
                "INSERT INTO consultation_orders "
                "(id, user_id, expert_id, schedule_id, subject, amount_cents, kind, chart_key, created_at, updated_at) "
                "VALUES (?, ?, NULL, NULL, ?, ?, 'analysis', ?, ?, ?)",
                (order_id, user_id, subject, price, chart_key, timestamp, timestamp),
            )
        return self.get_public_order(order_id, user_id)

    def get_analysis_order(self: StoreHost, user_id: str, chart_key: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE user_id = ? "
                "AND IFNULL(kind,'consultation')='analysis' AND chart_key = ? "
                "ORDER BY CASE payment_status WHEN 'paid' THEN 0 ELSE 1 END, created_at DESC LIMIT 1",
                (user_id, chart_key),
            ).fetchone()
        return _public_order(row) if row is not None else None

    def has_paid_analysis_order(self: StoreHost, user_id: str, chart_key: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM consultation_orders WHERE user_id = ? "
                "AND IFNULL(kind,'consultation')='analysis' AND chart_key = ? "
                "AND payment_status = 'paid' LIMIT 1",
                (user_id, chart_key),
            ).fetchone()
        return row is not None

    def upsert_analysis_report(
        self: StoreHost, user_id: str, chart_key: str, sections: dict[str, str], source: str,
    ) -> dict[str, object]:
        payload: dict[str, str] = {}
        for key in SECTION_KEYS:
            value = sections.get(key, "")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("解读段落不完整")
            payload[key] = value
        report_id = self.make_id("report")
        timestamp = self.now()
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO analysis_reports "
                "(id, user_id, chart_key, payload, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, chart_key) DO UPDATE SET "
                "payload = excluded.payload, source = excluded.source, updated_at = excluded.updated_at",
                (report_id, user_id, chart_key, encoded, source, timestamp, timestamp),
            )
        return self.public_analysis_report(user_id, chart_key)

    def public_analysis_report(
        self: StoreHost, user_id: str, chart_key: str, *, pending_reason: str = "",
    ) -> dict[str, object]:
        paid = self.has_paid_analysis_order(user_id, chart_key)
        if not paid:
            return {
                "chart_key": chart_key,
                "paid": False,
                "sections": {},
                "source": "pending",
                "reason": pending_reason or "尚未支付详细解读",
            }
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload, source FROM analysis_reports WHERE user_id = ? AND chart_key = ?",
                (user_id, chart_key),
            ).fetchone()
        if row is None:
            return {
                "chart_key": chart_key,
                "paid": True,
                "sections": {},
                "source": "pending",
                "reason": pending_reason or "详细解读尚未生成",
            }
        parsed = json.loads(str(row["payload"]))
        if not isinstance(parsed, dict):
            raise ValueError("解读正文损坏")
        sections = {}
        for key in SECTION_KEYS:
            value = parsed.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError("解读正文损坏")
            sections[key] = value
        return {
            "chart_key": chart_key,
            "paid": True,
            "sections": sections,
            "source": str(row["source"]),
            "reason": "",
        }
