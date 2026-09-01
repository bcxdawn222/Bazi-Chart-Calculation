from __future__ import annotations

import tempfile
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import Database
from backend.http_base import request_client_ip


def main() -> int:
    assert request_client_ip("127.0.0.1", "203.0.113.7, 127.0.0.1") == "203.0.113.7"
    assert request_client_ip("127.0.0.1", "invalid") == "127.0.0.1"
    assert request_client_ip("198.51.100.8", "203.0.113.7") == "198.51.100.8"
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
        assert database.list_experts() == []
        expert = database.update_expert(str(expert["id"]), {"status": "online"})
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = future_start + timedelta(hours=1)
        try:
            database.create_schedule({
                "expert_id": expert["id"],
                "starts_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "ends_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "status": "available",
            })
        except ValueError:
            pass
        else:
            raise AssertionError("已过期排班不能继续开放预约")
        schedule = database.create_schedule({
            "expert_id": expert["id"], "starts_at": future_start.isoformat(),
            "ends_at": future_end.isoformat(), "status": "available",
        })
        assert database.list_schedules(str(expert["id"]))[0]["id"] == schedule["id"]
        timestamp = database.now()
        with database.connect() as connection:
            connection.executemany(
                "INSERT INTO expert_schedules "
                "(id, expert_id, starts_at, ends_at, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'available', ?, ?)",
                [
                    (
                        f"expired-{index}", expert["id"],
                        (future_start - timedelta(days=index + 2)).isoformat(),
                        (future_end - timedelta(days=index + 2)).isoformat(), timestamp, timestamp,
                    )
                    for index in range(205)
                ],
            )
        assert schedule["id"] in {item["id"] for item in database.list_public_schedules(str(expert["id"]))}
        try:
            database.create_order(str(user["id"]), {"subject": "缺少排班", "expert_id": expert["id"]})
        except ValueError:
            pass
        else:
            raise AssertionError("咨询订单必须绑定可用排班")
        order = database.create_order(str(user["id"]), {
            "subject": "咨询排盘结果", "expert_id": expert["id"], "schedule_id": schedule["id"],
        })
        assert order["payment_status"] == "not_configured"
        assert order["amount_cents"] == 29900
        assert database.list_orders(str(user["id"]))[0]["id"] == order["id"]
        assert database.get_public_order(str(order["id"]), str(user["id"]))["id"] == order["id"]
        assert database.list_ops_orders()[0]["id"] == order["id"]
        assert database.list_ops_orders(payment_status="not_configured")[0]["id"] == order["id"]
        assert database.list_ops_orders(service_status="pending")[0]["id"] == order["id"]
        assert database.list_ops_orders(payment_status="paid") == []
        try:
            database.update_schedule(str(schedule["id"]), {"starts_at": (future_start + timedelta(hours=2)).isoformat()})
        except ValueError:
            pass
        else:
            raise AssertionError("已有订单的排班时间不能被修改")
        other_user = database.upsert_user("other-openid")
        try:
            database.create_order(str(other_user["id"]), {
                "subject": "重复预约", "expert_id": expert["id"], "schedule_id": schedule["id"],
            })
        except ValueError:
            pass
        else:
            raise AssertionError("同一排班不能生成多个有效订单")
        overlapping_schedule = database.create_schedule({
            "expert_id": expert["id"], "starts_at": (future_start + timedelta(minutes=30)).isoformat(),
            "ends_at": (future_end + timedelta(minutes=30)).isoformat(), "status": "available",
        })
        assert overlapping_schedule["id"] not in {
            item["id"] for item in database.list_public_schedules(str(expert["id"]))
        }
        try:
            database.create_order(str(other_user["id"]), {
                "subject": "重叠预约", "expert_id": expert["id"], "schedule_id": overlapping_schedule["id"],
            })
        except ValueError:
            pass
        else:
            raise AssertionError("同一专家的重叠时段不能重复预约")
        concurrent_schedule = database.create_schedule({
            "expert_id": expert["id"], "starts_at": (future_start + timedelta(days=1)).isoformat(),
            "ends_at": (future_end + timedelta(days=1)).isoformat(), "status": "available",
        })
        def reserve(user_id: str) -> bool:
            try:
                database.create_order(user_id, {
                    "subject": "并发预约", "expert_id": expert["id"], "schedule_id": concurrent_schedule["id"],
                })
            except ValueError:
                return False
            return True
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(reserve, (str(user["id"]), str(other_user["id"]))))
        assert results.count(True) == 1 and results.count(False) == 1
        try:
            database.update_order_service_status(str(order["id"]), "confirmed")
        except ValueError:
            pass
        else:
            raise AssertionError("未支付订单不能确认服务")
        database.mark_order_pending(str(order["id"]), str(user["id"]), "prepay-test")
        try:
            database.update_order_service_status(str(order["id"]), "cancelled")
        except ValueError:
            pass
        else:
            raise AssertionError("支付已发起的订单不能直接取消")
        order = database.mark_order_paid(
            str(order["id"]), "wx-test-service", 29900, database.now(), "notify-service",
        )
        order = database.update_order_service_status(str(order["id"]), "confirmed")
        assert order["service_status"] == "confirmed"
        try:
            database.create_review(str(user["id"]), {
                "order_id": order["id"], "rating": 5, "content": "服务尚未完成",
            })
        except ValueError:
            pass
        else:
            raise AssertionError("服务完成前不能评价")
        order = database.update_order_service_status(str(order["id"]), "completed")
        review = database.create_review(str(user["id"]), {
            "order_id": order["id"], "rating": 5, "content": "测试评价"
        })
        assert review["rating"] == 5
        try:
            database.create_review(str(user["id"]), {
                "order_id": order["id"], "rating": 4, "content": "重复评价",
            })
        except ValueError:
            pass
        else:
            raise AssertionError("同一订单只能评价一次")
        legacy_schedule = database.create_schedule({
            "expert_id": expert["id"], "starts_at": (future_start + timedelta(days=3)).isoformat(),
            "ends_at": (future_end + timedelta(days=3)).isoformat(), "status": "available",
        })
        legacy_order = database.create_order(str(user["id"]), {
            "subject": "旧状态兼容", "expert_id": expert["id"], "schedule_id": legacy_schedule["id"],
        })
        legacy_order = database.update_order_service_status(str(legacy_order["id"]), "cancelled")
        assert legacy_order["service_status"] == "cancelled"
        legacy_order = database.mark_order_paid(
            str(legacy_order["id"]), "wx-test-legacy", 29900, database.now(), "notify-legacy",
        )
        assert legacy_order["payment_status"] == "paid" and legacy_order["service_status"] == "pending"
        config = database.public_config()
        assert config["payment.enabled"] is False
        database.set_config("consultation.enabled", False, True)
        assert database.public_config()["consultation.enabled"] is False
    print("backend database checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
