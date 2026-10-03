from __future__ import annotations

import sqlite3
from typing import Protocol

from .commerce_store import SERVICE_STATUSES, _is_future, _price, _required_text, _row, _status
from .record_store import JsonObject


ORDER_COLUMNS = (
    "id, user_id, expert_id, schedule_id, subject, amount_cents, payment_status, "
    "prepay_id, transaction_id, paid_at, payment_notify_id, service_status, created_at, updated_at, "
    "kind, chart_key"
)
PUBLIC_ORDER_FIELDS = (
    "id", "expert_id", "schedule_id", "subject", "amount_cents", "payment_status",
    "service_status", "transaction_id", "paid_at", "created_at", "updated_at",
    "kind", "chart_key",
)
SERVICE_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


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
        expert_id = _required_text(payload, "expert_id", "专家", 64)
        schedule_id = _required_text(payload, "schedule_id", "排班", 64)
        order_id = self.make_id("order")
        timestamp = self.now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            unpaid = connection.execute(
                "SELECT 1 FROM consultation_orders WHERE user_id = ? AND IFNULL(kind,'consultation')='consultation' "
                "AND payment_status != 'paid' AND service_status != 'cancelled' LIMIT 1",
                (user_id,),
            ).fetchone()
            if unpaid is not None:
                raise ValueError("您已有待支付订单，请先继续支付或联系运营处理")
            selection = connection.execute(
                "SELECT expert.status AS expert_status, expert.price_cents, schedule.status AS schedule_status, "
                "schedule.starts_at, schedule.ends_at "
                "FROM experts AS expert JOIN expert_schedules AS schedule ON schedule.expert_id = expert.id "
                "WHERE expert.id = ? AND schedule.id = ?",
                (expert_id, schedule_id),
            ).fetchone()
            if selection is None or selection["expert_status"] != "online":
                raise ValueError("所选专家当前不可预约")
            if selection["schedule_status"] != "available":
                raise ValueError("所选排班不可用")
            if not _is_future(selection["starts_at"]):
                raise ValueError("所选排班已过期，请选择其他时间")
            amount_cents = _price(selection["price_cents"])
            if amount_cents is None:
                raise ValueError("所选专家尚未配置价格")
            reserved = connection.execute(
                "SELECT 1 FROM consultation_orders AS orders "
                "JOIN expert_schedules AS booked ON booked.id = orders.schedule_id "
                "WHERE orders.expert_id = ? AND orders.service_status != 'cancelled' "
                "AND datetime(booked.starts_at) < datetime(?) AND datetime(booked.ends_at) > datetime(?) LIMIT 1",
                (expert_id, selection["ends_at"], selection["starts_at"]),
            ).fetchone()
            if reserved is not None:
                raise ValueError("该专家在所选时段刚刚已被预约，请选择其他时间")
            connection.execute(
                "INSERT INTO consultation_orders "
                "(id, user_id, expert_id, schedule_id, subject, amount_cents, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, expert_id, schedule_id, subject, amount_cents, timestamp, timestamp),
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
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE user_id = ? "
                "AND IFNULL(kind,'consultation')='consultation' ORDER BY created_at DESC LIMIT 50",
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
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders{where} ORDER BY created_at DESC LIMIT 500",
                tuple(params),
            ).fetchall()
        return [_row(row) for row in rows]

    def update_order_service_status(self: StoreHost, order_id: str, status: str) -> dict[str, object]:
        value = _status(status, SERVICE_STATUSES, "服务")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE id = ?", (order_id,),
            ).fetchone()
            if row is None:
                raise KeyError(order_id)
            order = _row(row)
            current = str(order["service_status"])
            if value == current:
                return order
            if order.get("kind") == "analysis" and value != "cancelled":
                raise ValueError("详细解读订单由系统自动交付，不能人工确认或完成")
            if value not in SERVICE_TRANSITIONS[current]:
                raise ValueError(f"服务状态不能从 {current} 更新为 {value}")
            if value == "confirmed" and order["payment_status"] != "paid":
                raise ValueError("订单支付完成后才能确认服务")
            if value == "cancelled" and order["payment_status"] != "not_configured":
                raise ValueError("支付已发起的订单需核实交易并完成退款流程后再取消")
            cursor = connection.execute(
                "UPDATE consultation_orders SET service_status = ?, updated_at = ? WHERE id = ? AND service_status = ?",
                (value, self.now(), order_id, current),
            )
        if cursor.rowcount != 1:
            raise KeyError(order_id)
        return self._get_order_any(order_id)

    def mark_order_pending(self: StoreHost, order_id: str, user_id: str, prepay_id: str) -> dict[str, object]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            order = connection.execute(
                f"SELECT {ORDER_COLUMNS} FROM consultation_orders WHERE id = ? AND user_id = ?",
                (order_id, user_id),
            ).fetchone()
            if order is None:
                raise KeyError(order_id)
            if order["payment_status"] == "paid":
                raise ValueError("订单已经支付")
            if order["service_status"] != "pending":
                raise ValueError("当前服务状态不能发起支付")
            if not order["amount_cents"]:
                raise ValueError("订单尚未配置有效金额")
            if not str(prepay_id).strip():
                raise ValueError("预支付标识不能为空")
            connection.execute(
                "UPDATE consultation_orders SET payment_status = 'pending', prepay_id = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?", (prepay_id, self.now(), order_id, user_id),
            )
        return self.get_order(order_id, user_id)

    def mark_order_paid(
        self: StoreHost, out_trade_no: str, transaction_id: str, total_cents: int, paid_at: str, notify_id: str,
    ) -> dict[str, object]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
                transaction_order = connection.execute(
                    "SELECT id FROM consultation_orders WHERE transaction_id = ? AND id != ?",
                    (transaction_id, out_trade_no),
                ).fetchone()
                if transaction_order is not None:
                    raise ValueError("微信支付交易号已关联其他订单")
                current = connection.execute(
                    "SELECT payment_status, transaction_id FROM consultation_orders WHERE id = ?",
                    (out_trade_no,),
                ).fetchone()
                if current["payment_status"] == "paid" and current["transaction_id"] != transaction_id:
                    raise ValueError("订单已由其他微信支付交易完成")
                connection.execute(
                    "INSERT INTO payment_notifications (notify_id, out_trade_no, transaction_id, created_at) "
                    "VALUES (?, ?, ?, ?)", (notify_id, out_trade_no, transaction_id, self.now()),
                )
                connection.execute(
                    "UPDATE consultation_orders SET payment_status = 'paid', transaction_id = ?, paid_at = ?, "
                    "payment_notify_id = ?, service_status = CASE WHEN service_status = 'cancelled' "
                    "THEN 'pending' ELSE service_status END, updated_at = ? WHERE id = ?",
                    (transaction_id, paid_at, notify_id, self.now(), out_trade_no),
                )
        return self._get_order_any(out_trade_no)

    def create_review(self: StoreHost, user_id: str, payload: JsonObject) -> dict[str, object]:
        order_id = str(payload.get("order_id", "")).strip()
        try:
            rating = int(payload.get("rating", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("评分必须为 1 至 5") from error
        if rating < 1 or rating > 5:
            raise ValueError("评分必须为 1 至 5")
        order = self.get_order(order_id, user_id)
        if order["payment_status"] != "paid" or order["service_status"] != "completed":
            raise ValueError("订单支付并完成服务后才能评价")
        content = str(payload.get("content", "")).strip()
        if len(content) > 500:
            raise ValueError("评价内容不能超过 500 个字符")
        review_id = self.make_id("review")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM reviews WHERE order_id = ? LIMIT 1", (order_id,)).fetchone():
                raise ValueError("该订单已经评价")
            connection.execute(
                "INSERT INTO reviews (id, order_id, user_id, rating, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (review_id, order_id, user_id, rating, content, self.now()),
            )
            row = connection.execute(
                "SELECT id, order_id, rating, content, status, created_at FROM reviews WHERE id = ?", (review_id,),
            ).fetchone()
        return _row(row)
