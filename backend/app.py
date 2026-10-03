from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .analysis_ai import AnalysisAIError, generate_analysis_sections, is_valid_chart
from .analysis_store import analysis_price_cents, parse_chart_key
from .config import Settings
from .db import Database, JsonObject
from .http_base import JsonApiHandler, as_object, configure_logging, resource_id
from .record_api import list_records, parse_record_path, validate_status
from .wechat import exchange_code
from .payment_api import process_wechat_notification, prepare_order_payment
from . import ops_api
from .wechat_payments import PaymentError, WechatPayClient


class ApiHandler(JsonApiHandler):
    server_version = "BaziZiweiBackend/0.1"

    def do_GET(self) -> None:
        if not self.check_rate_limit():
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            if path == "/health":
                self.send_json(HTTPStatus.OK, {"status": "ok", "service": "bazi-ziwei"})
                return
            if path == "/api/config":
                config = self.database.public_config()
                payment_ready = WechatPayClient.from_settings(self.settings).configured
                payment_enabled = config.get("payment.enabled") is True and payment_ready
                price_cents = analysis_price_cents(config)
                ai_ready = bool(self.settings.ai_api_url and self.settings.ai_api_key)
                ai_reason = str(config.get("ai.reason") or "")
                if config.get("ai.enabled") is True and not ai_ready and not ai_reason:
                    ai_reason = "待确认 AI 接入范围和密钥"
                self.send_json(HTTPStatus.OK, {
                    "wechatLogin": bool(self.settings.wx_app_id and self.settings.wx_app_secret and self.settings.session_secret),
                    "consultation": {
                        "enabled": config.get("consultation.enabled") is True,
                        "channel": config.get("consultation.channel", "wechat-contact"),
                        "reason": config.get("consultation.reason", ""),
                    },
                    "payment": {"enabled": payment_enabled, "reason": config.get("payment.reason", "")},
                    "ai": {
                        "enabled": config.get("ai.enabled") is True and ai_ready,
                        "reason": ai_reason,
                    },
                    "analysis": {
                        "enabled": payment_enabled and price_cents is not None and price_cents > 0,
                        "price_cents": price_cents,
                        "reason": str(config.get("analysis.reason") or ""),
                    },
                })
                return
            if path == "/api/experts":
                self.send_json(HTTPStatus.OK, {"items": self.database.list_experts()})
                return
            if path == "/api/schedules":
                self.send_json(HTTPStatus.OK, {
                    "items": self.database.list_public_schedules(query.get("expert_id", [""])[0])
                })
                return
            if path.startswith("/api/ops/"):
                self.require_admin()
                result = ops_api.get(self.database, path, query)
                if result:
                    self.send_json(*result)
                    return
            if path == "/api/users/me":
                self.send_json(HTTPStatus.OK, {"item": self.database.get_user(self.user_id())})
                return
            if path == "/api/analysis-orders":
                user_id = self.user_id()
                chart_key = parse_chart_key((query.get("chart_key") or [""])[0])
                self.send_json(HTTPStatus.OK, {"item": self.database.get_analysis_order(user_id, chart_key)})
                return
            if path == "/api/analysis-reports":
                user_id = self.user_id()
                chart_key = parse_chart_key((query.get("chart_key") or [""])[0])
                self.send_json(HTTPStatus.OK, {"item": self.database.public_analysis_report(user_id, chart_key)})
                return
            if path == "/api/orders":
                self.send_json(HTTPStatus.OK, {"items": self.database.list_orders(self.user_id())})
                return
            order_id = resource_id(path, "/api/orders")
            if order_id:
                self.send_json(HTTPStatus.OK, {"item": self.database.get_public_order(order_id, self.user_id())})
                return
            self.send_record_get(path, query)
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "记录不存在"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except PermissionError as error:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def send_record_get(self, path: str, query: dict[str, list[str]]) -> None:
        del query
        user = self.user_id()
        records = list_records(self.database, path, user)
        if records is not None:
            self.send_json(HTTPStatus.OK, {"items": records})
            return
        target = parse_record_path(path)
        if target:
            table, record_id = target
            self.send_json(HTTPStatus.OK, {"item": self.database.get_for_user(table, record_id, user)})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})

    def do_PATCH(self) -> None:
        if not self.check_rate_limit():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path.startswith("/api/ops/"):
                self.require_admin()
                result = ops_api.patch(self.database, path, self.read_body())
                if result:
                    self.send_json(*result)
                    return
            target = parse_record_path(path)
            if not target:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
                return
            table, record_id = target
            status = validate_status(table, str(self.read_body().get("status", "")).strip())
            item = self.database.update_record(table, record_id, self.user_id(), status)
            self.send_json(HTTPStatus.OK, {"item": item})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "记录不存在"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except PermissionError as error:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def do_PUT(self) -> None:
        if not self.check_rate_limit():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            self.require_admin()
            result = ops_api.put(self.database, path, self.read_body())
            if result is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
                return
            self.send_json(*result)
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "记录不存在"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except PermissionError as error:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def do_DELETE(self) -> None:
        if not self.check_rate_limit():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path.startswith("/api/ops/"):
                self.require_admin()
                result = ops_api.delete(self.database, path)
                if result:
                    self.send_json(*result)
                    return
            target = parse_record_path(path)
            if not target:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
                return
            table, record_id = target
            self.database.delete_record(table, record_id, self.user_id())
            self.send_json(HTTPStatus.OK, {"status": "deleted", "id": record_id})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "记录不存在"})
        except PermissionError as error:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def do_POST(self) -> None:
        if not self.check_rate_limit():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/api/payments/wechat/notify":
                self.handle_wechat_notify()
                return
            body = self.read_body()
            if path == "/api/auth/wechat":
                self.handle_wechat_login(body)
                return
            if path == "/api/users/me":
                nickname = str(body.get("nickname", "")).strip()[:40]
                avatar_url = str(body.get("avatar_url", "")).strip()[:500]
                self.send_json(HTTPStatus.OK, {"item": self.database.update_user(self.user_id(), nickname, avatar_url)})
                return
            if path.startswith("/api/ops/"):
                self.require_admin()
                result = ops_api.post(self.database, path, body)
                if result:
                    self.send_json(*result)
                    return
            if path == "/api/orders":
                user_id = self.user_id()
                config = self.database.public_config()
                if config.get("consultation.enabled") is not True:
                    raise RuntimeError(str(config.get("consultation.reason") or "咨询服务暂未开放"))
                if config.get("payment.enabled") is not True or not WechatPayClient.from_settings(self.settings).configured:
                    raise RuntimeError(str(config.get("payment.reason") or "微信支付暂未开放"))
                self.send_json(HTTPStatus.CREATED, {"item": self.database.create_order(user_id, body)})
                return
            if path.startswith("/api/orders/") and path.endswith("/pay"):
                self.handle_order_payment(path.split("/")[-2])
                return
            if path == "/api/reviews":
                self.send_json(HTTPStatus.CREATED, {"item": self.database.create_review(self.user_id(), body)})
                return
            if path == "/api/analysis-orders":
                user_id = self.user_id()
                config = self.database.public_config()
                payment_ready = WechatPayClient.from_settings(self.settings).configured
                if config.get("payment.enabled") is not True or not payment_ready:
                    raise RuntimeError(str(config.get("payment.reason") or "支付或售价未配置"))
                price = analysis_price_cents(config)
                if price is None or price <= 0:
                    raise RuntimeError(str(config.get("analysis.reason") or "支付或售价未配置"))
                self.send_json(HTTPStatus.CREATED, {"item": self.database.create_analysis_order(user_id, body)})
                return
            if path == "/api/analysis-reports/generate":
                self.handle_analysis_generate(body)
                return
            handlers = {
                "/api/charts": self.database.create_chart,
                "/api/prayers": self.database.create_prayer,
                "/api/wishes": self.database.create_wish,
                "/api/consultations": self.database.create_consultation,
            }
            handler = handlers.get(path)
            if handler is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
                return
            payload = as_object(body.get("payload"))
            record = handler(self.user_id(body), payload)
            self.send_json(HTTPStatus.CREATED, {"item": record})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "关联记录不存在"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except PermissionError as error:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def handle_order_payment(self, order_id: str) -> None:
        user_id = self.user_id()
        saved, payment = prepare_order_payment(self.database, self.settings, order_id, user_id)
        self.send_json(HTTPStatus.OK, {"item": saved, "payment": payment})

    def handle_analysis_generate(self, body: JsonObject) -> None:
        user_id = self.user_id()
        chart_key = parse_chart_key(body.get("chart_key"))
        chart = body.get("chart")
        if not isinstance(chart, dict) or not is_valid_chart(chart):
            raise ValueError("命盘结构无效")
        if not self.database.has_paid_analysis_order(user_id, chart_key):
            raise ValueError("该命盘尚未支付详细解读")
        config = self.database.public_config()
        if config.get("ai.enabled") is not True or not self.settings.ai_api_url or not self.settings.ai_api_key:
            raise RuntimeError(str(config.get("ai.reason") or "AI 未配置"))
        try:
            sections = generate_analysis_sections(chart, self.settings)
        except AnalysisAIError as error:
            logging.warning("详细解读生成失败：%s", error)
            self.send_json(HTTPStatus.OK, {
                "item": self.database.public_analysis_report(
                    user_id, chart_key, pending_reason="详细解读尚未生成",
                ),
            })
            return
        self.send_json(
            HTTPStatus.OK,
            {"item": self.database.upsert_analysis_report(user_id, chart_key, sections, "ai")},
        )

    def handle_wechat_notify(self) -> None:
        try:
            raw = self.read_raw_body()
            headers = {key: value for key, value in self.headers.items()}
            process_wechat_notification(self.database, self.settings, headers, raw)
            self.send_json(HTTPStatus.OK, {"code": "SUCCESS", "message": "成功"})
        except KeyError:
            self.send_json(HTTPStatus.NOT_FOUND, {"code": "FAIL", "message": "订单不存在"})
        except (PaymentError, ValueError, TypeError, json.JSONDecodeError) as error:
            logging.warning("微信支付通知处理失败：%s", error)
            self.send_json(HTTPStatus.BAD_REQUEST, {"code": "FAIL", "message": "通知处理失败"})

    def handle_wechat_login(self, body: JsonObject) -> None:
        if not str(body.get("code", "")).strip():
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "缺少微信登录 code"})
            return
        if not (self.settings.wx_app_id and self.settings.wx_app_secret):
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "status": "not_configured",
                "error": "微信登录参数尚未配置，当前保留本地模式",
            })
            return
        if not self.settings.session_secret:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "not_configured", "error": "会话密钥尚未配置"})
            return
        identity = exchange_code(self.settings.wx_app_id, self.settings.wx_app_secret, str(body["code"]).strip())
        user = self.database.upsert_user(identity.openid, identity.unionid)
        token, expires_at = self.database.create_session(str(user["id"]), self.settings.session_secret)
        self.send_json(HTTPStatus.OK, {"status": "ok", "token": token, "expires_at": expires_at, "user": user})


class ApiServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], settings: Settings) -> None:
        super().__init__(address, ApiHandler)
        self.settings = settings
        self.database = Database(settings.db_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="八字紫微小程序后端")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.host:
        settings = replace(settings, host=args.host)
    if args.port:
        settings = replace(settings, port=args.port)
    configure_logging(settings)
    server = ApiServer((settings.host, settings.port), settings)
    logging.info("后端启动 host=%s port=%s db=%s", settings.host, settings.port, settings.db_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("后端收到停止信号")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
