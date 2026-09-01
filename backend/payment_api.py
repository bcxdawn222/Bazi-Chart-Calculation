from __future__ import annotations

import json
import logging

from .config import Settings
from .db import Database
from .wechat_payments import PaymentError, WechatPayClient


def prepare_order_payment(database: Database, settings: Settings, order_id: str, user_id: str) -> tuple[dict[str, object], dict[str, str]]:
    order = database.get_order(order_id, user_id)
    client = WechatPayClient.from_settings(settings)
    if not client.configured:
        raise PaymentError("微信支付参数尚未完整配置")
    if not order["amount_cents"]:
        raise ValueError("订单尚未配置有效金额")
    payment = client.create_jsapi_payment(
        str(order["id"]), str(order["subject"]), int(order["amount_cents"]),
        database.get_user_openid(user_id),
    )
    saved = database.mark_order_pending(order_id, user_id, payment["prepayId"])
    payment.pop("prepayId", None)
    return saved, payment


def process_wechat_notification(database: Database, settings: Settings, headers: dict[str, str], raw: bytes) -> None:
    client = WechatPayClient.from_settings(settings)
    if not client.configured:
        raise PaymentError("支付通知未配置")
    notification = client.verify_notification(headers, raw)
    if notification.trade_state != "SUCCESS":
        return
    if notification.app_id != settings.wx_app_id:
        raise PaymentError("支付通知 AppID 不匹配")
    if notification.mch_id != settings.wx_pay_mch_id:
        raise PaymentError("支付通知商户号不匹配")
    if notification.currency != "CNY":
        raise PaymentError("支付通知币种不支持")
    database.mark_order_paid(
        notification.out_trade_no, notification.transaction_id,
        notification.amount_total, notification.success_time, notification.notify_id,
    )
