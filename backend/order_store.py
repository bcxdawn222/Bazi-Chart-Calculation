from __future__ import annotations

import sqlite3
from typing import Protocol

from .commerce_store import SERVICE_STATUSES, _price, _required_text, _row, _status
from .record_store import JsonObject


ORDER_COLUMNS = (
    "id, user_id, expert_id, schedule_id, subject, amount_cents, payment_status, "
    "prepay_id, transaction_id, paid_at, payment_notify_id, service_status, created_at, updated_at"
)
PUBLIC_ORDER_FIELDS = (
    "id", "expert_id", "schedule_id", "subject", "amount_cents", "payment_status",
    "service_status", "transaction_id", "paid_at", "created_at", "updated_at",
)


class StoreHost(Protocol):
    def connect(self) -> sqlite3.Connection: ...
    @staticmethod
    def now() -> str: ...
    @staticmethod
    def make_id(prefix: str) -> str: ...
    def get_expert(self, expert_id: str) -> dict[str, object]: ...
    def get_schedule(self, schedule_id: str) -> dict[str, object]: ...


class OrderStoreMixin:
    def create_order(self: StoreHost, user_id: str, payload: JsonObject) -> dict[str, object]:
        subject = _required_text(payload, "subject", "咨询事项", 120)
        expert_id = str(payload.get("expert_id", "")).strip()
        schedule_id = str(payload.get("schedule_id", "")).strip()
        amount_cents: int | None = None
        if expert_id:
            expert = self.get_expert(expert_id)
            if expert["status"] == "hidden":
                raise ValueError("专家不存在或暂未开放")
            amount_cents = _price(expert["price_cents"])
        if schedule_id:
            schedule = self.get_schedule(schedule_id)
            if schedule["expert_id"] != expert_id or schedule["status"] != "available":
                raise ValueError("所选排班不可用")
        order_id = self.make_id("order")
        timestamp = self.now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO consultation_orders "
                "(id, user_id, expert_id, schedule_id, subject, amount_cents, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, expert_id or None, schedule_id or None, subject, amount_cents, timestamp, timestamp),
            )
        return self.get_order(order_id, user_id)

    def get_order(self: StoreHost, order_id: str, user_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE id = ? AND user_id = ?",
                (order_id, user_id),
            ).fetchone()
        if row is None:
            raise KeyError(order_id)
        return _row(row)

    def _get_order_any(self: StoreHost, order_id: str) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE id = ?", (order_id,),
            ).fetchone()
        if row is None:
            raise KeyError(order_id)
        return _row(row)

    def get_public_order(self: StoreHost, order_id: str, user_id: str) -> dict[str, object]:
        order = self.get_order(order_id, user_id)
        return {key: order[key] for key in PUBLIC_ORDER_FIELDS}

    def list_orders(self: StoreHost, user_id: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [{key: row[key] for key in PUBLIC_ORDER_FIELDS} for row in rows]

    def list_ops_orders(self: StoreHost, payment_status: str = "", service_status: str = "") -> list[dict[str, object]]:
        filters: list[str] = []
        params: list[object] = []
        if payment_status:
            if payment_status not in {"not_configured", "pending", "paid"}:
                raise ValueError("支付状态无效")
            filters.append("payment_status = ?")
            params.append(payment_status)
        if service_status:
            _status(service_status, SERVICE_STATUSES, "服务")
            filters.append("service_status = ?")
            params.append(service_status)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders{where} ORDER BY created_at DESC", tuple(params),
            ).fetchall()
        return [_row(row) for row in rows]

    def update_order_service_status(self: StoreHost, order_id: str, status: str) -> dict[str, object]:
        value = _status(status, SERVICE_STATUSES, "服务")
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE consultation_orders SET service_status = ?, updated_at = ? WHERE id = ?",
                (value, self.now(), order_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(order_id)
        return self._get_order_any(order_id)

    def mark_order_pending(self: StoreHost, order_id: str, user_id: str, prepay_id: str) -> dict[str, object]:
        order = self.get_order(order_id, user_id)
        if order["payment_status"] == "paid":
            raise ValueError("订单已经支付")
        if not order["amount_cents"]:
            raise ValueError("订单尚未配置有效金额")
        with self.connect() as connection:
            connection.execute(
                "UPDATE consultation_orders SET payment_status = 'pending', prepay_id = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?", (prepay_id, self.now(), order_id, user_id),
            )
        return self.get_order(order_id, user_id)

    def mark_order_paid(
        self: StoreHost, out_trade_no: str, transaction_id: str, total_cents: int, paid_at: str, notify_id: str,
    ) -> dict[str, object]:
        with self.connect() as connection:
            order = connection.execute(
                "SELECT id, amount_cents FROM consultation_orders WHERE id = ?", (out_trade_no,),
            ).fetchone()
            if order is None:
                raise KeyError(out_trade_no)
            if int(order["amount_cents"] or 0) != total_cents:
                raise ValueError("支付金额与订单金额不一致")
            existing = connection.execute(
                "SELECT out_trade_no, transaction_id FROM payment_notifications WHERE notify_id = ?", (notify_id,),
            ).fetchone()
            if existing and (existing["out_trade_no"] != out_trade_no or existing["transaction_id"] != transaction_id):
                raise ValueError("支付通知 ID 与历史记录冲突")
            if existing is None:
                connection.execute(
                    "INSERT INTO payment_notifications (notify_id, out_trade_no, transaction_id, created_at) "
                    "VALUES (?, ?, ?, ?)", (notify_id, out_trade_no, transaction_id, self.now()),
                )
                connection.execute(
                    "UPDATE consultation_orders SET payment_status = 'paid', transaction_id = ?, paid_at = ?, "
                    "payment_notify_id = ?, updated_at = ? WHERE id = ?",
                    (transaction_id, paid_at, notify_id, self.now(), out_trade_no),
                )
        return self._get_order_any(out_trade_no)

    def create_review(self: StoreHost, user_id: str, payload: JsonObject) -> dict[str, object]:
        order_id = str(payload.get("order_id", "")).strip()
        rating = int(payload.get("rating", 0))
        if rating < 1 or rating > 5:
            raise ValueError("评分必须为 1 至 5")
        self.get_order(order_id, user_id)
        review_id = self.make_id("review")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO reviews (id, order_id, user_id, rating, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, order_id, user_id, rating, str(payload.get("content", "")).strip(), self.now()),
            )
            row = connection.execute(
                "SELECT id, order_id, rating, content, status, created_at FROM reviews WHERE id = ?", (review_id,),
            ).fetchone()
        return _row(row)
