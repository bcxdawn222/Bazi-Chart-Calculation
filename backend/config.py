from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: Path
    log_path: Path
    wx_app_id: str
    wx_app_secret: str
    session_secret: str
    admin_token: str
    allowed_origins: tuple[str, ...]
    wx_pay_mch_id: str = ""
    wx_pay_serial_no: str = ""
    wx_pay_private_key_path: Path = Path("")
    wx_pay_api_v3_key: str = ""
    wx_pay_notify_url: str = ""
    wx_pay_platform_serial_no: str = ""
    wx_pay_platform_public_key_path: Path = Path("")
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = ROOT / "data"
        log_dir = ROOT / "logs"
        return cls(
            host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
            port=int(os.environ.get("BACKEND_PORT", "8787")),
            db_path=Path(os.environ.get("APP_DB_PATH", str(data_dir / "app.sqlite3"))),
            log_path=Path(os.environ.get("BACKEND_LOG_PATH", str(log_dir / "backend.log"))),
            wx_app_id=os.environ.get("WX_APP_ID", ""),
            wx_app_secret=os.environ.get("WX_APP_SECRET", ""),
            session_secret=os.environ.get("SESSION_SECRET", ""),
            admin_token=os.environ.get("ADMIN_TOKEN", ""),
            allowed_origins=tuple(
                item.strip() for item in os.environ.get("ALLOWED_ORIGINS", "").split(",") if item.strip()
            ),
            wx_pay_mch_id=os.environ.get("WX_PAY_MCH_ID", ""),
            wx_pay_serial_no=os.environ.get("WX_PAY_SERIAL_NO", ""),
            wx_pay_private_key_path=Path(os.environ.get("WX_PAY_PRIVATE_KEY_PATH", "")),
            wx_pay_api_v3_key=os.environ.get("WX_PAY_API_V3_KEY", ""),
            wx_pay_notify_url=os.environ.get("WX_PAY_NOTIFY_URL", ""),
            wx_pay_platform_serial_no=os.environ.get("WX_PAY_PLATFORM_SERIAL_NO", ""),
            wx_pay_platform_public_key_path=Path(os.environ.get("WX_PAY_PLATFORM_PUBLIC_KEY_PATH", "")),
            ai_api_url=os.environ.get("AI_API_URL", ""),
            ai_api_key=os.environ.get("AI_API_KEY", ""),
            ai_model=os.environ.get("AI_MODEL", ""),
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
