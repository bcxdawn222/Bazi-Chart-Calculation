from __future__ import annotations

import argparse
import getpass
import logging
import os
import posixpath
import shlex
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

import paramiko

from support.ssh_hosts import create_ssh_client, persist_host_keys


HOST = "124.223.182.85"
USER = "ubuntu"
REMOTE_ROOT = "/home/ubuntu/bazi-ziwei"
DB_PATH = f"{REMOTE_ROOT}/data/app.sqlite3"
BACKUP_DIR = f"{REMOTE_ROOT}/backups"
SERVICE = "bazi-ziwei.service"


@dataclass(frozen=True)
class ServerOptions:
    host: str
    user: str
    password: str
    trust_new_host_key: bool


def configure_logging() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "server-manage.log"), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def connect(options: ServerOptions) -> paramiko.SSHClient:
    client = create_ssh_client(options.trust_new_host_key)
    client.connect(
        options.host,
        username=options.user,
        password=options.password,
        timeout=10,
        auth_timeout=10,
        banner_timeout=10,
    )
    persist_host_keys(client, options.trust_new_host_key)
    return client


def run(client: paramiko.SSHClient, command: str, *, label: str, log_output: bool = True) -> str:
    _, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode("utf-8", "replace").strip()
    error = stderr.read().decode("utf-8", "replace").strip()
    status = stdout.channel.recv_exit_status()
    suffix = f"\n{output}" if output and log_output else ""
    logging.info("%s status=%s%s", label, status, suffix)
    if status != 0:
        if error:
            logging.error("%s", error)
        raise RuntimeError(f"服务器操作失败：{label}")
    return output


def status(client: paramiko.SSHClient) -> None:
    commands = (
        ("后端状态", f"systemctl is-active {SERVICE}"),
        ("Caddy 状态", "systemctl is-active caddy"),
        ("系统信息", "uname -m && . /etc/os-release && echo \"$PRETTY_NAME\""),
        ("磁盘空间", f"df -h {shlex.quote(REMOTE_ROOT)}"),
    )
    for label, command in commands:
        run(client, command, label=label)


def health(client: paramiko.SSHClient) -> None:
    run(client, "curl -fsS http://127.0.0.1:8787/health", label="后端健康检查")
    run(client, "curl -fsS http://127.0.0.1/health", label="Caddy 健康检查")
    run(client, "curl -fsS http://127.0.0.1/api/config", label="配置接口检查")
    run(client, "curl -fsS http://127.0.0.1/admin/ops-config.html | grep -q '运营配置'", label="运营配置页检查")


def service_action(client: paramiko.SSHClient, action: str) -> None:
    run(client, f"sudo -n systemctl {action} {SERVICE}", label=f"服务 {action}")
    if action in {"start", "restart"}:
        time.sleep(1)
        health(client)


def backup(client: paramiko.SSHClient, suffix: str = "") -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"app-{timestamp}{suffix}.sqlite3"
    target = posixpath.join(BACKUP_DIR, name)
    script = (
        "import sqlite3; "
        f"src=sqlite3.connect({DB_PATH!r}); "
        f"dst=sqlite3.connect({target!r}); "
        "src.backup(dst); dst.close(); src.close()"
    )
    run(client, f"mkdir -p {shlex.quote(BACKUP_DIR)}", label="创建备份目录")
    run(client, f"python3 -c {shlex.quote(script)}", label="SQLite 在线备份")
    run(client, f"test -s {shlex.quote(target)} && ls -lh {shlex.quote(target)}", label="校验备份")
    return target


def validate_backup_path(source: str) -> str:
    normalized = posixpath.normpath(source)
    candidate = PurePosixPath(normalized)
    if candidate.parent != PurePosixPath(BACKUP_DIR) or candidate.suffix != ".sqlite3":
        raise ValueError(f"恢复文件必须位于 {BACKUP_DIR} 且后缀为 .sqlite3")
    return normalized


