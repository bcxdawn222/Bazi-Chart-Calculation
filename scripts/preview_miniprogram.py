from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "miniprogram"
LOG_FILE = ROOT / "logs" / "wechat-preview.log"


def find_cli(explicit: Path | None) -> Path:
    if explicit:
        return explicit.resolve()
    candidates = (
        Path("D:/微信web开发者工具/cli.bat"),
        Path("C:/Program Files/Tencent/微信开发者工具/cli.bat"),
    )
    command = shutil.which("cli.bat")
    if command:
        candidates = (Path(command),) + candidates
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("未找到微信开发者工具 cli.bat")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成微信小程序预览包")
    parser.add_argument("--cli", type=Path)
    args = parser.parse_args()
    cli = find_cli(args.cli)
    command = [
        os.environ.get("COMSPEC", "cmd.exe"),
        "/d",
        "/c",
        str(cli),
        "preview",
        "--lang",
        "zh",
        "--project",
        str(PROJECT),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    output = completed.stdout + completed.stderr
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(output, encoding="utf-8")
    print(output)
    print(f"日志：{LOG_FILE}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
