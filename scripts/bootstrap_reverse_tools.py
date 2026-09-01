from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


JADX_VERSION = "1.5.1"
APKTOOL_VERSION = "2.10.0"
JADX_URL = f"https://github.com/skylot/jadx/releases/download/v{JADX_VERSION}/jadx-{JADX_VERSION}.zip"
APKTOOL_URL = f"https://github.com/iBotPeaches/Apktool/releases/download/v{APKTOOL_VERSION}/apktool_{APKTOOL_VERSION}.jar"


@dataclass
class ToolRecord:
    name: str
    version: str
    path: str
    sha256: str
    status: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    logging.info("下载 %s", url)
    with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as stream:
        shutil.copyfileobj(response, stream)


def install_jadx(root: Path) -> ToolRecord:
    archive = root / f"jadx-{JADX_VERSION}.zip"
    if not archive.exists():
        download(JADX_URL, archive)
    extract_root = root / f"jadx-{JADX_VERSION}"
    if not extract_root.exists():
        with zipfile.ZipFile(archive) as package:
            package.extractall(extract_root)
    executable = extract_root / "bin" / "jadx.bat"
    if not executable.exists():
        raise RuntimeError(f"JADX executable missing: {executable}")
    return ToolRecord("jadx", JADX_VERSION, str(executable.resolve()), sha256_file(archive), "ready")


def install_apktool(root: Path) -> ToolRecord:
    jar = root / f"apktool-{APKTOOL_VERSION}.jar"
    if not jar.exists():
        download(APKTOOL_URL, jar)
    if jar.stat().st_size < 100_000:
        raise RuntimeError(f"apktool jar is unexpectedly small: {jar}")
    return ToolRecord("apktool", APKTOOL_VERSION, str(jar.resolve()), sha256_file(jar), "ready")


def install_frida(target: Path) -> ToolRecord:
    interpreter = [sys.executable]
    if shutil.which("py"):
        probe = subprocess.run(["py", "-3.13", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, check=False)
        if probe.returncode == 0:
            interpreter = ["py", "-3.13"]
    command = interpreter + ["-m", "pip", "install", "--target", str(target), "frida-tools"]
    logging.info("执行: %s", " ".join(command))
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    (target / "frida-install.stdout.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"frida-tools install failed with exit code {completed.returncode}")
    verify = subprocess.run(interpreter + ["-c", f"import sys; sys.path.insert(0, r'{target.resolve()}'); import frida; print(frida.__version__)"], capture_output=True, text=True, check=False)
    if verify.returncode != 0:
        raise RuntimeError(f"frida import verification failed: {verify.stderr.strip()}")
    return ToolRecord("frida-tools", "pip-resolved", str(target.resolve()), sha256_file(target / "frida-install.stdout.log"), "ready")


def main() -> int:
    parser = argparse.ArgumentParser(description="准备隔离的 Android 逆向工具")
    parser.add_argument("--root", type=Path, default=Path(".tools/reverse"))
    parser.add_argument("--log", type=Path, default=Path("logs/bootstrap-reverse-tools.log"))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(args.log, encoding="utf-8"), logging.StreamHandler()])
    records: List[ToolRecord] = []
    try:
        records.append(install_jadx(args.root))
        records.append(install_apktool(args.root))
        frida_target = args.root / "python"
        frida_target.mkdir(exist_ok=True)
        records.append(install_frida(frida_target))
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        report = {"status": "failed", "error": str(error), "tools": [asdict(record) for record in records]}
        (args.root / "tool-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.exception("工具准备失败")
        return 6
    report = {"status": "ready", "tools": [asdict(record) for record in records]}
    (args.root / "tool-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("工具准备完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
