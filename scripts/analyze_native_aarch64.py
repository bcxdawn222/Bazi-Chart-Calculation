from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


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
class InstructionRef:
    string: str
    function_address: str
    instruction_address: str
    instruction: str
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
    references: list[InstructionRef] = field(default_factory=list)
    imported_names: list[str] = field(default_factory=list)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def map_address(segments: list[Segment], file_offset: int) -> int | None:
    for segment in segments:
        if segment.offset <= file_offset < segment.offset + segment.filesz:
            return segment.vaddr + file_offset - segment.offset
    return None


def parse_elf(data: bytes) -> tuple[int, list[Segment], int]:
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError("expected little-endian ELF64")
    entry = struct.unpack_from("<Q", data, 24)[0]
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]
    segments: list[Segment] = []
    for index in range(phnum):
        base = phoff + index * phentsize
        p_type, flags = struct.unpack_from("<II", data, base)
        if p_type != 1:
            continue
        offset, vaddr, _, filesz, memsz = struct.unpack_from("<QQQQQ", data, base + 8)
        segments.append(Segment(offset, vaddr, filesz, memsz, flags, bool(flags & 1)))
    machine = struct.unpack_from("<H", data, 18)[0]
    return machine, segments, entry


def ascii_hits(data: bytes, segments: list[Segment]) -> list[StringHit]:
    wanted = ("RMUTGF", "JIAGU_", "libijmData", "assets/.jgapp", "/proc/self/maps", "DexFile", "inflate", "dlopen", "mmap")
    hits: list[StringHit] = []
    start = 0
    while start < len(data):
        end = data.find(b"\x00", start)
        if end < 0:
            break
        raw = data[start:end]
        if 5 <= len(raw) <= 256:
            text = raw.decode("ascii", errors="ignore")
            if any(token in text for token in wanted):
                hits.append(StringHit(text, start, map_address(segments, start)))
        start = end + 1
    return hits


def imported_names(data: bytes) -> list[str]:
    tokens = ("fopen", "fread", "inflate", "mmap", "dlopen", "inotify", "pread", "strcmp", "memcpy", "AES", "JNI_OnLoad")
    values: list[str] = []
    for token in tokens:
        if token.encode() in data:
            values.append(token)
    return values


def disassemble_refs(data: bytes, segments: list[Segment], strings: list[StringHit]) -> list[InstructionRef]:
    spec = importlib.util.spec_from_file_location("capstone", Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python" / "capstone" / "__init__.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("capstone is not installed in .tools/reverse/python")
    capstone = importlib.util.module_from_spec(spec)
    sys.modules["capstone"] = capstone
    spec.loader.exec_module(capstone)
    from capstone.arm64 import ARM64_INS_ADD, ARM64_INS_ADRP, ARM64_INS_LDR

    targets = {item.virtual_address: item.value for item in strings if item.virtual_address is not None}
    references: list[InstructionRef] = []
    for segment in segments:
        if not segment.executable or segment.filesz == 0:
            continue
        disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        disassembler.detail = True
        chunk_size = 0x1000
        for chunk_offset in range(0, segment.filesz, chunk_size):
            start = segment.offset + chunk_offset
            code = data[start:min(segment.offset + segment.filesz, start + chunk_size)]
            address = segment.vaddr + chunk_offset
            instructions = list(disassembler.disasm(code, address))
            for index, instruction in enumerate(instructions):
                candidates: list[tuple[int, str]] = []
                if instruction.id == ARM64_INS_ADRP and len(instruction.operands) >= 2:
                    base = instruction.operands[1].imm
                    register = instruction.operands[0].reg
                    for following in instructions[index + 1:index + 4]:
                        if following.id == ARM64_INS_ADD and len(following.operands) >= 3:
                            same_source = following.operands[1].reg == register
                            immediate = following.operands[2].imm if following.operands[2].type == capstone.arm64.ARM64_OP_IMM else None
                            if same_source and immediate is not None:
                                candidates.append((base + immediate, f"{instruction.mnemonic} {instruction.op_str}; {following.mnemonic} {following.op_str}"))
                        if following.id == ARM64_INS_LDR and len(following.operands) >= 2 and following.operands[1].type == capstone.arm64.ARM64_OP_MEM:
                            memory = following.operands[1].mem
                            if memory.base == register:
                                candidates.append((base + memory.disp, f"{instruction.mnemonic} {instruction.op_str}; {following.mnemonic} {following.op_str}"))
                elif instruction.id == ARM64_INS_LDR and len(instruction.operands) >= 2 and instruction.operands[1].type == capstone.arm64.ARM64_OP_MEM:
                    memory = instruction.operands[1].mem
                    if memory.base == 31:
                        candidates.append((instruction.address + memory.disp, f"{instruction.mnemonic} {instruction.op_str}"))
                for candidate, text in candidates:
                    for target, value in targets.items():
                        if candidate == target:
                            nearby = tuple(f"0x{item.address:x}: {item.mnemonic} {item.op_str}" for item in instructions[max(0, index - 2):index + 5])
                            references.append(InstructionRef(value, f"0x{instruction.address:x}", f"0x{instruction.address:x}", text, nearby))
                            break
    return references


def analyze(path: Path) -> NativeReport:
    data = path.read_bytes()
    machine, segments, entry = parse_elf(data)
    strings = ascii_hits(data, segments)
    return NativeReport(str(path.resolve()), len(data), sha256(data), "ELF64", machine, f"0x{entry:x}", segments, strings, disassemble_refs(data, segments, strings), imported_names(data))


def main() -> int:
    parser = argparse.ArgumentParser(description="分析 AArch64 ELF 中的 Jiagu 字符串引用")
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
