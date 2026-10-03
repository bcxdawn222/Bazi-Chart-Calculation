from __future__ import annotations

import argparse
import getpass
import logging
import os
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

import paramiko

from support.ssh_hosts import create_ssh_client, persist_host_keys


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / "logs" / "deploy-server.log"
REMOTE_ROOT = "/home/ubuntu/bazi-ziwei"
BACKUP_CADDY = "/etc/caddy/Caddyfile.bazi-backup"


@dataclass(frozen=True)
class RemoteCommand:
    name: str
    command: str


FILES = (
    "backend/__init__.py",
    "backend/config.py",
    "backend/schema.sql",
    "backend/db.py",
    "backend/record_store.py",
    "backend/record_api.py",
    "backend/commerce_store.py",
    "backend/order_store.py",
    "backend/analysis_store.py",
    "backend/analysis_ai.py",
    "backend/ops_api.py",
    "backend/http_base.py",
    "backend/security.py",
    "backend/wechat.py",
    "backend/wechat_payments.py",
    "backend/payment_api.py",
    "backend/app.py",
    "requirements.txt",
)
ADMIN_FILES = ("ops-config.html", "ops-config.css", "ops-config.js")


SERVICE_TEXT = """[Unit]
Description=Bazi Ziwei API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/bazi-ziwei
ExecStart=/home/ubuntu/bazi-ziwei/.venv/bin/python -m backend.app --host 127.0.0.1 --port 8787
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/home/ubuntu/bazi-ziwei/.env
Environment=APP_DB_PATH=/home/ubuntu/bazi-ziwei/data/app.sqlite3
Environment=BACKEND_LOG_PATH=/home/ubuntu/bazi-ziwei/logs/backend.log

[Install]
WantedBy=multi-user.target
"""


def render_caddy_config(domain: str) -> str:
    host = domain.strip().lower()
    if host and not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host):
        raise ValueError("域名格式无效，请只填写主机名")
    site = host or ":80"
    return f"""{site} {{
\thandle /api/* {{
\t\treverse_proxy 127.0.0.1:8787
\t}}
\thandle /health {{
\t\treverse_proxy 127.0.0.1:8787
\t}}
\thandle {{
\t\troot * /usr/share/caddy
\t\tfile_server
\t}}
}}
"""


def dependency_install_command() -> str:
    return (
        f"cd {REMOTE_ROOT} && python3 -m venv .venv && "
        ".venv/bin/python -m pip install -r requirements.txt"
    )


def system_dependency_command() -> str:
    return (
        "dpkg -s python3-venv >/dev/null 2>&1 || "
        "(sudo -n apt-get update && "
        "sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv)"
    )


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)


def run(client: paramiko.SSHClient, item: RemoteCommand) -> str:
    _, stdout, stderr = client.exec_command(item.command)
    output = stdout.read().decode("utf-8", "replace")
    error = stderr.read().decode("utf-8", "replace")
    status = stdout.channel.recv_exit_status()
    logging.info("远端步骤 [%s] status=%s\n%s%s", item.name, status, output, error)
    if status != 0:
        raise RuntimeError(f"远端步骤失败：{item.name}")
    return output


def ensure_dirs(client: paramiko.SSHClient) -> None:
    run(client, RemoteCommand(
        "创建目录", f"mkdir -p {REMOTE_ROOT}/backend {REMOTE_ROOT}/data {REMOTE_ROOT}/logs {REMOTE_ROOT}/admin",
    ))


def upload_files(client: paramiko.SSHClient, caddy_text: str) -> None:
    with client.open_sftp() as sftp:
        for relative in FILES:
            local = ROOT / relative
            remote = posixpath.join(REMOTE_ROOT, relative.replace("\\", "/"))
            sftp.put(str(local), remote)
            logging.info("上传 %s -> %s", local, remote)
        for name in ADMIN_FILES:
            local = ROOT / "admin" / name
            sftp.put(str(local), f"{REMOTE_ROOT}/admin/{name}")
            logging.info("上传 %s -> %s", local, f"{REMOTE_ROOT}/admin/{name}")
        with sftp.file(f"{REMOTE_ROOT}/bazi-ziwei.service.tmp", "w") as stream:
            stream.write(SERVICE_TEXT)
        with sftp.file(f"{REMOTE_ROOT}/Caddyfile.tmp", "w") as stream:
            stream.write(caddy_text)


