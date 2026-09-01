from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Capture:
    path: str
    source: str
    begin: str
    size: int
    class_defs: int
    sha256: str


def load_frida() -> Any:
    root = Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python"
    sys.path.insert(0, str(root))
    import frida

    return frida


def javascript() -> str:
    return r'''
const seen = new Set();
const hooked = new Set();
let registerProbes = 0;

function emit(payload, data) { send(payload, data || null); }

function readDexLayout(candidate, beginOffset, sizeOffset, source) {
  try {
    if (candidate === null || candidate.isNull()) return;
    const begin = candidate.add(beginOffset).readPointer();
    const size = candidate.add(sizeOffset).readU64().toNumber();
    if (begin.isNull() || size < 112 || size > 128 * 1024 * 1024) return;
    const magic = begin.readUtf8String(4);
    if (magic !== "dex\n" && magic !== "cdex") return;
    const key = begin.toString() + ":" + size;
    if (seen.has(key)) return;
    const headerSize = begin.add(36).readU32();
    const classDefs = begin.add(96).readU32();
    if (headerSize !== 112 || classDefs > 1000000) return;
    const bytes = begin.readByteArray(size);
    if (bytes === null) return;
    seen.add(key);
    emit({type: "dex", source: source, begin: begin.toString(), size: size, class_defs: classDefs}, bytes);
  } catch (error) {
    emit({type: "candidate_error", source: source, candidate: String(candidate), error: String(error)});
  }
}

function readDexCandidate(candidate, source) {
  const layouts = [[0, 8], [8, 16], [8, 32], [16, 24], [24, 32], [32, 40], [40, 48]];
  for (const layout of layouts) readDexLayout(candidate, layout[0], layout[1], source + ":" + layout[0] + ":" + layout[1]);
}

function probeCandidate(candidate, source) {
  if (registerProbes > 24) return;
  try {
    if (candidate === null || candidate.isNull()) {
      emit({type: "candidate_probe", source: source, value: "null"});
      return;
    }
    const values = [];
    for (let offset = 0; offset < 48; offset += Process.pointerSize) {
      try { values.push({offset: offset, value: candidate.add(offset).readPointer().toString()}); }
      catch (error) { values.push({offset: offset, error: String(error)}); }
    }
    emit({type: "candidate_probe", source: source, candidate: candidate.toString(), values: values});
  } catch (error) {
    emit({type: "candidate_probe_error", source: source, error: String(error)});
  }
}

function hookByName(pattern, callback) {
  for (const module of Process.enumerateModules()) {
    if (!/^libart(\.base)?\.so$/.test(module.name)) continue;
    let symbols = [];
    try { symbols = module.enumerateSymbols(); } catch (error) { continue; }
    for (const item of symbols) {
      if (!pattern.test(item.name)) continue;
      const key = item.address.toString();
      if (hooked.has(key)) continue;
      try {
        Interceptor.attach(item.address, callback(item.name));
        hooked.add(key);
        emit({type: "hook_installed", symbol: item.name, address: key});
      } catch (error) {
        emit({type: "hook_error", symbol: item.name, address: key, error: String(error)});
      }
    }
  }
}

function safeString(pointer) {
  try { return pointer.isNull() ? "" : pointer.readCString(); } catch (error) { return ""; }
}

emit({type: "script_loaded"});

hookByName(/ClassLinker.*RegisterDexFileLocked/, function (name) {
  return {
    onEnter(args) {
      emit({type: "register_enter", symbol: name});
      // RegisterDexFileLocked receives `this` followed by a DexFile reference.
      if (registerProbes < 8) {
        for (let index = 0; index < 6; index += 1) probeCandidate(args[index], name + ":arg" + index);
        registerProbes += 1;
      }
      readDexCandidate(args[1], name + ":arg1");
      readDexCandidate(args[0], name + ":arg0");
    }
  };
});

hookByName(/DexFile_open(InMemoryDexFilesNative|DexFileNative)/, function (name) {
  return {
    onEnter(args) {
      emit({type: "dex_open_enter", symbol: name});
      for (let index = 0; index < 6; index += 1) {
        readDexCandidate(args[index], name + ":arg" + index);
      }
    }
  };
});

hookByName(/DexFileLoader.*Open(Common|Memory)/, function (name) {
  return {
    onEnter(args) {
      emit({type: "loader_open_enter", symbol: name, arg0: safeString(args[0]), arg1: safeString(args[1])});
      for (let index = 0; index < 6; index += 1) {
        readDexCandidate(args[index], name + ":arg" + index);
      }
    }
  };
});

emit({type: "hooks_ready"});
'''


def handle_message(message: dict[str, Any], data: bytes | None, output: Path, captures: list[Capture]) -> None:
    if message.get("type") == "error":
        with (output / "frida-errors.log").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(message, ensure_ascii=False) + "\n")
        print(json.dumps(message, ensure_ascii=False), flush=True)
        return
    payload = message.get("payload")
    if not isinstance(payload, dict):
        return
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    if payload.get("type") != "dex" or data is None:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return
    digest = hashlib.sha256(data).hexdigest()
    if any(item.sha256 == digest for item in captures):
        print(json.dumps({"type": "duplicate_dex", "sha256": digest}, ensure_ascii=False), flush=True)
        return
    target = output / f"capture-{len(captures):03d}-{digest[:16]}.dex"
    target.write_bytes(data)
    capture = Capture(str(target.resolve()), str(payload.get("source", "unknown")),
                      str(payload.get("begin", "")), len(data), int(payload.get("class_defs", 0)), digest)
    captures.append(capture)
    print(json.dumps(asdict(capture), ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="在 ART DexFile 注册点捕获运行时 DEX")
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--host", default="127.0.0.1:27042")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frida = load_frida()
    device = frida.get_device_manager().add_remote_device(args.host)
    pid = device.spawn([args.package])
    session = device.attach(pid)
    captures: list[Capture] = []

    def on_message(message: dict[str, Any], data: bytes | None) -> None:
        handle_message(message, data, args.output, captures)

    script = session.create_script(javascript())
    script.on("message", on_message)
    script.load()
    device.resume(pid)
    time.sleep(args.seconds)
    session.detach()
    (args.output / "capture-index.json").write_text(
        json.dumps([asdict(item) for item in captures], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"captured": len(captures), "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0 if captures else 6


if __name__ == "__main__":
    raise SystemExit(main())
