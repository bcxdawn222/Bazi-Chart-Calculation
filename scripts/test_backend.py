from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import Database


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        database = Database(Path(directory) / "test.sqlite3")
        chart = database.create_chart("tester", {"pillars": ["己巳", "丙子", "丙寅", "甲午"]})
        assert chart["user_id"] == "tester"
        assert database.list_charts("tester")[0]["payload"]["pillars"] == ["己巳", "丙子", "丙寅", "甲午"]
        prayer = database.create_prayer("tester", {"title": "平安"})
        wish = database.create_wish("tester", {"content": "顺利"})
        consultation = database.create_consultation("tester", {"channel": "wechat-contact"})
        assert prayer["status"] == wish["status"] == consultation["status"] == "active"
        prayer = database.update_record("prayers", prayer["id"], "tester", "completed")
        assert prayer["status"] == "completed"
        database.delete_record("wishes", wish["id"], "tester")
        assert database.list_wishes("tester") == []
        user = database.upsert_user("openid-test", "unionid-test")
        assert database.upsert_user("openid-test")["id"] == user["id"]
        user = database.update_user(str(user["id"]), "测试用户", "https://example.invalid/avatar.png")
        assert user["nickname"] == "测试用户"
        token, expires_at = database.create_session(str(user["id"]), "session-secret")
        assert expires_at
        assert database.resolve_session(token, "session-secret") == user["id"]
        assert database.resolve_session(token, "wrong-secret") is None
        assert database.list_experts() == []
        expert = database.create_expert({
            "display_name": "测试老师", "bio": "固定样例", "avatar_url": "",
            "status": "online", "price_cents": 19900,
        })
        assert expert["price_cents"] == 19900
        expert = database.update_expert(str(expert["id"]), {"status": "offline", "price_cents": 29900})
        assert expert["status"] == "offline" and expert["price_cents"] == 29900
        schedule = database.create_schedule({
            "expert_id": expert["id"], "starts_at": "2026-09-01T09:00:00+08:00",
            "ends_at": "2026-09-01T10:00:00+08:00", "status": "available",
        })
        assert database.list_schedules(str(expert["id"]))[0]["id"] == schedule["id"]
        order = database.create_order(str(user["id"]), {
            "subject": "咨询排盘结果", "expert_id": expert["id"], "schedule_id": schedule["id"],
        })
        assert order["payment_status"] == "not_configured"
        assert order["amount_cents"] == 29900
        assert database.list_orders(str(user["id"]))[0]["id"] == order["id"]
        assert database.get_public_order(str(order["id"]), str(user["id"]))["id"] == order["id"]
        assert database.list_ops_orders()[0]["id"] == order["id"]
        order = database.update_order_service_status(str(order["id"]), "confirmed")
        assert order["service_status"] == "confirmed"
        review = database.create_review(str(user["id"]), {
            "order_id": order["id"], "rating": 5, "content": "测试评价"
        })
        assert review["rating"] == 5
        config = database.public_config()
        assert config["payment.enabled"] is False
        database.set_config("consultation.enabled", False, True)
        assert database.public_config()["consultation.enabled"] is False
    print("backend database checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
