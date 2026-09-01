from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from logging.handlers import RotatingFileHandler

from .config import Settings
from .db import Database, JsonObject
from .security import RateLimiter, token_matches


MAX_BODY_BYTES = 1024 * 1024


def configure_logging(settings: Settings) -> None:
    settings.ensure_dirs()
    handler = RotatingFileHandler(
        settings.log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def as_object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("payload 必须是 JSON 对象")
    return {str(key): item for key, item in value.items()}


def resource_id(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix + "/"):
        return None
    value = path.removeprefix(prefix + "/").strip()
    return value if value and "/" not in value else None


class JsonApiHandler(BaseHTTPRequestHandler):
    rate_limiter = RateLimiter()

    @property
    def database(self) -> Database:
        return self.server.database  # type: ignore[attr-defined]

    @property
    def settings(self) -> Settings:
        return self.server.settings  # type: ignore[attr-defined]

    def log_message(self, format_string: str, *args: object) -> None:
        logging.info("%s %s", self.address_string(), format_string % args)

    def send_json(self, status: HTTPStatus, payload: JsonObject) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin", "")
        if origin and origin in self.settings.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> JsonObject:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("请求体超过 1 MB 限制")
        raw = self.rfile.read(length) if length else b"{}"
        return as_object(json.loads(raw.decode("utf-8")))

    def user_id(self, body: JsonObject | None = None) -> str:
        del body
        if not self.settings.session_secret:
            raise RuntimeError("会话服务尚未配置")
        authorization = self.headers.get("Authorization", "").strip()
        if not authorization.startswith("Bearer "):
            raise PermissionError("缺少登录会话")
        user_id = self.database.resolve_session(authorization.removeprefix("Bearer ").strip(), self.settings.session_secret)
        if not user_id:
            raise PermissionError("登录会话无效或已过期")
        return user_id

    def require_admin(self) -> None:
        token = self.headers.get("X-Admin-Token", "").strip()
        if not token_matches(token, self.settings.admin_token):
            raise PermissionError("运营配置鉴权失败")

    def check_rate_limit(self) -> bool:
        key = self.client_address[0] if self.client_address else "unknown"
        if self.rate_limiter.allow(key):
            return True
        self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "请求过于频繁，请稍后重试"})
        return False

    def do_OPTIONS(self) -> None:
        self.send_json(HTTPStatus.NO_CONTENT, {})
