from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "miniprogram"
LOG_FILE = ROOT / "logs" / "wechat-preview.log"
QR_FILE = ROOT / "logs" / "wechat-preview-qr.jpg"
INFO_FILE = ROOT / "logs" / "wechat-preview-info.json"
ERROR_MARKERS = (b"[error]", b"#initialize-error")
JPEG_SIGNATURE = b"\xff\xd8\xff"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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


def clear_previous_artifacts() -> None:
    QR_FILE.unlink(missing_ok=True)
    QR_FILE.with_suffix(".png").unlink(missing_ok=True)
    INFO_FILE.unlink(missing_ok=True)


def output_has_error(output: bytes) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in ERROR_MARKERS)


def artifacts_are_valid(qr_file: Path = QR_FILE, info_file: Path = INFO_FILE) -> bool:
    if not qr_file.is_file() or not info_file.is_file():
        return False
    if qr_file.stat().st_size <= len(JPEG_SIGNATURE) or info_file.stat().st_size == 0:
        return False
    with qr_file.open("rb") as qr_stream:
        return qr_stream.read(len(JPEG_SIGNATURE)) == JPEG_SIGNATURE


def publish_artifacts(source_qr: Path, source_info: Path) -> bool:
    if not artifacts_are_valid(source_qr, source_info):
        return False
    shutil.copy2(source_qr, QR_FILE)
    shutil.copy2(source_info, INFO_FILE)
    return True


def preview_succeeded(returncode: int, output: bytes) -> bool:
    return returncode == 0 and not output_has_error(output) and artifacts_are_valid()


def main() -> int:
    parser = argparse.ArgumentParser(description="生成微信小程序预览包")
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--timeout", type=int, default=120, help="等待微信 CLI 完成的秒数")
    args = parser.parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout 必须为正整数")
    cli = find_cli(args.cli)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    clear_previous_artifacts()
    with tempfile.TemporaryDirectory(prefix="bazi-preview-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        temporary_qr = temporary_root / "preview.jpg"
        temporary_info = temporary_root / "preview.json"
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
            "--qr-format",
            "image",
            "--qr-output",
            str(temporary_qr),
            "--info-output",
            str(temporary_info),
        ]
        try:
            completed = subprocess.run(
                command, cwd=ROOT, capture_output=True, check=False, timeout=args.timeout,
            )
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"") + (error.stderr or b"")
            LOG_FILE.write_bytes(output)
            clear_previous_artifacts()
            print(f"微信小程序预览超时，已等待 {args.timeout} 秒")
            print(f"日志：{LOG_FILE}")
            return 1
        artifacts_published = publish_artifacts(temporary_qr, temporary_info)
    output = completed.stdout + completed.stderr
    LOG_FILE.write_bytes(output)
    sizes = [int(value) for value in re.findall(rb"\b\d{6,9}\b", output)]
    succeeded = artifacts_published and preview_succeeded(completed.returncode, output)
    if not succeeded:
        clear_previous_artifacts()
    if succeeded:
        print("微信小程序预览成功")
    else:
        print(f"微信小程序预览失败，exit={completed.returncode}")
        if output_has_error(output):
            print("CLI 输出包含错误标记")
        if not artifacts_are_valid():
            print("未生成有效的二维码或预览信息文件")
    if sizes:
        print(f"包体大小：{max(sizes)} Byte")
    print(f"日志：{LOG_FILE}")
    return 0 if succeeded else completed.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
