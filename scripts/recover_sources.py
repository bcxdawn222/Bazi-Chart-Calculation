from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ToolRun:
    name: str
    command: List[str]
    returncode: int
    log_path: str


@dataclass
class RecoveryManifest:
    input_path: str
    input_sha256: str
    output_path: str
    status: str = "running"
    source_inputs: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    runs: List[ToolRun] = field(default_factory=list)
    native_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: List[str], log_path: Path, timeout: int = 600, java17: bool = False) -> ToolRun:
    logging.info("执行: %s", " ".join(command))
    environment = os.environ.copy()
    if java17:
        java_home = Path("C:/Program Files/Java/jdk-17")
        if not (java_home / "bin/java.exe").exists():
            raise FileNotFoundError(f"Java 17 is required for JADX: {java_home}")
        environment["JAVA_HOME"] = str(java_home)
        environment["PATH"] = str(java_home / "bin") + os.pathsep + environment.get("PATH", "")
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False, env=environment)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return ToolRun(command[0], command, completed.returncode, str(log_path.resolve()))


def find_jadx(root: Path, explicit: Optional[Path]) -> Path:
    candidates = [explicit] if explicit else []
    candidates.extend([root / "jadx-1.5.1" / "bin" / "jadx.bat", root / "jadx-1.5.1" / "bin" / "jadx"])
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    path = shutil.which("jadx") or shutil.which("jadx.bat")
    if path:
        return Path(path)
    raise FileNotFoundError("JADX executable was not found; run scripts\\bootstrap_reverse_tools.py first")


def find_apktool(root: Path, explicit: Optional[Path]) -> Path:
    candidates = [explicit] if explicit else []
    candidates.append(root / "apktool-2.10.0.jar")
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("apktool jar was not found; run scripts\\bootstrap_reverse_tools.py first")


def locate_apk(input_path: Path) -> Path:
    if input_path.is_file() and input_path.suffix.lower() == ".apk":
        return input_path
    manifest = input_path / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"runtime manifest missing: {manifest}")
    sample_path = Path(json.loads(manifest.read_text(encoding="utf-8"))["sample_path"])
    if not sample_path.is_file():
        raise FileNotFoundError(f"original APK missing: {sample_path}")
    return sample_path


def collect_dex(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".apk":
        return [input_path]
    dex = sorted(input_path.rglob("*.dex"))
    if not dex:
        raise FileNotFoundError(f"no DEX files in artifact directory: {input_path}")
    return dex


def extract_native(apk: Path, output: Path, manifest: RecoveryManifest) -> None:
    native_dir = output / "native"
    with zipfile.ZipFile(apk) as archive:
        names = [name for name in archive.namelist() if name.startswith("lib/") and name.endswith(".so")]
        for name in names:
            target = native_dir / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            manifest.native_files.append(str(target.resolve()))
    if not names:
        logging.info("APK 中没有 native 库")


def native_evidence(files: List[str], output: Path) -> None:
    pattern = re.compile(rb"[ -~]{4,}")
    lines: List[str] = []
    for name in files:
        data = Path(name).read_bytes()
        lines.append(f"=== {name} ===")
        for match in pattern.finditer(data):
            value = match.group().decode("ascii", errors="ignore")
            if "JNI_OnLoad" in value or "Java_" in value or re.search(r"(?i)dex|loadlibrary|decrypt|password|master|rsa|url|http", value):
                lines.append(value)
    (output / "native-evidence.txt").write_text("\n".join(lines), encoding="utf-8")


def generated_java_count(destination: Path) -> int:
    return len(list(destination.rglob("*.java"))) if destination.exists() else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="从 APK 或运行时 artifact 恢复可反编译源码")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/recovered"))
    parser.add_argument("--tools", type=Path, default=Path(".tools/reverse"))
    parser.add_argument("--jadx", type=Path)
    parser.add_argument("--apktool", type=Path)
    args = parser.parse_args()
    if not args.input.exists():
        logging.error("输入不存在: %s", args.input)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    log_path = args.output / "source-recovery.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()])
    source_hash = sha256_file(args.input) if args.input.is_file() else sha256_file(locate_apk(args.input))
    manifest = RecoveryManifest(str(args.input.resolve()), source_hash, str(args.output.resolve()))
    try:
        apk = locate_apk(args.input)
        dex_inputs = collect_dex(args.input)
        jadx = find_jadx(args.tools, args.jadx)
        apktool = find_apktool(args.tools, args.apktool)
        manifest.tools.extend([str(jadx.resolve()), str(apktool.resolve())])
        manifest.source_inputs = [str(path.resolve()) for path in dex_inputs]
        source_dir = args.output / "java"
        partial_jadx = False
        for index, dex in enumerate(dex_inputs):
            destination = source_dir / f"dex-{index:02d}"
            if dex.suffix.lower() == ".apk":
                command = [str(jadx), "-d", str(destination), str(dex)]
            else:
                command = [str(jadx), "-d", str(destination), str(dex)]
            result = run(command, args.output / "logs" / f"jadx-{index:02d}.log", java17=True)
            manifest.runs.append(result)
            if result.returncode != 0:
                java_count = generated_java_count(destination / "sources")
                if java_count == 0:
                    raise RuntimeError(f"JADX failed for {dex} with exit code {result.returncode} and produced no Java source")
                partial_jadx = True
                manifest.errors.append(f"JADX returned {result.returncode} for {dex}; preserved {java_count} generated Java files and continued")
        resource_result = run(["java", "-jar", str(apktool), "d", "-f", "-o", str(args.output / "resources"), str(apk)], args.output / "logs" / "apktool.log")
        manifest.runs.append(resource_result)
        if resource_result.returncode != 0:
            raise RuntimeError(f"apktool failed with exit code {resource_result.returncode}")
        extract_native(apk, args.output, manifest)
        native_evidence(manifest.native_files, args.output)
        manifest.status = "recovered_partial" if partial_jadx else "recovered"
        return 0
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        manifest.status = "failed"
        manifest.errors.append(str(error))
        logging.exception("源码恢复失败")
        return 6
    finally:
        (args.output / "source-recovery.json").write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
