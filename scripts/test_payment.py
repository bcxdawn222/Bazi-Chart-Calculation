from __future__ import annotations

import base64
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import Settings
from backend.db import Database
from backend.payment_api import prepare_order_payment, process_wechat_notification
from backend.wechat_payments import PaymentError, WechatPayClient


def signed_notification(
    client: WechatPayClient, private: rsa.RSAPrivateKey, plain: dict[str, object], notify_id: str
) -> tuple[dict[str, str], bytes]:
    nonce = "123456789012"
    encrypted = AESGCM(client.api_v3_key.encode("utf-8")).encrypt(
        nonce.encode(), json.dumps(plain, ensure_ascii=False).encode("utf-8"), b"",
    )
    body = json.dumps({
        "id": notify_id,
        "create_time": "2026-08-27T00:00:00+08:00",
        "event_type": "TRANSACTION.SUCCESS",
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(encrypted).decode(),
            "associated_data": "",
            "nonce": nonce,
        },
    }, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    header_nonce = "header-test"
    signed = (timestamp + "\n" + header_nonce + "\n").encode() + body + b"\n"
    signature = private.sign(signed, padding.PKCS1v15(), hashes.SHA256())
    return {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": header_nonce,
        "Wechatpay-Signature": base64.b64encode(signature).decode(),
        "Wechatpay-Serial": "platform-test",
    }, body


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path = root / "merchant.pem"
        platform_path = root / "platform.pem"
        private_path.write_bytes(private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        platform_path.write_bytes(private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        client = WechatPayClient(
            "wx-test", "mch-test", "serial-test", private_path, "12345678901234567890123456789012",
            "https://pay.example.test/api/payments/wechat/notify", "platform-test", platform_path,
        )
        assert client.configured
        settings = Settings(
            host="127.0.0.1", port=0, db_path=root / "test.sqlite3", log_path=root / "test.log",
            wx_app_id="wx-test", wx_app_secret="secret", session_secret="session",
            admin_token="admin", allowed_origins=(), wx_pay_mch_id="mch-test",
            wx_pay_serial_no="serial-test", wx_pay_private_key_path=private_path,
            wx_pay_api_v3_key=client.api_v3_key, wx_pay_notify_url=client.notify_url,
            wx_pay_platform_serial_no="platform-test", wx_pay_platform_public_key_path=platform_path,
        )
        database = Database(root / "test.sqlite3")
        user = database.upsert_user("openid-test")
        connection = database.connect()
        try:
            connection.execute(
                "INSERT INTO experts (id, display_name, price_cents, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", ("expert-test", "测试专家", 100, "online", "now", "now")
            )
            connection.commit()
        finally:
            connection.close()
        schedule = database.create_schedule({
            "expert_id": "expert-test",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "ends_at": (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat(),
            "status": "available",
        })
        order = database.create_order(str(user["id"]), {
            "subject": "测试咨询", "expert_id": "expert-test", "schedule_id": schedule["id"],
        })
        try:
            prepare_order_payment(database, settings, str(order["id"]), str(user["id"]))
        except PaymentError:
            pass
        else:
            raise AssertionError("运营关闭支付时不能发起支付")
        database.set_config("payment.enabled", True, True)
        database.mark_order_pending(str(order["id"]), str(user["id"]), "wx-test-prepay")
        saved, retry_payment = prepare_order_payment(
            database, settings, str(order["id"]), str(user["id"]),
        )
        assert saved["payment_status"] == "pending"
        assert retry_payment["package"] == "prepay_id=wx-test-prepay"
        plain = {
            "appid": "wx-test", "mchid": "mch-test",
            "out_trade_no": order["id"], "transaction_id": "wx-transaction-test",
            "trade_state": "SUCCESS", "success_time": "2026-08-27T00:00:00+08:00",
            "amount": {"total": 100, "currency": "CNY"},
        }
        headers, body = signed_notification(client, private, plain, "notify-test")
        notification = client.verify_notification(headers, body)
        assert notification.notify_id == "notify-test"
        assert notification.out_trade_no == order["id"]
        process_wechat_notification(database, settings, {key.lower(): value for key, value in headers.items()}, body)
        paid = database.get_order(str(order["id"]), str(user["id"]))
        process_wechat_notification(database, settings, headers, body)
        duplicate = database.get_order(str(order["id"]), str(user["id"]))
        assert paid["payment_status"] == duplicate["payment_status"] == "paid"

        second_schedule = database.create_schedule({
            "expert_id": "expert-test",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "ends_at": (datetime.now(timezone.utc) + timedelta(days=2, hours=1)).isoformat(),
            "status": "available",
        })
        second_order = database.create_order(str(user["id"]), {
            "subject": "第二笔咨询", "expert_id": "expert-test", "schedule_id": second_schedule["id"],
        })
        conflict_plain = dict(plain)
        conflict_plain["out_trade_no"] = second_order["id"]
        conflict_headers, conflict_body = signed_notification(
            client, private, conflict_plain, "notify-conflict-transaction",
        )
        try:
            process_wechat_notification(database, settings, conflict_headers, conflict_body)
        except ValueError:
            pass
        else:
            raise AssertionError("同一微信支付交易号不能入账到多个订单")

        bad_plain = dict(plain)
        bad_plain["appid"] = "wrong-app"
        bad_headers, bad_body = signed_notification(client, private, bad_plain, "notify-bad-app")
        try:
            process_wechat_notification(database, settings, bad_headers, bad_body)
        except PaymentError:
            pass
        else:
            raise AssertionError("支付通知 AppID 不匹配时必须拒绝")
    print("wechat payment signing, decrypt and idempotency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