def restore(client: paramiko.SSHClient, source: str) -> None:
    source = validate_backup_path(source)
    run(client, f"test -s {shlex.quote(source)}", label="检查恢复源")
    backup(client, "-before-restore")
    run(client, f"sudo -n systemctl stop {SERVICE}", label="停止后端")
    try:
        run(client, f"cp {shlex.quote(source)} {shlex.quote(DB_PATH)}", label="恢复数据库")
    finally:
        run(client, f"sudo -n systemctl start {SERVICE}", label="启动后端")
    time.sleep(1)
    health(client)


def verify_restore(client: paramiko.SSHClient) -> None:
    source = backup(client, "-restore-check")
    marker = f"ops-{datetime.now():%Y%m%d%H%M%S}"
    token_command = (
        "cd /home/ubuntu/bazi-ziwei; "
        "set -a; . /home/ubuntu/bazi-ziwei/.env; set +a; "
        "python3 -c "
        "\"from backend.db import Database; from pathlib import Path; import os; "
        "db=Database(Path('/home/ubuntu/bazi-ziwei/data/app.sqlite3')); "
        "u=db.upsert_user('ops-check'); "
        "print(db.create_session(str(u['id']), os.environ['SESSION_SECRET'])[0])\""
    )
    token = run(client, token_command, label="创建恢复测试会话", log_output=False)
    payload = '{"user_id":"ops-check","payload":{"marker":"' + marker + '"}}'
    post = (
        "curl -fsS -X POST -H 'Content-Type: application/json' "
        f"-H 'Authorization: Bearer {shlex.quote(token)}' "
        f"--data {shlex.quote(payload)} http://127.0.0.1:8787/api/charts"
    )
    run(client, post, label="写入恢复测试记录")
    restore(client, source)
    restored = run(
        client,
        "python3 -c "
        "\"import sqlite3; "
        f"db=sqlite3.connect('{DB_PATH}'); "
        "rows=db.execute('SELECT payload FROM charts WHERE user_id = ?', ('ops-check',)).fetchall(); "
        "print('\\n'.join(row[0] for row in rows))\"",
        label="恢复后检查测试记录",
    )
    if marker in restored:
        raise RuntimeError("数据库恢复后测试记录仍存在")
    cleanup = (
        "python3 -c "
        "\"import sqlite3; "
        f"db=sqlite3.connect('{DB_PATH}'); "
        "db.execute(\\\"DELETE FROM charts WHERE user_id IN "
        "(SELECT id FROM users WHERE openid = 'ops-check')\\\"); "
        "db.execute(\\\"DELETE FROM sessions WHERE user_id IN "
        "(SELECT id FROM users WHERE openid = 'ops-check')\\\"); "
        "db.execute(\\\"DELETE FROM users WHERE openid = 'ops-check'\\\"); "
        "db.commit()\""
    )
    run(client, cleanup, label="清理恢复测试数据")
    logging.info("数据库写入、备份和恢复验证通过")


def show_logs(client: paramiko.SSHClient, lines: int) -> None:
    run(
        client,
        f"journalctl -u {SERVICE} -n {lines} --no-pager",
        label="后端服务日志",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ubuntu 后端服务器运维")
    parser.add_argument("command", choices=(
        "status", "health", "start", "stop", "restart", "backup", "restore", "verify-restore", "logs"
    ))
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--user", default=USER)
    parser.add_argument("--file", help="restore 使用的远端 SQLite 备份路径")
    parser.add_argument("--lines", type=int, default=80)
    parser.add_argument("--trust-new-host-key", action="store_true", help="首次连接时信任并保存服务器主机密钥")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = os.environ.get("REMOTE_PASSWORD") or getpass.getpass("SSH password: ")
    options = ServerOptions(args.host, args.user, password, args.trust_new_host_key)
    configure_logging()
    client = connect(options)
    try:
        if args.command == "status":
            status(client)
        elif args.command == "health":
            health(client)
        elif args.command in {"start", "stop", "restart"}:
            service_action(client, args.command)
        elif args.command == "backup":
            logging.info("备份文件：%s", backup(client))
        elif args.command == "restore":
            if not args.file:
                raise ValueError("restore 需要 --file 指定远端备份路径")
            restore(client, args.file)
        elif args.command == "verify-restore":
            verify_restore(client)
        else:
            show_logs(client, max(1, min(args.lines, 500)))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
