from __future__ import annotations

from http import HTTPStatus

from .db import Database, JsonObject


ApiResult = tuple[HTTPStatus, JsonObject]


def _resource_id(path: str, prefix: str) -> str | None:
    if not path.startswith(prefix + "/"):
        return None
    value = path.removeprefix(prefix + "/").strip()
    return value if value and "/" not in value else None


def get(database: Database, path: str, query: dict[str, list[str]]) -> ApiResult | None:
    if path == "/api/ops/experts":
        return HTTPStatus.OK, {"items": database.list_ops_experts()}
    if path == "/api/ops/schedules":
        return HTTPStatus.OK, {"items": database.list_schedules(query.get("expert_id", [""])[0])}
    if path == "/api/ops/orders":
        return HTTPStatus.OK, {"items": database.list_ops_orders(
            query.get("payment_status", [""])[0], query.get("service_status", [""])[0],
        )}
    return None


def post(database: Database, path: str, body: JsonObject) -> ApiResult | None:
    if path == "/api/ops/config":
        key = str(body.get("key", "")).strip()
        if not key or len(key) > 80:
            raise ValueError("配置键不能为空且不能超过 80 个字符")
        is_public = body.get("is_public")
        if not isinstance(is_public, bool):
            raise ValueError("is_public 必须是布尔值")
        if key in {"ai.enabled", "payment.enabled", "consultation.enabled"} and not isinstance(body.get("value"), bool):
            raise ValueError("开关配置值必须是 JSON 布尔值 true 或 false")
        if key == "analysis.price_cents":
            price = body.get("value")
            if isinstance(price, bool) or not isinstance(price, int) or price < 0:
                raise ValueError("详细解读售价必须是 0 或正整数分")
        database.set_config(key, body.get("value"), is_public)
        return HTTPStatus.OK, {"status": "updated"}
    if path == "/api/ops/experts":
        return HTTPStatus.CREATED, {"item": database.create_expert(body)}
    if path == "/api/ops/schedules":
        return HTTPStatus.CREATED, {"item": database.create_schedule(body)}
    return None


def put(database: Database, path: str, body: JsonObject) -> ApiResult | None:
    expert_id = _resource_id(path, "/api/ops/experts")
    if expert_id:
        return HTTPStatus.OK, {"item": database.update_expert(expert_id, body)}
    schedule_id = _resource_id(path, "/api/ops/schedules")
    if schedule_id:
        return HTTPStatus.OK, {"item": database.update_schedule(schedule_id, body)}
    return None


def patch(database: Database, path: str, body: JsonObject) -> ApiResult | None:
    order_id = _resource_id(path, "/api/ops/orders")
    if not order_id:
        return None
    if set(body) != {"service_status"}:
        raise ValueError("运营订单只允许更新 service_status")
    return HTTPStatus.OK, {
        "item": database.update_order_service_status(order_id, str(body["service_status"]).strip())
    }


def delete(database: Database, path: str) -> ApiResult | None:
    expert_id = _resource_id(path, "/api/ops/experts")
    if expert_id:
        return HTTPStatus.OK, {"status": database.delete_expert(expert_id), "id": expert_id}
    schedule_id = _resource_id(path, "/api/ops/schedules")
    if schedule_id:
        return HTTPStatus.OK, {"status": database.delete_schedule(schedule_id), "id": schedule_id}
    return None
