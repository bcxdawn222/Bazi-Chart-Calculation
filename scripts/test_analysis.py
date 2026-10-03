from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.analysis_ai import DISCLAIMER, generate_analysis_sections, is_valid_chart
from backend.analysis_store import SECTION_KEYS
from backend.app import ApiServer
from backend.config import Settings
from backend.db import Database


PALACE_NAMES = (
    "命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
    "迁移", "交友", "官禄", "田宅", "福德", "父母",
)


def _palace(name: str) -> dict[str, object]:
    return {
        "name": name,
        "mainStars": ["紫微"],
        "auxiliaryStars": [],
        "luckyStars": [],
        "maleficStars": [],
        "brightness": [{"star": "紫微", "level": "庙"}],
        "transformations": [{"name": "化禄", "star": "紫微"}],
        "relatedPalaces": {"opposite": "夫妻", "trines": ["官禄", "交友"]},
    }


def valid_chart() -> dict[str, object]:
    return {
        "input": {"gender": "male"},
        "normalizedTime": {
            "solar": {"year": 1990, "month": 1, "day": 1},
            "lunar": {"year": 1989, "month": 12, "day": 5},
            "hour": 11,
            "minute": 41,
            "solarTimeCorrection": {"minutes": 0},
        },
        "bazi": {
            "pillars": {"year": "己巳", "month": "丙子", "day": "丙寅", "hour": "甲午"},
            "tenGods": {"year": "偏财", "month": "正官", "day": "日主", "hour": "七杀"},
            "details": {
                "elementCounts": {"wood": 2, "fire": 2, "earth": 1, "metal": 1, "water": 2},
                "pillars": [
                    {"hiddenStems": [{"stem": "戊", "tenGod": "偏财"}]},
                    {"hiddenStems": []},
                    {"hiddenStems": []},
                    {"hiddenStems": []},
                ],
            },
            "dayun": {"items": []},
            "shensha": [],
        },
        "ziwei": {
            "details": {},
            "liunian": [],
            "palaces": [_palace(name) for name in PALACE_NAMES],
        },
        "analysis": {
            "wealth": "财",
            "marriage": "姻",
            "career": "业",
            "personality": "性",
            "health": "康",
        },
    }


def fixture_sections() -> dict[str, str]:
    return {key: f"{key} 详细说明。{DISCLAIMER}" for key in SECTION_KEYS}


def fixture_http_post(url: str, api_key: str, payload: dict[str, object]) -> dict[str, object]:
    if not url or not api_key or not isinstance(payload.get("messages"), list):
        raise AssertionError("模型请求缺少地址、密钥或 messages")
    return {"choices": [{"message": {"content": json.dumps(fixture_sections(), ensure_ascii=False)}}]}


def request(base: str, path: str, *, method: str = "GET", token: str = "", data: object = None) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "{}")


def report_count(database: Database) -> int:
    with database.connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS n FROM analysis_reports").fetchone()
    return int(row["n"])


