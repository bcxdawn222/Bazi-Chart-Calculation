from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


DEX_MAGICS = (b"dex\n035\x00", b"dex\n037\x00", b"cdex001\x00")


@dataclass(frozen=True)
class MemoryRegion:
    start: int
    end: int
    permissions: str
    path: str


@dataclass(frozen=True)
class DexRecord:
    path: str
    address: str
    size: int
    class_defs: int
    sha256: str
    region: str


@dataclass(frozen=True)
class MappedRecord:
    path: str
    source: str
    address: str
    size: int
    sha256: str


def run_adb(adb_path: Path, serial: str, arguments: list[str], binary: bool = False) -> subprocess.CompletedProcess[bytes]:
    command = [str(adb_path), "-s", serial] + arguments
    return subprocess.run(command, capture_output=True, timeout=120, check=False)


def parse_maps(text: str) -> list[MemoryRegion]:
    regions: list[MemoryRegion] = []
    for line in text.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 5:
            continue
        try:
            start_text, end_text = parts[0].split("-", 1)
            start, end = int(start_text, 16), int(end_text, 16)
        except ValueError:
            continue
        path = parts[5] if len(parts) == 6 else ""
        regions.append(MemoryRegion(start, end, parts[1], path))
    return regions


def priority(region: MemoryRegion, package: str) -> int:
    if "r" not in region.permissions:
        return -1
    path = region.path
    if "/.jiagu/" in path or package in path or "classes" in path:
        return 100
    if not path and "p" in region.permissions:
        return 80
    if path.startswith("[stack") or path.startswith("[vdso") or path.startswith("[vvar"):
        return 5
    if path.startswith("/data/"):
        return 60
    if path.startswith("/apex/") or path.startswith("/system/") or path.startswith("/vendor/"):
        return 10
    return 20


def candidate_regions(regions: list[MemoryRegion], package: str, limit: int) -> list[MemoryRegion]:
    selected: list[MemoryRegion] = []
    used = 0
    ordered = sorted(regions, key=lambda item: (-priority(item, package), item.start))
    for region in ordered:
        rank = priority(region, package)
        size = region.end - region.start
        if rank < 0 or size <= 0:
            continue
        if used + size > limit:
            continue
        selected.append(region)
        used += size
    return selected


def read_memory(adb_path: Path, serial: str, pid: int, address: int, size: int) -> bytes:
    command = (
        f"dd if=/proc/{pid}/mem iflag=skip_bytes,count_bytes "
        f"skip={address} count={size} 2>/dev/null"
    )
    result = run_adb(adb_path, serial, ["exec-out", "sh", "-c", command], binary=True)
    if result.returncode == 0 and len(result.stdout) == size:
        return result.stdout

    page_size = 4096
    if address % page_size != 0:
        return b""
    page_count = (size + page_size - 1) // page_size
    fallback = (
        f"dd if=/proc/{pid}/mem bs={page_size} "
        f"skip={address // page_size} count={page_count} 2>/dev/null"
    )
    fallback_result = run_adb(adb_path, serial, ["exec-out", "sh", "-c", fallback], binary=True)
    if fallback_result.returncode != 0 or len(fallback_result.stdout) < size:
        return b""
    return fallback_result.stdout[:size]


def plausible_header(data: bytes, offset: int) -> tuple[int, int] | None:
    if offset + 112 > len(data):
        return None
    magic = data[offset:offset + 8]
    if magic not in DEX_MAGICS[:2]:
        return None
    file_size, header_size, endian_tag = struct.unpack_from("<III", data, offset + 32)
    class_defs = struct.unpack_from("<I", data, offset + 96)[0]
    if header_size != 112 or endian_tag not in {0x12345678, 0x78563412}:
        return None
    if file_size < 112 or file_size > 128 * 1024 * 1024 or class_defs > 1_000_000:
        return None
    return file_size, class_defs


