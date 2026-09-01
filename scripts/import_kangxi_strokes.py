from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import TypedDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tmp" / "kangxi-mcp" / "packages" / "kangxi-core" / "data" / "chars.json.gz"
DEFAULT_OUTPUT = ROOT / "miniprogram" / "data" / "kangxi-strokes.js"
SOURCE_COMMIT = "fad0bdf7c34b0ec555edbb2af91db737825a4beb"


class SourceChar(TypedDict, total=False):
    kx: int
    src: str
    t: str


class CompactChar(TypedDict, total=False):
    k: int
    t: str


class SourceFile(TypedDict):
    chars: dict[str, SourceChar]
    alias: dict[str, str]
    meta: dict[str, int]


class OutputFile(TypedDict):
    chars: dict[str, CompactChar]
    alias: dict[str, str]
    traditional: dict[str, str]
    meta: dict[str, int | str]


def load_source(path: Path) -> SourceFile:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def build_output(source: SourceFile) -> OutputFile:
    common = {
        char: entry
        for char, entry in source["chars"].items()
        if entry.get("src") == "b"
    }
    chars: dict[str, CompactChar] = {}
    traditional: dict[str, str] = {}
    for char, entry in common.items():
        compact: CompactChar = {"k": int(entry["kx"])}
        if entry.get("t"):
            compact["t"] = entry["t"]
            traditional.setdefault(entry["t"], char)
        chars[char] = compact

    alias = {
        alias_char: target
        for alias_char, target in source["alias"].items()
        if target in chars
    }
    return {
        "chars": chars,
        "alias": alias,
        "traditional": traditional,
        "meta": {
            "source": "shunshi-ai/kangxi-mcp",
            "license": "MIT",
            "sourceCommit": SOURCE_COMMIT,
            "sourceVersion": "main snapshot 2026-08-27",
            "commonCount": len(chars),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="导入康熙笔画常用字数据")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(f"找不到数据源：{args.source}")
    output = build_output(load_source(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    args.output.write_text(f"module.exports = {serialized};\n", encoding="utf-8")
    print(f"已导入 {output['meta']['commonCount']} 个常用字：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
