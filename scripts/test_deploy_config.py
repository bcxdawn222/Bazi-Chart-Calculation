from __future__ import annotations

import sys
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
    system_command = system_dependency_command()
    assert "dpkg -s python3-venv" in system_command
    assert "apt-get install -y python3-venv" in system_command
    assert "backend/commerce_store.py" in FILES
    assert "backend/order_store.py" in FILES
    assert "backend/ops_api.py" in FILES
    assert set(ADMIN_FILES) == {"ops-config.html", "ops-config.css", "ops-config.js"}
    print("deployment configuration checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
