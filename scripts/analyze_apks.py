from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import struct
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


PRINTABLE_RE = re.compile(rb"[ -~]{5,}")


@dataclass
class DexInfo:
    name: str
    size: int
    sha256: str
    version: str
    string_ids: int
    type_ids: int
    method_ids: int
    class_defs: int
    data_size: int
    data_off: int
    trailing_size: int
    trailing_magic: str
    trailing_entropy: float
    embedded_magics: List[str] = field(default_factory=list)
    class_descriptors: List[str] = field(default_factory=list)
    strings: List[str] = field(default_factory=list)


@dataclass
class NativeLibInfo:
    name: str
    size: int
    sha256: str
    abi: str


@dataclass
class ApkReport:
    path: str
    size: int
    sha256: str
    entries: int
    compression_ratio: float
    dex: List[DexInfo]
    native_libs: List[NativeLibInfo]
    notable_entries: List[str]
    strings: List[str]
    keyword_hits: List[str]
    network_strings: List[str]
    aapt_badging: Optional[str]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_strings(data: bytes, limit: int = 80) -> List[str]:
    values: List[str] = []
    for match in PRINTABLE_RE.finditer(data):
        value = match.group().decode("ascii", errors="ignore")
        if value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def dex_metrics(data: bytes) -> tuple[int, int, int, int]:
    if len(data) < 112 or not data.startswith(b"dex\n"):
        return (0, 0, 0, 0)
    return struct.unpack_from("<I", data, 56)[0], struct.unpack_from("<I", data, 64)[0], struct.unpack_from("<I", data, 88)[0], struct.unpack_from("<I", data, 96)[0]


def read_uleb128(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    return value, offset


def extract_dex_strings(data: bytes) -> List[str]:
    if len(data) < 112 or not data.startswith(b"dex\n"):
        return []
    string_count = struct.unpack_from("<I", data, 56)[0]
    string_offset = struct.unpack_from("<I", data, 60)[0]
    values: List[str] = []
    for index in range(string_count):
        entry = string_offset + index * 4
        if entry + 4 > len(data):
            break
        item_offset = struct.unpack_from("<I", data, entry)[0]
        _, text_offset = read_uleb128(data, item_offset)
        end = data.find(b"\x00", text_offset)
        if end < 0:
            end = len(data)
        values.append(data[text_offset:end].decode("utf-8", errors="replace"))
    return values


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    length = len(data)
    return round(-sum((count / length) * math.log2(count / length) for count in counts if count), 3)


def find_magics(data: bytes) -> List[str]:
    known = {b"PK\x03\x04": "zip", b"dex\n": "dex", b"\x7fELF": "elf", b"\x89PNG": "png", b"\x1f\x8b": "gzip"}
    hits: List[str] = []
    for magic, label in known.items():
        offset = data.find(magic)
        if offset >= 0:
            hits.append(f"{label}@0x{offset:x}")
    return hits


def run_aapt(apk: Path) -> Optional[str]:
    sdk = Path.home() / "AppData/Local/Android/Sdk"
    candidates = sorted(sdk.glob("build-tools/*/aapt2.exe"), reverse=True)
    if not candidates:
        return None
    try:
        completed = subprocess.run(
            [str(candidates[0]), "dump", "badging", str(apk)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    return (completed.stdout + completed.stderr).strip() or None


def analyze_apk(apk: Path) -> ApkReport:
    logging.info("分析 APK: %s", apk)
    raw_size = apk.stat().st_size
    with zipfile.ZipFile(apk) as archive:
        infos = archive.infolist()
        compressed = sum(item.compress_size for item in infos)
        uncompressed = sum(item.file_size for item in infos)
        dex_reports: List[DexInfo] = []
        native_reports: List[NativeLibInfo] = []
        notable: List[str] = []
        all_strings: List[str] = []
        for item in infos:
            name = item.filename
            if name == "AndroidManifest.xml" or name.startswith(("META-INF/", "assets/", "lib/", "res/raw/")):
                notable.append(name)
            if name.endswith(".dex"):
                data = archive.read(item)
                version = data[4:7].decode("ascii", errors="replace") if data.startswith(b"dex\n") else "unknown"
                string_ids, type_ids, method_ids, class_defs = dex_metrics(data)
                data_size = struct.unpack_from("<I", data, 104)[0] if len(data) >= 108 else 0
                data_off = struct.unpack_from("<I", data, 108)[0] if len(data) >= 112 else 0
                trailing_offset = min(len(data), data_off + data_size)
                trailing = data[trailing_offset:]
                dex_strings = extract_dex_strings(data)
                descriptors = [value for value in dex_strings if value.startswith("L") and value.endswith(";")][:500]
                dex_reports.append(DexInfo(name, item.file_size, sha256_bytes(data), version, string_ids, type_ids, method_ids, class_defs, data_size, data_off, len(trailing), trailing[:16].hex(), entropy(trailing), find_magics(trailing), descriptors, dex_strings[:5000]))
                all_strings.extend(dex_strings)
            elif name.startswith("lib/") and name.endswith(".so"):
                data = archive.read(item)
                abi = name.split("/", maxsplit=2)[1] if name.count("/") >= 2 else "unknown"
                native_reports.append(NativeLibInfo(name, item.file_size, sha256_bytes(data), abi))
                all_strings.extend(extract_strings(data, 120))
        unique_strings: List[str] = []
        for value in all_strings:
            if value not in unique_strings:
                unique_strings.append(value)
        ratio = (uncompressed / compressed) if compressed else 0.0
        keyword_re = re.compile(r"(?i)(https?://|wss?://|api|token|secret|password|license|serial|loadlibrary|frida|xposed|root|debug|alipay|wechat|weixin|支付|密钥|校验)")
        keyword_hits = [value for value in unique_strings if keyword_re.search(value)][:200]
        network_re = re.compile(r"(?i)(https?://|wss?://|[a-z0-9.-]+\.(?:com|cn|net|org)(?:/|$)|/api|baseurl|server|host|socket|upload|download)")
        network_strings = [value for value in unique_strings if network_re.search(value)][:300]
        return ApkReport(
            path=str(apk.resolve()),
            size=raw_size,
            sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
            entries=len(infos),
            compression_ratio=round(ratio, 2),
            dex=dex_reports,
            native_libs=native_reports,
            notable_entries=notable[:500],
            strings=unique_strings[:300],
            keyword_hits=keyword_hits,
            network_strings=network_strings,
            aapt_badging=run_aapt(apk),
        )


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 APK 静态基线分析报告")
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/apk-analysis.json"))
    parser.add_argument("--log", type=Path, default=Path("logs/apk-analysis.log"))
    args = parser.parse_args()
    configure_logging(args.log)
    reports = [analyze_apk(apk) for apk in args.apks]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(report) for report in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("报告已写入: %s", args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