def install_configs(client: paramiko.SSHClient) -> None:
    run(client, RemoteCommand(
        "生成服务器密钥",
        "if [ ! -s /home/ubuntu/bazi-ziwei/.env ]; then "
        "umask 077; "
        "printf 'SESSION_SECRET=%s\\nADMIN_TOKEN=%s\\n' "
        "\"$(openssl rand -hex 32)\" \"$(openssl rand -hex 32)\" "
        "> /home/ubuntu/bazi-ziwei/.env; "
        "fi; chmod 600 /home/ubuntu/bazi-ziwei/.env",
    ))
    run(client, RemoteCommand("检查 Python venv", system_dependency_command()))
    run(client, RemoteCommand("安装 Python 依赖", dependency_install_command()))
    run(client, RemoteCommand(
        "安装 systemd 配置",
        f"sudo -n install -m 0644 {REMOTE_ROOT}/bazi-ziwei.service.tmp /etc/systemd/system/bazi-ziwei.service",
    ))
    run(client, RemoteCommand(
        "备份 Caddy 配置",
        f"sudo -n cp /etc/caddy/Caddyfile {BACKUP_CADDY}",
    ))
    run(client, RemoteCommand(
        "安装 Caddy 配置",
        f"sudo -n install -m 0644 {REMOTE_ROOT}/Caddyfile.tmp /etc/caddy/Caddyfile",
    ))
    run(client, RemoteCommand(
        "安装运营配置页",
        f"sudo -n install -d -m 0755 /usr/share/caddy/admin && "
        f"sudo -n install -m 0644 {REMOTE_ROOT}/admin/ops-config.html /usr/share/caddy/admin/ops-config.html && "
        f"sudo -n install -m 0644 {REMOTE_ROOT}/admin/ops-config.css /usr/share/caddy/admin/ops-config.css && "
        f"sudo -n install -m 0644 {REMOTE_ROOT}/admin/ops-config.js /usr/share/caddy/admin/ops-config.js",
    ))
    try:
        run(client, RemoteCommand("验证 Caddy", "sudo -n caddy validate --config /etc/caddy/Caddyfile"))
    except RuntimeError:
        run(client, RemoteCommand("恢复 Caddy", f"sudo -n cp {BACKUP_CADDY} /etc/caddy/Caddyfile"))
        raise


def activate(client: paramiko.SSHClient, domain: str) -> None:
    commands = [
        RemoteCommand("刷新 systemd", "sudo -n systemctl daemon-reload"),
        RemoteCommand("启动后端", "sudo -n systemctl enable --now bazi-ziwei.service"),
        RemoteCommand("重载 Caddy", "sudo -n systemctl reload caddy"),
        RemoteCommand("后端状态", "systemctl is-active bazi-ziwei.service"),
        RemoteCommand("本机健康检查", "curl -fsS http://127.0.0.1:8787/health"),
    ]
    if domain:
        commands.append(RemoteCommand(
            "HTTPS 健康检查", f"curl -fsS --resolve {domain}:443:127.0.0.1 https://{domain}/health",
        ))
    else:
        commands.append(RemoteCommand("Caddy 健康检查", "curl -fsS http://127.0.0.1/health"))
    for item in commands:
        run(client, item)


def main() -> int:
    parser = argparse.ArgumentParser(description="部署八字紫微后端到 Ubuntu")
    parser.add_argument("--host", default="124.223.182.85")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--domain", default="", help="备案并解析到服务器的 HTTPS 域名；留空时为内部 HTTP 验收模式")
    parser.add_argument("--trust-new-host-key", action="store_true", help="首次连接时信任并保存服务器主机密钥")
    args = parser.parse_args()
    password = os.environ.get("REMOTE_PASSWORD") or getpass.getpass("SSH password: ")
    configure_logging()
    client = create_ssh_client(args.trust_new_host_key)
    try:
        client.connect(
            args.host, username=args.user, password=password,
            timeout=10, auth_timeout=10, banner_timeout=10,
        )
        persist_host_keys(client, args.trust_new_host_key)
        ensure_dirs(client)
        upload_files(client, render_caddy_config(args.domain))
        install_configs(client)
        activate(client, args.domain)
    finally:
        client.close()
    logging.info("部署完成；日志：%s", LOG_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