def main() -> int:
    assert is_valid_chart(valid_chart())
    assert not is_valid_chart({})
    assert not is_valid_chart({"input": {}})
    settings = Settings(
        host="127.0.0.1",
        port=0,
        db_path=Path("unused.sqlite3"),
        log_path=Path("unused.log"),
        wx_app_id="",
        wx_app_secret="",
        session_secret="session",
        admin_token="admin",
        allowed_origins=(),
        ai_api_url="https://example.invalid/v1/chat/completions",
        ai_api_key="fixture-key",
        ai_model="fixture-model",
    )
    sections = generate_analysis_sections(valid_chart(), settings, http_post=fixture_http_post)
    assert all(DISCLAIMER in sections[key] and sections[key] for key in SECTION_KEYS)
    try:
        generate_analysis_sections(
            valid_chart(), settings, http_post=lambda url, key, payload: {"choices": [{"message": {"content": "{}"}}]},
        )
    except Exception:
        pass
    else:
        raise AssertionError("无效模型 JSON 不能写成解读正文")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        private_key = root / "merchant.pem"
        platform_key = root / "platform.pem"
        private_key.write_text("test", encoding="utf-8")
        platform_key.write_text("test", encoding="utf-8")
        http_settings = Settings(
            host="127.0.0.1",
            port=0,
            db_path=root / "analysis.sqlite3",
            log_path=root / "analysis.log",
            wx_app_id="wx-test",
            wx_app_secret="",
            session_secret="test-session-secret",
            admin_token="test-admin-token",
            allowed_origins=(),
            wx_pay_mch_id="mch-test",
            wx_pay_serial_no="merchant-serial",
            wx_pay_private_key_path=private_key,
            wx_pay_api_v3_key="12345678901234567890123456789012",
            wx_pay_notify_url="https://example.invalid/api/payments/wechat/notify",
            wx_pay_platform_serial_no="platform-serial",
            wx_pay_platform_public_key_path=platform_key,
        )
        server = ApiServer((http_settings.host, http_settings.port), http_settings)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            user = server.database.upsert_user("analysis-openid")
            token, _ = server.database.create_session(str(user["id"]), http_settings.session_secret)
            server.database.set_config("payment.enabled", True, True)
            server.database.set_config("analysis.price_cents", 8800, True)
            chart_key = "ck-1990-1-1-11-41-male-early-solar"
            order = server.database.create_analysis_order(str(user["id"]), {"chart_key": chart_key})
            server.database.mark_order_paid(
                str(order["id"]), "wx-analysis-fixture", 8800, server.database.now(), "notify-analysis-fixture",
            )
            for manual in ("confirmed", "cancelled"):
                try:
                    server.database.update_order_service_status(str(order["id"]), manual)
                except ValueError:
                    pass
                else:
                    raise AssertionError("详细解读订单不能由运营手动改服务状态")
            status, blocked = request(
                base, "/api/analysis-reports/generate", method="POST", token=token,
                data={"chart_key": chart_key, "chart": valid_chart()},
            )
            assert status == 503
            assert report_count(server.database) == 0
            pending = request(base, "/api/analysis-reports?chart_key=" + chart_key, token=token)[1]["item"]
            assert pending["paid"] is True
            assert pending["sections"] == {}
            assert pending["source"] == "pending"

            keyed = Settings(
                host=http_settings.host,
                port=http_settings.port,
                db_path=http_settings.db_path,
                log_path=http_settings.log_path,
                wx_app_id=http_settings.wx_app_id,
                wx_app_secret=http_settings.wx_app_secret,
                session_secret=http_settings.session_secret,
                admin_token=http_settings.admin_token,
                allowed_origins=http_settings.allowed_origins,
                wx_pay_mch_id=http_settings.wx_pay_mch_id,
                wx_pay_serial_no=http_settings.wx_pay_serial_no,
                wx_pay_private_key_path=http_settings.wx_pay_private_key_path,
                wx_pay_api_v3_key=http_settings.wx_pay_api_v3_key,
                wx_pay_notify_url=http_settings.wx_pay_notify_url,
                wx_pay_platform_serial_no=http_settings.wx_pay_platform_serial_no,
                wx_pay_platform_public_key_path=http_settings.wx_pay_platform_public_key_path,
                ai_api_url="https://example.invalid/v1/chat/completions",
                ai_api_key="fixture-key",
                ai_model="fixture-model",
            )
            server.settings = keyed
            server.database.set_config("ai.enabled", True, True)
            with patch("backend.analysis_ai._http_post", side_effect=fixture_http_post):
                status, generated = request(
                    base, "/api/analysis-reports/generate", method="POST", token=token,
                    data={"chart_key": chart_key, "chart": valid_chart()},
                )
            assert status == 200
            assert generated["item"]["source"] == "ai"
            assert generated["item"]["paid"] is True
            for key in SECTION_KEYS:
                assert DISCLAIMER in str(generated["item"]["sections"][key])
            assert report_count(server.database) == 1
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("analysis report and AI fixture checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
