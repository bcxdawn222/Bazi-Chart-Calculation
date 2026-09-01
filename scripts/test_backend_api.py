from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import ApiServer
from backend.config import Settings


def request(base: str, path: str, *, method: str = "GET", token: str = "", admin: str = "", data: object = None) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if admin:
        headers["X-Admin-Token"] = admin
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "{}")


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        private_key = root / "merchant.pem"
        platform_key = root / "platform.pem"
        private_key.write_text("test", encoding="utf-8")
        platform_key.write_text("test", encoding="utf-8")
        settings = Settings(
            host="127.0.0.1",
            port=0,
            db_path=root / "api.sqlite3",
            log_path=root / "api.log",
            wx_app_id="wx-test",
            wx_app_secret="",
            session_secret="test-session-secret",
            admin_token="test-admin-token",
            allowed_origins=("https://example.invalid",),
            wx_pay_mch_id="mch-test",
            wx_pay_serial_no="merchant-serial",
            wx_pay_private_key_path=private_key,
            wx_pay_api_v3_key="12345678901234567890123456789012",
            wx_pay_notify_url="https://example.invalid/api/payments/wechat/notify",
            wx_pay_platform_serial_no="platform-serial",
            wx_pay_platform_public_key_path=platform_key,
        )
        server = ApiServer((settings.host, settings.port), settings)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            assert request(base, "/health")[0] == 200
            status, config = request(base, "/api/config")
            assert status == 200 and config["wechatLogin"] is False
            assert request(base, "/api/charts")[0] == 401
            assert request(base, "/api/auth/wechat", method="POST", data={"code": "test"})[0] == 503

            user = server.database.upsert_user("api-openid")
            token, _ = server.database.create_session(str(user["id"]), settings.session_secret)
            status, chart = request(
                base, "/api/charts", method="POST", token=token,
                data={"payload": {"pillars": ["己巳", "丙子", "丙寅", "甲午"]}},
            )
            assert status == 201 and chart["item"]["user_id"] == user["id"]
            status, charts = request(base, "/api/charts", token=token)
            assert status == 200 and len(charts["items"]) == 1
            chart_id = str(chart["item"]["id"])
            status, updated = request(
                base, "/api/charts/" + chart_id, method="PATCH", token=token,
                data={"status": "archived"},
            )
            assert status == 200 and updated["item"]["status"] == "archived"
            assert request(
                base, "/api/charts/" + chart_id, method="PATCH", token=token,
                data={"status": "completed"},
            )[0] == 400
            other_user = server.database.upsert_user("other-openid")
            other_token, _ = server.database.create_session(str(other_user["id"]), settings.session_secret)
            assert request(base, "/api/charts/" + chart_id, method="DELETE", token=other_token)[0] == 404
            assert request(base, "/api/charts/" + chart_id, method="DELETE", token=token)[0] == 200
            assert request(base, "/api/charts/" + chart_id, token=token)[0] == 404
            assert request(base, "/api/experts")[1]["items"] == []
            assert request(
                base, "/api/orders", method="POST",
                data={"subject": "未登录", "expert_id": "missing", "schedule_id": "missing"},
            )[0] == 401
            assert request(
                base, "/api/orders", method="POST", token=token,
                data={"subject": "无效专家", "expert_id": "missing", "schedule_id": "missing"},
            )[0] == 503
            server.database.set_config("payment.enabled", True, True)
            assert request(
                base, "/api/orders", method="POST", token=token,
                data={"subject": "无效专家", "expert_id": "missing", "schedule_id": "missing"},
            )[0] == 400

            status, expert = request(
                base, "/api/ops/experts", method="POST", admin=settings.admin_token,
                data={
                    "display_name": "测试老师", "bio": "固定样例", "avatar_url": "",
                    "status": "online", "price_cents": 19900,
                },
            )
            assert status == 201 and expert["item"]["price_cents"] == 19900
            expert_id = str(expert["item"]["id"])
            assert request(
                base, "/api/ops/experts/" + expert_id, method="PUT", admin=settings.admin_token,
                data={"status": "offline", "price_cents": 29900},
            )[1]["item"]["status"] == "offline"
            assert request(base, "/api/experts")[1]["items"] == []
            assert request(
                base, "/api/ops/experts/" + expert_id, method="PUT", admin=settings.admin_token,
                data={"status": "online"},
            )[0] == 200
            status, schedule = request(
                base, "/api/ops/schedules", method="POST", admin=settings.admin_token,
                data={
                    "expert_id": expert_id,
                    "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    "ends_at": (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).isoformat(),
                    "status": "available",
                },
            )
            assert status == 201 and schedule["item"]["expert_id"] == expert_id
            assert request(
                base, "/api/ops/schedules", method="POST", admin=settings.admin_token,
                data={
                    "expert_id": expert_id,
                    "starts_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                    "ends_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                    "status": "available",
                },
            )[0] == 400
            assert request(
                base, "/api/orders", method="POST", token=token,
                data={"subject": "缺少排班", "expert_id": expert_id},
            )[0] == 400

            status, order = request(
                base, "/api/orders", method="POST", token=token,
                data={
                    "subject": "排盘咨询", "expert_id": expert_id,
                    "schedule_id": schedule["item"]["id"],
                },
            )
            assert status == 201 and order["item"]["amount_cents"] == 29900
            order_id = str(order["item"]["id"])
            assert request(base, "/api/orders/" + order_id, token=token)[1]["item"]["id"] == order_id
            assert request(base, "/api/orders/" + order_id, token=other_token)[0] == 404
            assert request(
                base, "/api/orders", method="POST", token=other_token,
                data={
                    "subject": "重复预约", "expert_id": expert_id,
                    "schedule_id": schedule["item"]["id"],
                },
            )[0] == 400
            assert request(base, "/api/ops/orders", admin=settings.admin_token)[1]["items"][0]["id"] == order_id
            filtered_orders = request(
                base, "/api/ops/orders?payment_status=not_configured&service_status=pending",
                admin=settings.admin_token,
            )[1]["items"]
            assert len(filtered_orders) == 1 and filtered_orders[0]["id"] == order_id
            status, serviced = request(
                base, "/api/ops/orders/" + order_id, method="PATCH", admin=settings.admin_token,
                data={"service_status": "confirmed"},
            )
            assert status == 400
            server.database.mark_order_paid(
                order_id, "wx-api-service", 29900, server.database.now(), "notify-api-service",
            )
            status, serviced = request(
                base, "/api/ops/orders/" + order_id, method="PATCH", admin=settings.admin_token,
                data={"service_status": "confirmed"},
            )
            assert status == 200 and serviced["item"]["service_status"] == "confirmed"
            assert request(
                base, "/api/ops/orders/" + order_id, method="PATCH", admin=settings.admin_token,
                data={"payment_status": "paid"},
            )[0] == 400
            assert request(base, "/api/orders/" + order["item"]["id"] + "/pay", method="POST", token=token, data={})[0] == 400
            assert request(
                base, "/api/reviews", method="POST", token=token,
                data={"order_id": "missing", "rating": 5, "content": "不存在订单"},
            )[0] == 404
            assert request(
                base, "/api/reviews", method="POST", token=token,
                data={"order_id": order["item"]["id"], "rating": None, "content": "非法评分"},
            )[0] == 400
            assert request(
                base, "/api/reviews", method="POST", token=token,
                data={"order_id": order["item"]["id"], "rating": 5, "content": "固定样例"},
            )[0] == 400
            assert request(
                base, "/api/ops/orders/" + order_id, method="PATCH", admin=settings.admin_token,
                data={"service_status": "completed"},
            )[0] == 200
            status, review = request(
                base, "/api/reviews", method="POST", token=token,
                data={"order_id": order["item"]["id"], "rating": 5, "content": "固定样例"},
            )
            assert status == 201 and review["item"]["rating"] == 5
            assert request(
                base, "/api/reviews", method="POST", token=token,
                data={"order_id": order["item"]["id"], "rating": 4, "content": "重复评价"},
            )[0] == 400
            server.database.set_config("consultation.enabled", False, True)
            assert request(
                base, "/api/orders", method="POST", token=other_token,
                data={
                    "subject": "关闭期间预约", "expert_id": expert_id,
                    "schedule_id": schedule["item"]["id"],
                },
            )[0] == 503
            assert request(base, "/api/ops/config", method="POST", data={"key": "ai.enabled", "value": True})[0] == 401
            assert request(
                base, "/api/ops/config", method="POST", admin=settings.admin_token,
                data={"key": "ai.enabled", "value": True, "is_public": "true"},
            )[0] == 400
            assert request(
                base, "/api/ops/config", method="POST", admin=settings.admin_token,
                data={"key": "ai.enabled", "value": True, "is_public": True},
            )[0] == 200
            assert request(base, "/api/config")[1]["ai"]["enabled"] is True
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("backend API checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
