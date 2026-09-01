from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LoadSegment:
    index: int
    offset: int
    virtual_address: int
    file_size: int
    memory_size: int
    alignment: int
    flags: int


@dataclass(frozen=True)
class ElfReport:
    path: str
    size: int
    machine: int
    segments: list[LoadSegment]
    page_compatible: bool


def iter_paths(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    yield from sorted(root.rglob("*.so"))


def analyze(path: Path, required_alignment: int) -> ElfReport | None:
    data = path.read_bytes()
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    machine = struct.unpack_from("<H", data, 18)[0]
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]
    segments: list[LoadSegment] = []
    for index in range(phnum):
        base = phoff + index * phentsize
        if base + 56 > len(data):
            break
        p_type, flags = struct.unpack_from("<II", data, base)
        if p_type != 1:
            continue
        offset, vaddr, _, filesz, memsz, alignment = struct.unpack_from("<QQQQQQ", data, base + 8)
        segments.append(LoadSegment(index, offset, vaddr, filesz, memsz, alignment, flags))
    compatible = all(
        segment.alignment >= required_alignment
        and segment.offset % required_alignment == segment.virtual_address % required_alignment
        for segment in segments
    )
    return ElfReport(str(path.resolve()), len(data), machine, segments, compatible)


def main() -> int:
    parser = argparse.ArgumentParser(description="只读检查 ELF PT_LOAD 对齐")
    parser.add_argument("root", type=Path)
    parser.add_argument("--required-alignment", type=int, default=16384)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [item for path in iter_paths(args.root) if (item := analyze(path, args.required_alignment)) is not None]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(item) for item in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(reports), "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
