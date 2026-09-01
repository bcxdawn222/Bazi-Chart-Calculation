from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = ROOT / "miniprogram"
LOG_FILE = ROOT / "logs" / "open-miniprogram.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用微信开发者工具打开当前小程序工程")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--cli", type=Path, help="微信开发者工具 cli.bat 的完整路径")
    parser.add_argument("--reopen", action="store_true", help="先关闭当前工程再重新打开")
    parser.add_argument("--restart-ide", action="store_true", help="完整退出开发者工具后重新打开工程")
    return parser.parse_args()


def find_cli(explicit: Path | None) -> Path:
    if explicit is not None:
        if explicit.is_file():
            return explicit.resolve()
        raise FileNotFoundError(f"指定的微信开发者工具 CLI 不存在：{explicit}")
    command = shutil.which("cli.bat")
    candidates = [
        Path(command) if command else None,
        Path("D:/微信web开发者工具/cli.bat"),
        Path("C:/Program Files/Tencent/微信开发者工具/cli.bat"),
        Path("C:/Program Files (x86)/Tencent/微信web开发者工具/cli.bat"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("未找到微信开发者工具 cli.bat，请通过 --cli 提供完整路径")


def build_command(cli: Path, action: str, project: Path) -> Sequence[str]:
    arguments = (action, "--lang", "zh")
    if action != "quit":
        arguments += ("--project", str(project))
    if os.name == "nt" and cli.suffix.lower() == ".bat":
        return (os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(cli), *arguments)
    return (str(cli), *arguments)


def run_cli(cli: Path, action: str, project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_command(cli, action, project),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    project = args.project.resolve()
    if not (project / "project.config.json").is_file():
        raise FileNotFoundError(f"小程序工程缺少 project.config.json：{project}")
    cli = find_cli(args.cli)
    outputs: list[str] = []
    if args.restart_ide:
        stopped = run_cli(cli, "quit", project)
        outputs.append("[quit]\n" + (stopped.stdout + stopped.stderr).strip())
        if stopped.returncode != 0:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG_FILE.write_text("\n".join(outputs) + "\n", encoding="utf-8")
            return stopped.returncode
        time.sleep(1.0)
    if args.reopen:
        closed = run_cli(cli, "close", project)
        outputs.append("[close]\n" + (closed.stdout + closed.stderr).strip())
        if closed.returncode != 0:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG_FILE.write_text("\n".join(outputs) + "\n", encoding="utf-8")
            return closed.returncode
    completed = run_cli(cli, "open", project)
    outputs.append("[open]\n" + (completed.stdout + completed.stderr).strip())
    output = "\n".join(outputs).strip()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(output + "\n", encoding="utf-8")
    if output:
        print(output)
    print(f"日志：{LOG_FILE}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
