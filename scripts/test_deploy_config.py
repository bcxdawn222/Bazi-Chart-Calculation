from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.deploy_server import (
    ADMIN_FILES,
    FILES,
    dependency_install_command,
    render_caddy_config,
    system_dependency_command,
)
from scripts.preview_miniprogram import JPEG_SIGNATURE, artifacts_are_valid, output_has_error
from scripts.server_manage import BACKUP_DIR, validate_backup_path


def main() -> int:
    internal = render_caddy_config("")
    assert internal.startswith(":80")
    assert "reverse_proxy 127.0.0.1:8787" in internal

    production = render_caddy_config("api.example.com")
    assert production.startswith("api.example.com")
    assert ":80" not in production.splitlines()[0]
    assert "reverse_proxy 127.0.0.1:8787" in production

    command = dependency_install_command()
    assert "python3 -m venv" in command
    assert ".venv/bin/python -m pip install" in command
    assert "requirements.txt" in command
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "paramiko" in requirements
    assert "python-docx" in requirements
    system_command = system_dependency_command()
    assert "dpkg -s python3-venv" in system_command
    assert "apt-get install -y python3-venv" in system_command
    assert "backend/commerce_store.py" in FILES
    assert "backend/order_store.py" in FILES
    assert "backend/ops_api.py" in FILES
    assert set(ADMIN_FILES) == {"ops-config.html", "ops-config.css", "ops-config.js"}
    valid_backup = f"{BACKUP_DIR}/app-20260901.sqlite3"
    assert validate_backup_path(valid_backup) == valid_backup
    try:
        validate_backup_path(f"{BACKUP_DIR}/../data/app.sqlite3")
    except ValueError:
        pass
    else:
        raise AssertionError("恢复路径不能越过备份目录")

    assert output_has_error(b"[error] preview failed")
    assert output_has_error(b"#initialize-error")
    assert not output_has_error("× IDE may already started".encode("utf-8"))
    assert not output_has_error(b"preview success")
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        qr_file = temporary_root / "preview.jpg"
        info_file = temporary_root / "preview.json"
        assert not artifacts_are_valid(qr_file, info_file)
        qr_file.write_bytes(JPEG_SIGNATURE + b"preview")
        info_file.write_text("{}", encoding="utf-8")
        assert artifacts_are_valid(qr_file, info_file)
    print("deployment configuration checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
