"""只部署运营后台静态文件到 Caddy 站点目录，不改动后端服务。密码从 REMOTE_PASSWORD 读取。"""
from __future__ import annotations

import argparse
import getpass
import os
import posixpath
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support.ssh_hosts import create_ssh_client, persist_host_keys  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin"
STAGING = "/home/ubuntu/bazi-ziwei/admin-console-staging"
TARGET = "/usr/share/caddy/admin"


def files() -> list[str]:
    items = ["index.html"]
    items += sorted(f"console/{p.name}" for p in (ADMIN / "console").iterdir() if p.suffix in {".js", ".css"})
    return items


def run(client, command: str) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=30)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    if stdout.channel.recv_exit_status() != 0:
        raise RuntimeError(f"远端命令失败：{command}\n{out}{err}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="部署运营后台静态页")
    parser.add_argument("--host", default="124.223.182.85")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--trust-new-host-key", action="store_true")
    args = parser.parse_args()
    password = os.environ.get("REMOTE_PASSWORD") or getpass.getpass("SSH password: ")
    client = create_ssh_client(args.trust_new_host_key)
    client.connect(args.host, username=args.user, password=password, timeout=15, auth_timeout=15, banner_timeout=15)
    try:
        persist_host_keys(client, args.trust_new_host_key)
        run(client, f"rm -rf {STAGING} && mkdir -p {STAGING}/console")
        with client.open_sftp() as sftp:
            for relative in files():
                sftp.put(str(ADMIN / relative), posixpath.join(STAGING, relative))
                print(f"上传 {relative}")
        run(client, f"sudo -n install -d -m 0755 {TARGET} {TARGET}/console")
        for relative in files():
            run(client, f"sudo -n install -m 0644 {STAGING}/{relative} {TARGET}/{relative}")
        run(client, f"rm -rf {STAGING}")
        print(run(client, f"ls -la {TARGET} {TARGET}/console"))
        print(run(client, "curl -s -o /dev/null -w 'index %{http_code}\\n' http://127.0.0.1/admin/; "
                          "curl -s -o /dev/null -w 'main.js %{http_code} %{content_type}\\n' http://127.0.0.1/admin/console/main.js; "
                          "curl -s -o /dev/null -w 'ops-config %{http_code}\\n' http://127.0.0.1/admin/ops-config.html; "
                          "curl -s http://127.0.0.1/health"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
