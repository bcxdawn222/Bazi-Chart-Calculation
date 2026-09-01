from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import Settings


class PaymentError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedPaymentNotification:
    notify_id: str
    app_id: str
    mch_id: str
    out_trade_no: str
    transaction_id: str
    trade_state: str
    amount_total: int
    currency: str
    success_time: str


def _required_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key)
    return value.strip()


@dataclass(frozen=True)
class WechatPayClient:
    app_id: str
    mch_id: str
    serial_no: str
    private_key_path: Path
    api_v3_key: str
    notify_url: str
    platform_serial_no: str
    platform_public_key_path: Path

    @classmethod
    def from_settings(cls, settings: Settings) -> "WechatPayClient":
        return cls(
            app_id=settings.wx_app_id, mch_id=settings.wx_pay_mch_id,
            serial_no=settings.wx_pay_serial_no, private_key_path=settings.wx_pay_private_key_path,
            api_v3_key=settings.wx_pay_api_v3_key, notify_url=settings.wx_pay_notify_url,
            platform_serial_no=settings.wx_pay_platform_serial_no,
            platform_public_key_path=settings.wx_pay_platform_public_key_path,
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.app_id and self.mch_id and self.serial_no and self.private_key_path.is_file()
            and len(self.api_v3_key.encode("utf-8")) == 32 and self.notify_url.startswith("https://")
            and self.platform_serial_no and self.platform_public_key_path.is_file()
        )

    def _private_key(self):
        try:
            return serialization.load_pem_private_key(self.private_key_path.read_bytes(), password=None)
        except (OSError, ValueError) as error:
            raise PaymentError("微信支付商户私钥不可用") from error

    def _platform_key(self):
        try:
            raw = self.platform_public_key_path.read_bytes()
            try:
                return serialization.load_pem_public_key(raw)
            except ValueError:
                return x509.load_pem_x509_certificate(raw).public_key()
        except (OSError, ValueError) as error:
            raise PaymentError("微信支付平台公钥不可用") from error

    def _sign(self, message: bytes) -> str:
        signature = self._private_key().sign(message, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("ascii")

    def _authorization(self, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
        message = b"\n".join((method.encode(), path.encode(), timestamp.encode(), nonce.encode(), body, b""))
        signature = self._sign(message)
        return (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mch_id}",nonce_str="{nonce}",'
            f'signature="{signature}",timestamp="{timestamp}",serial_no="{self.serial_no}"'
        )

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(16)
        request = urllib.request.Request(
            "https://api.mch.weixin.qq.com" + path,
            data=body if method != "GET" else None, method=method,
            headers={
                "Accept": "application/json", "Content-Type": "application/json",
                "User-Agent": "bazi-ziwei-wechat-pay/1.0",
                "Authorization": self._authorization(method, path, timestamp, nonce, body),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as error:
            raise PaymentError("微信支付接口暂不可用") from error
        if not isinstance(result, dict):
            raise PaymentError("微信支付返回内容无效")
        return {str(key): value for key, value in result.items()}

    def create_jsapi_payment(self, out_trade_no: str, description: str, total_cents: int, openid: str) -> dict[str, str]:
        if not self.configured:
            raise PaymentError("微信支付参数尚未完整配置")
        prepay = self._request("POST", "/v3/pay/transactions/jsapi", {
            "appid": self.app_id, "mchid": self.mch_id, "description": description[:127],
            "out_trade_no": out_trade_no, "notify_url": self.notify_url,
            "amount": {"total": total_cents, "currency": "CNY"}, "payer": {"openid": openid},
        })
        prepay_id = str(prepay.get("prepay_id", ""))
        if not prepay_id:
            raise PaymentError("微信支付未返回预支付标识")
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(16)
        package = "prepay_id=" + prepay_id
        message = "\n".join((self.app_id, timestamp, nonce, package, ""))
        return {
            "timeStamp": timestamp, "nonceStr": nonce, "package": package,
            "signType": "RSA", "paySign": self._sign(message.encode("utf-8")), "prepayId": prepay_id,
        }

    def verify_notification(self, headers: dict[str, str], body: bytes) -> VerifiedPaymentNotification:
        timestamp = headers.get("Wechatpay-Timestamp", "")
        nonce = headers.get("Wechatpay-Nonce", "")
        signature = headers.get("Wechatpay-Signature", "")
        serial = headers.get("Wechatpay-Serial", "")
        try:
            if abs(int(time.time()) - int(timestamp)) > 300 or serial != self.platform_serial_no:
                raise ValueError("notification metadata")
            signed = (timestamp + "\n" + nonce + "\n").encode("utf-8") + body + b"\n"
            self._platform_key().verify(base64.b64decode(signature), signed, padding.PKCS1v15(), hashes.SHA256())
            envelope = json.loads(body.decode("utf-8"))
            resource = envelope["resource"]
            ciphertext = base64.b64decode(resource["ciphertext"])
            plain = AESGCM(self.api_v3_key.encode("utf-8")).decrypt(
                resource["nonce"].encode("utf-8"), ciphertext,
                resource.get("associated_data", "").encode("utf-8"),
            )
            result = json.loads(plain.decode("utf-8"))
            if not isinstance(envelope, dict) or not isinstance(result, dict):
                raise TypeError("notification payload")
            envelope_data = {str(key): value for key, value in envelope.items()}
            transaction = {str(key): value for key, value in result.items()}
            amount = transaction.get("amount")
            if not isinstance(amount, dict):
                raise TypeError("amount")
            amount_data = {str(key): value for key, value in amount.items()}
            notification = VerifiedPaymentNotification(
                notify_id=_required_text(envelope_data, "id"),
                app_id=_required_text(transaction, "appid"),
                mch_id=_required_text(transaction, "mchid"),
                out_trade_no=_required_text(transaction, "out_trade_no"),
                transaction_id=_required_text(transaction, "transaction_id"),
                trade_state=_required_text(transaction, "trade_state"),
                amount_total=int(amount_data["total"]),
                currency=_required_text(amount_data, "currency"),
                success_time=str(transaction.get("success_time", "")),
            )
        except (KeyError, ValueError, TypeError, UnicodeDecodeError, InvalidSignature, json.JSONDecodeError, base64.binascii.Error) as error:
            raise PaymentError("微信支付通知验签或解密失败") from error
        return notification
