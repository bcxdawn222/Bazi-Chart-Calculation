from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


PT_LOAD = 1
PT_DYNAMIC = 2
DT_HASH = 4
DT_STRTAB = 5
DT_SYMTAB = 6
DT_STRSZ = 10
DT_SYMENT = 11
DT_GNU_HASH = 0x6FFFFEF5


@dataclass(frozen=True)
class Segment:
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    flags: int
    executable: bool


@dataclass(frozen=True)
class StringHit:
    value: str
    file_offset: int
    virtual_address: int | None


@dataclass(frozen=True)
class DynamicSymbol:
    name: str
    value: int
    size: int
    defined: bool


@dataclass(frozen=True)
class CodeReference:
    string: str
    instruction_address: str
    instruction: str
    target_address: str
    nearby: tuple[str, ...]


@dataclass(frozen=True)
class NativeReport:
    path: str
    size: int
    sha256: str
    elf_class: str
    machine: int
    entry: str
    segments: list[Segment]
    strings: list[StringHit]
    dynamic_symbols: list[DynamicSymbol]
    references: list[CodeReference] = field(default_factory=list)
    imported_names: list[str] = field(default_factory=list)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vaddr_to_offset(segments: Iterable[Segment], address: int) -> int | None:
    for segment in segments:
        if segment.vaddr <= address < segment.vaddr + segment.filesz:
            return segment.offset + address - segment.vaddr
    return None


def parse_elf(data: bytes) -> tuple[int, int, list[Segment], list[tuple[int, int]]]:
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError("expected little-endian ELF64")
    machine = struct.unpack_from("<H", data, 18)[0]
    entry = struct.unpack_from("<Q", data, 24)[0]
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]
    segments: list[Segment] = []
    dynamic: list[tuple[int, int]] = []
    for index in range(phnum):
        base = phoff + index * phentsize
        p_type, flags = struct.unpack_from("<II", data, base)
        offset, vaddr, _, filesz, memsz = struct.unpack_from("<QQQQQ", data, base + 8)
        if p_type == PT_LOAD:
            segments.append(Segment(offset, vaddr, filesz, memsz, flags, bool(flags & 1)))
        elif p_type == PT_DYNAMIC:
            for cursor in range(offset, min(offset + filesz, len(data)), 16):
                tag, value = struct.unpack_from("<QQ", data, cursor)
                dynamic.append((tag, value))
                if tag == 0:
                    break
    return machine, entry, segments, dynamic


def dynamic_symbols(data: bytes, segments: list[Segment], dynamic: list[tuple[int, int]]) -> list[DynamicSymbol]:
    tags = {tag: value for tag, value in dynamic}
    strtab_address = tags.get(DT_STRTAB)
    symtab_address = tags.get(DT_SYMTAB)
    if strtab_address is None or symtab_address is None:
        return []
    strtab_offset = vaddr_to_offset(segments, strtab_address)
    symtab_offset = vaddr_to_offset(segments, symtab_address)
    if strtab_offset is None or symtab_offset is None:
        return []
    strtab_size = int(tags.get(DT_STRSZ, len(data) - strtab_offset))
    syment = int(tags.get(DT_SYMENT, 24))
    count = 0
    hash_address = tags.get(DT_HASH)
    if hash_address is not None:
        hash_offset = vaddr_to_offset(segments, hash_address)
        if hash_offset is not None and hash_offset + 8 <= len(data):
            _, count = struct.unpack_from("<II", data, hash_offset)
    if count == 0:
        count = max(0, (strtab_offset - symtab_offset) // syment)
    result: list[DynamicSymbol] = []
    for index in range(count):
        base = symtab_offset + index * syment
        if base + 24 > len(data):
            break
        name_offset, info, _, _ = struct.unpack_from("<IBBH", data, base)
        value, size = struct.unpack_from("<QQ", data, base + 8)
        if name_offset >= strtab_size:
            name = ""
        else:
            start = strtab_offset + name_offset
            end = data.find(b"\x00", start, strtab_offset + strtab_size)
            end = len(data) if end < 0 else end
            name = data[start:end].decode("utf-8", errors="replace")
        result.append(DynamicSymbol(name, value, size, bool((info & 0x0F) != 0 and value != 0)))
    return result


def ascii_hits(data: bytes, segments: list[Segment]) -> list[StringHit]:
    wanted = (
        "RMUTGF", "JIAGU_", "libijmData", "assets/.jgapp", "/proc/self/maps",
        "DexFile", "inflate", "dlopen", "mmap", "fread", "pread", "inotify",
    )
    hits: list[StringHit] = []
    start = 0
    while start < len(data):
        end = data.find(b"\x00", start)
        if end < 0:
            break
        raw = data[start:end]
        if 4 <= len(raw) <= 256:
            text = raw.decode("ascii", errors="ignore")
            if any(token in text for token in wanted):
                hits.append(StringHit(text, start, vaddr_to_offset_inverse(segments, start)))
        start = end + 1
    return hits


def vaddr_to_offset_inverse(segments: list[Segment], file_offset: int) -> int | None:
    for segment in segments:
        if segment.offset <= file_offset < segment.offset + segment.filesz:
            return segment.vaddr + file_offset - segment.offset
    return None


def load_capstone():
    root = Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python"
    sys.path.insert(0, str(root))
    import capstone
    from capstone.x86_const import X86_REG_RIP
    return capstone, X86_REG_RIP


def disassemble_refs(data: bytes, segments: list[Segment], strings: list[StringHit]) -> list[CodeReference]:
    capstone, rip = load_capstone()
    targets = {item.virtual_address: item.value for item in strings if item.virtual_address is not None}
    references: list[CodeReference] = []
    seen: set[tuple[int, int]] = set()
    for segment in segments:
        if not segment.executable or segment.filesz == 0:
            continue
        disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        disassembler.detail = True
        code_start = segment.offset
        code_end = segment.offset + segment.filesz
        for file_offset in range(code_start, code_end):
            code = data[file_offset:min(code_end, file_offset + 15)]
            instruction = next(disassembler.disasm(code, segment.vaddr + file_offset - segment.offset), None)
            if instruction is None:
                continue
            for operand in instruction.operands:
                if operand.type != capstone.x86.X86_OP_MEM or operand.mem.base != rip:
                    continue
                target = instruction.address + instruction.size + operand.mem.disp
                if target not in targets:
                    continue
                key = (instruction.address, target)
                if key in seen:
                    continue
                seen.add(key)
                context_start = max(code_start, file_offset - 16)
                context_end = min(code_end, file_offset + 48)
                context_code = data[context_start:context_end]
                context = list(disassembler.disasm(context_code, segment.vaddr + context_start - segment.offset))
                nearby = tuple(f"0x{item.address:x}: {item.mnemonic} {item.op_str}" for item in context)
                references.append(CodeReference(
                    targets[target], f"0x{instruction.address:x}",
                    f"{instruction.mnemonic} {instruction.op_str}",
                    f"0x{target:x}", nearby,
                ))
    return references


def analyze(path: Path) -> NativeReport:
    data = path.read_bytes()
    machine, entry, segments, dynamic = parse_elf(data)
    strings = ascii_hits(data, segments)
    symbols = dynamic_symbols(data, segments, dynamic)
    imported = sorted({item.name for item in symbols if not item.defined and item.name})
    return NativeReport(
        str(path.resolve()), len(data), digest(data), "ELF64", machine,
        f"0x{entry:x}", segments, strings, symbols,
        disassemble_refs(data, segments, strings), imported,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 x86_64 Jiagu 壳库的字符串引用和动态符号")
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [analyze(path) for path in args.paths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(report) for report in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
