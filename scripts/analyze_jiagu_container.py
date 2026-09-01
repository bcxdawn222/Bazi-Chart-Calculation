from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


PRINTABLE = re.compile(rb"[ -~]{6,}")
MAGICS = {
    b"dex\n": "dex",
    b"cdex": "cdex",
    b"PK\x03\x04": "zip",
    b"\x7fELF": "elf",
    b"\x1f\x8b": "gzip",
    b"BZh": "bzip2",
    b"\x28\xb5\x2f\xfd": "zstd",
    b"\x04\x22\x4d\x18": "lz4",
}


@dataclass(frozen=True)
class DEXHeader:
    file_size: int
    header_size: int
    endian_tag: int
    string_ids: int
    type_ids: int
    proto_ids: int
    field_ids: int
    method_ids: int
    class_defs: int
    data_size: int
    data_off: int
    data_end: int


@dataclass(frozen=True)
class MagicHit:
    kind: str
    offset: int
    context_sha256: str


@dataclass(frozen=True)
class NativeEvidence:
    path: str
    size: int
    sha256: str
    elf_class: str
    machine: str
    strings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContainerReport:
    apk: str
    apk_sha256: str
    apk_size: int
    dex_name: str
    dex_sha256: str
    dex_size: int
    dex_header: DEXHeader | None
    trailing_offset: int
    trailing_size: int
    trailing_sha256: str
    trailing_entropy: float
    magic_hits: list[MagicHit]
    trailing_strings: list[str]
    candidate_boundaries: list[int]
    native_evidence: list[NativeEvidence]
    zip_entries: list[dict[str, int | str]]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    length = len(data)
    return round(-sum((count / length) * math.log2(count / length) for count in counts if count), 5)


def parse_dex_header(data: bytes) -> DEXHeader | None:
    if len(data) < 112 or not data.startswith(b"dex\n"):
        return None
    file_size = struct.unpack_from("<I", data, 32)[0]
    header_size = struct.unpack_from("<I", data, 36)[0]
    endian_tag = struct.unpack_from("<I", data, 40)[0]
    string_ids = struct.unpack_from("<I", data, 56)[0]
    type_ids = struct.unpack_from("<I", data, 64)[0]
    proto_ids = struct.unpack_from("<I", data, 72)[0]
    field_ids = struct.unpack_from("<I", data, 80)[0]
    method_ids = struct.unpack_from("<I", data, 88)[0]
    class_defs = struct.unpack_from("<I", data, 96)[0]
    data_size = struct.unpack_from("<I", data, 104)[0]
    data_off = struct.unpack_from("<I", data, 108)[0]
    return DEXHeader(
        file_size=file_size,
        header_size=header_size,
        endian_tag=endian_tag,
        string_ids=string_ids,
        type_ids=type_ids,
        proto_ids=proto_ids,
        field_ids=struct.unpack_from("<I", data, 80)[0],
        method_ids=method_ids,
        class_defs=class_defs,
        data_size=data_size,
        data_off=data_off,
        data_end=min(len(data), data_off + data_size),
    )


def magic_hits(data: bytes, base: int = 0) -> list[MagicHit]:
    hits: list[MagicHit] = []
    for magic, kind in MAGICS.items():
        start = 0
        while True:
            offset = data.find(magic, start)
            if offset < 0:
                break
            context = data[max(0, offset - 16): offset + 64]
            hits.append(MagicHit(kind, base + offset, sha256(context)))
            start = offset + 1
    return sorted(hits, key=lambda item: item.offset)


def printable_strings(data: bytes, limit: int = 200) -> list[str]:
    values: list[str] = []
    for match in PRINTABLE.finditer(data):
        value = match.group().decode("ascii", errors="replace")
        if value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return values


def native_info(path: Path) -> NativeEvidence:
    data = path.read_bytes()
    machine = "unknown"
    elf_class = "unknown"
    if data[:4] == b"\x7fELF" and len(data) >= 20:
        elf_class = {1: "ELF32", 2: "ELF64"}.get(data[4], f"ELF{data[4]}")
        machine_value = struct.unpack_from("<H", data, 18)[0]
        machine = {40: "ARM", 183: "AArch64", 62: "x86_64", 3: "x86"}.get(machine_value, str(machine_value))
    selected = [
        value for value in printable_strings(data, 1000)
        if any(token in value for token in ("jiagu", "JIAGU", "RMUTGF", "Encryption", "Dex", "dex", "GetKey", "Password", "maps"))
    ][:80]
    return NativeEvidence(str(path.resolve()), len(data), sha256(data), elf_class, machine, selected)


def candidate_boundaries(data: bytes, header: DEXHeader | None) -> list[int]:
    candidates = {0}
    if header is not None:
        candidates.update({header.data_end, header.file_size, header.header_size})
    for hit in magic_hits(data):
        candidates.add(hit.offset)
    for marker in (b"JIAGU", b"RMUTGF", b"AES", b"KEY", b"IV"):
        start = 0
        while True:
            offset = data.find(marker, start)
            if offset < 0:
                break
            candidates.add(offset)
            start = offset + 1
    return sorted(value for value in candidates if 0 <= value < len(data))


def iter_native_entries(archive: zipfile.ZipFile) -> Iterable[tuple[str, bytes]]:
    for item in archive.infolist():
        if item.filename.startswith("lib/") and item.filename.endswith(".so"):
            yield item.filename, archive.read(item)


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 Jiagu DEX 尾随容器和相关 Native 证据")
    parser.add_argument("apk", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_apk = args.apk.read_bytes()
    with zipfile.ZipFile(args.apk) as archive:
        dex_entry = archive.getinfo("classes.dex")
        dex = archive.read(dex_entry)
        header = parse_dex_header(dex)
        trailing_offset = header.data_end if header else len(dex)
        trailing = dex[trailing_offset:]
        natives: list[NativeEvidence] = []
        for name, content in iter_native_entries(archive):
            if any(token in name for token in ("libjiagu", "libyiqilibrary")):
                temp = args.output.parent / ".native-cache" / name.replace("/", "_")
                temp.parent.mkdir(parents=True, exist_ok=True)
                temp.write_bytes(content)
                natives.append(native_info(temp))
        entries = [
            {"name": item.filename, "size": item.file_size, "compressed": item.compress_size}
            for item in archive.infolist()
            if item.filename in {"classes.dex", "AndroidManifest.xml", "assets/.jgapp", "assets/nearme.apk"}
        ]
    report = ContainerReport(
        apk=str(args.apk.resolve()),
        apk_sha256=sha256(raw_apk),
        apk_size=len(raw_apk),
        dex_name="classes.dex",
        dex_sha256=sha256(dex),
        dex_size=len(dex),
        dex_header=header,
        trailing_offset=trailing_offset,
        trailing_size=len(trailing),
        trailing_sha256=sha256(trailing),
        trailing_entropy=entropy(trailing),
        magic_hits=magic_hits(trailing, trailing_offset),
        trailing_strings=printable_strings(trailing),
        candidate_boundaries=candidate_boundaries(dex, header),
        native_evidence=natives,
        zip_entries=entries,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
