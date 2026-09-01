from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import struct
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChunkProbe:
    kind: str
    offset: int
    valid: bool
    decoded_size: int = 0
    decoded_magic: str = ""
    entries: int = 0
    entry_names: tuple[str, ...] = ()
    elf_class: int = 0
    elf_machine: int = 0
    error: str = ""
    sha256: str = ""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def offsets(data: bytes, magic: bytes) -> list[int]:
    found: list[int] = []
    start = 0
    while True:
        position = data.find(magic, start)
        if position < 0:
            return found
        found.append(position)
        start = position + 1


def probe_gzip(data: bytes, position: int, absolute: int) -> ChunkProbe:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data[position:])) as stream:
            decoded = stream.read()
        return ChunkProbe("gzip", absolute, True, len(decoded), decoded[:4].decode("latin1"), sha256=sha256(decoded))
    except (OSError, EOFError, ValueError) as error:
        return ChunkProbe("gzip", absolute, False, error=type(error).__name__)


def probe_zip(data: bytes, position: int, absolute: int) -> ChunkProbe:
    try:
        with zipfile.ZipFile(io.BytesIO(data[position:])) as archive:
            names = tuple(item.filename for item in archive.infolist()[:8])
            return ChunkProbe("zip", absolute, True, entries=len(archive.infolist()), entry_names=names)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        return ChunkProbe("zip", absolute, False, error=type(error).__name__)


def probe_elf(data: bytes, position: int, absolute: int) -> ChunkProbe:
    if position + 20 > len(data):
        return ChunkProbe("elf", absolute, False, error="short_header")
    elf_class = data[position + 4]
    machine = struct.unpack_from("<H", data, position + 18)[0]
    valid = elf_class in {1, 2} and machine in {3, 40, 62, 183}
    return ChunkProbe("elf", absolute, valid, elf_class=elf_class, elf_machine=machine)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 Jiagu DEX 尾随区中的压缩、ZIP 和 ELF 候选块")
    parser.add_argument("dex", type=Path)
    parser.add_argument("--trailing-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.dex.read_bytes()
    tail = raw[args.trailing_offset:]
    probes: list[ChunkProbe] = []
    for magic, kind in ((b"\x1f\x8b", "gzip"), (b"PK\x03\x04", "zip"), (b"\x7fELF", "elf")):
        for position in offsets(tail, magic):
            absolute = args.trailing_offset + position
            if kind == "gzip":
                probes.append(probe_gzip(tail, position, absolute))
            elif kind == "zip":
                probes.append(probe_zip(tail, position, absolute))
            else:
                probes.append(probe_elf(tail, position, absolute))
    probes.sort(key=lambda item: (item.offset, item.kind))
    report = {
        "input": str(args.dex.resolve()),
        "input_sha256": sha256(raw),
        "input_size": len(raw),
        "trailing_offset": args.trailing_offset,
        "trailing_size": len(tail),
        "probes": [asdict(item) for item in probes],
        "valid": [asdict(item) for item in probes if item.valid],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "probes": len(probes), "valid": len(report["valid"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