def scan_process(adb_path: Path, serial: str, pid: int, package: str, maps_text: str, output: Path, limit_mb: int) -> list[DexRecord]:
    output.mkdir(parents=True, exist_ok=True)
    regions = candidate_regions(parse_maps(maps_text), package, limit_mb * 1024 * 1024)
    records: list[DexRecord] = []
    seen: set[int] = set()
    chunk_size = 4 * 1024 * 1024
    for region in regions:
        overlap = b""
        cursor = region.start
        while cursor < region.end:
            size = min(chunk_size, region.end - cursor)
            block = read_memory(adb_path, serial, pid, cursor, size)
            if not block:
                break
            data = overlap + block
            base = cursor - len(overlap)
            for magic in DEX_MAGICS[:2]:
                search = 0
                while True:
                    local = data.find(magic, search)
                    if local < 0:
                        break
                    address = base + local
                    search = local + 1
                    if address in seen:
                        continue
                    header = plausible_header(data, local)
                    if header is None:
                        continue
                    file_size, class_defs = header
                    payload = read_memory(adb_path, serial, pid, address, file_size)
                    if len(payload) != file_size:
                        continue
                    seen.add(address)
                    target = output / f"memory-{len(records):03d}-{address:x}.dex"
                    target.write_bytes(payload)
                    records.append(DexRecord(
                        str(target.resolve()), hex(address), file_size, class_defs,
                        hashlib.sha256(payload).hexdigest(),
                        f"{hex(region.start)}-{hex(region.end)} {region.permissions} {region.path}".strip(),
                    ))
            overlap = data[-111:]
            cursor += len(block)
    (output / "memory-scan-index.json").write_text(json.dumps([asdict(item) for item in records], ensure_ascii=False, indent=2), encoding="utf-8")
    return records


def dump_private_mappings(adb_path: Path, serial: str, pid: int, package: str, maps_text: str, output: Path, limit_mb: int = 64) -> list[MappedRecord]:
    output.mkdir(parents=True, exist_ok=True)
    records: list[MappedRecord] = []
    total = 0
    seen: set[str] = set()
    regions = sorted(parse_maps(maps_text), key=lambda item: (-priority(item, package), item.start))
    for region in regions:
        path = region.path.removesuffix(" (deleted)")
        if not path.startswith(f"/data/data/{package}/"):
            continue
        if path.endswith("/base.apk") or path in seen:
            continue
        size = region.end - region.start
        if size <= 0 or size > 64 * 1024 * 1024 or total + size > limit_mb * 1024 * 1024:
            continue
        seen.add(path)
        payload = read_memory(adb_path, serial, pid, region.start, size)
        if len(payload) != size:
            continue
        safe = path.replace("/", "__").replace(":", "_")
        target = output / f"mapped-{len(records):03d}-{safe}.bin"
        target.write_bytes(payload)
        records.append(MappedRecord(
            str(target.resolve()), path, hex(region.start), size,
            hashlib.sha256(payload).hexdigest(),
        ))
        total += size
    (output / "mapped-memory-index.json").write_text(json.dumps([asdict(item) for item in records], ensure_ascii=False, indent=2), encoding="utf-8")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描 Android 进程内存中的合法 DEX 头并导出")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--package", required=True)
    parser.add_argument("--maps", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit-mb", type=int, default=512)
    parser.add_argument("--dump-private-mappings", action="store_true")
    args = parser.parse_args()
    adb_path = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
    maps_text = args.maps.read_text(encoding="utf-8", errors="replace")
    records = scan_process(adb_path, args.serial, args.pid, args.package, maps_text, args.output, args.limit_mb)
    mappings = dump_private_mappings(adb_path, args.serial, args.pid, args.package, maps_text, args.output) if args.dump_private_mappings else []
    print(json.dumps({"dex": [asdict(item) for item in records], "mappings": [asdict(item) for item in mappings]}, ensure_ascii=False, indent=2))
    return 0 if records or mappings else 6


if __name__ == "__main__":
    raise SystemExit(main())
