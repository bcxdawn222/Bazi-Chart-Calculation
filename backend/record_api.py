from __future__ import annotations

from collections.abc import Callable

from .db import Database
from .record_store import StoredRecord


COLLECTIONS = {
    "/api/charts": "charts",
    "/api/prayers": "prayers",
    "/api/wishes": "wishes",
    "/api/consultations": "consultations",
}

ALLOWED_STATUSES = {
    "charts": {"active", "archived"},
    "prayers": {"active", "completed"},
    "wishes": {"active", "completed"},
    "consultations": {"active", "completed", "cancelled"},
}


def parse_record_path(path: str) -> tuple[str, str] | None:
    for prefix, table in COLLECTIONS.items():
        if path.startswith(prefix + "/"):
            record_id = path.removeprefix(prefix + "/").strip()
            if record_id and "/" not in record_id:
                return table, record_id
    return None


def list_records(database: Database, path: str, user_id: str) -> list[StoredRecord] | None:
    methods: dict[str, Callable[[str], list[StoredRecord]]] = {
        "/api/charts": database.list_charts,
        "/api/prayers": database.list_prayers,
        "/api/wishes": database.list_wishes,
        "/api/consultations": database.list_consultations,
    }
    method = methods.get(path)
    return method(user_id) if method else None


def validate_status(table: str, status: str) -> str:
    if status not in ALLOWED_STATUSES[table]:
        allowed = "、".join(sorted(ALLOWED_STATUSES[table]))
        raise ValueError(f"{table} 状态只允许：{allowed}")
    return status
