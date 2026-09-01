from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
PID_FILE = LOG_DIR / "backend.pid"
BACKUP_DIR = ROOT / "backups"
TEST_LOG = LOG_DIR / "test-suite.log"
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def start(host: str, port: int) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    current = read_pid()
    if current and is_running(current):
        print(f"后端已运行，PID={current}，地址=http://{host}:{port}")
        return 0
    log_path = LOG_DIR / "backend-process.log"
    log = log_path.open("a", encoding="utf-8")
    command = [sys.executable, "-m", "backend.app", "--host", host, "--port", str(port)]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=creationflags)
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"后端已启动，PID={process.pid}，地址=http://{host}:{port}")
    return 0


def stop() -> int:
    pid = read_pid()
    if not pid:
        print("后端未发现 PID 文件")
        return 0
    if is_running(pid):
        os.kill(pid, signal.SIGTERM)
        print(f"已发送停止信号，PID={pid}")
    PID_FILE.unlink(missing_ok=True)
    return 0


def health(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as response:
        print(response.read().decode("utf-8"))
    return 0


def backup(db_path: Path) -> int:
    if not db_path.is_file():
        raise FileNotFoundError(f"数据库不存在：{db_path}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    shutil.copy2(db_path, target)
    print(f"备份完成：{target}")
    return 0


def restore(db_path: Path, source: Path) -> int:
    if not source.is_file():
        raise FileNotFoundError(f"备份文件不存在：{source}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.is_file():
        backup(db_path)
    shutil.copy2(source, db_path)
    print(f"恢复完成：{source} -> {db_path}")
    return 0


def restart(host: str, port: int) -> int:
    stop()
    return start(host, port)


def test_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("bazi-ziwei-tests")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(TEST_LOG, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def run_checks() -> int:
    logger = test_logger()
    checks = ("test_backend.py", "test_backend_api.py", "test_payment.py", "test_deploy_config.py")
    for check in checks:
        logger.info("开始 %s", check)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / check)], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if result.stdout:
            print(result.stdout, end="")
            logger.info("%s stdout\n%s", check, result.stdout.rstrip())
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
            logger.error("%s stderr\n%s", check, result.stderr.rstrip())
        if result.returncode:
            logger.error("失败 %s exit=%s", check, result.returncode)
            return result.returncode
        logger.info("通过 %s", check)
    print(f"全部后端检查通过；日志：{TEST_LOG}")
    return 0


def clean_generated() -> int:
    root = ROOT.resolve()
    removed = 0
    for path in sorted(ROOT.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.name not in CACHE_DIR_NAMES and path.suffix not in {".pyc", ".pyo"}:
            continue
        resolved = path.resolve()
        if root not in resolved.parents:
            raise RuntimeError(f"拒绝清理项目目录外路径：{resolved}")
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        removed += 1
    pid = read_pid()
    if PID_FILE.exists() and (not pid or not is_running(pid)):
        PID_FILE.unlink()
        removed += 1
    print(f"已清理 {removed} 项缓存、字节码或失效 PID 文件")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="八字紫微后端运行管理")
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--host", default="127.0.0.1")
    start_parser.add_argument("--port", type=int, default=8787)
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("test")
    sub.add_parser("clean")
    health_parser = sub.add_parser("health")
    health_parser.add_argument("--url", default="http://127.0.0.1:8787/health")
    backup_parser = sub.add_parser("backup")
    backup_parser.add_argument("--db", type=Path, default=ROOT / "data" / "app.sqlite3")
    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("source", type=Path)
    restore_parser.add_argument("--db", type=Path, default=ROOT / "data" / "app.sqlite3")
    restart_parser = sub.add_parser("restart")
    restart_parser.add_argument("--host", default="127.0.0.1")
    restart_parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if args.command == "start":
        return start(args.host, args.port)
    if args.command == "stop":
        return stop()
    if args.command == "status":
        pid = read_pid()
        print(f"running pid={pid}" if pid and is_running(pid) else "stopped")
        return 0
    if args.command == "test":
        return run_checks()
    if args.command == "clean":
        return clean_generated()
    if args.command == "health":
        return health(args.url)
    if args.command == "backup":
        return backup(args.db)
    if args.command == "restore":
        return restore(args.db, args.source)
    return restart(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
