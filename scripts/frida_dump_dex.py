from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class DumpRecord:
    path: str
    address: str
    size: int
    class_defs: int
    sha256: str


def load_frida() -> Any:
    tool_root = Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python"
    sys.path.insert(0, str(tool_root))
    import frida

    return frida


def javascript() -> str:
    return r"""
const seen = new Set();
const patterns = [
  "64 65 78 0a 30 33 35 00",
  "64 65 78 0a 30 33 37 00",
  "63 64 65 78 30 30 31 00"
];

function scanRange(range) {
  if (range.size < 112 || range.size > 128 * 1024 * 1024) return;
  Memory.scan(range.base, range.size, patterns[0], {
    onMatch(address) { emitDex(address, range); },
    onComplete() {
      Memory.scan(range.base, range.size, patterns[1], {
        onMatch(address) { emitDex(address, range); },
        onComplete() {
          Memory.scan(range.base, range.size, patterns[2], {
            onMatch(address) { emitDex(address); },
            onComplete() {}
          });
        }
      });
    }
  });
}

function emitDex(address, range) {
  const key = address.toString();
  if (seen.has(key)) return;
  seen.add(key);
  try {
    const fileSize = address.add(32).readU32();
    const headerSize = address.add(36).readU32();
    const classDefs = address.add(96).readU32();
    if (headerSize !== 112 || fileSize < 112 || fileSize > 128 * 1024 * 1024) return;
    const bytes = address.readByteArray(fileSize);
    if (bytes === null) return;
    send({
      type: "dex",
      address: key,
      size: fileSize,
      class_defs: classDefs,
      range: range.base.toString() + "+" + range.size
    }, bytes);
  } catch (error) {
    send({ type: "scan_error", address: key, error: String(error) });
  }
}

function installRegisterHook() {
  const symbol = "_ZN3art11ClassLinker15RegisterDexFileERKNS_7DexFileENS_6ObjPtrINS_6mirror11ClassLoaderEEE";
  let target = Module.findGlobalExportByName(symbol);
  if (target === null) {
    const module = Process.getModuleByName("libart.so");
    const matches = module.enumerateSymbols().filter(item => item.name === symbol);
    target = matches.length > 0 ? matches[0].address : null;
  }
  if (target === null) {
    send({ type: "hook_missing", symbol: symbol });
    return;
  }
  Interceptor.attach(target, {
    onEnter(args) {
      try {
        const dexFile = args[1];
        const begin = dexFile.readPointer();
        send({ type: "dex_registered", object: dexFile.toString(), begin: begin.toString() });
        emitDex(begin, { base: begin, size: 128 * 1024 * 1024 });
      } catch (error) {
        send({ type: "register_error", error: String(error) });
      }
    }
  });
  send({ type: "hook_installed", symbol: symbol, address: target.toString() });
}

function scanAll() {
  const ranges = Process.enumerateRanges({ protection: "r--", coalesce: false });
  ranges.concat(Process.enumerateRanges({ protection: "rw-", coalesce: false }))
    .concat(Process.enumerateRanges({ protection: "r-x", coalesce: false }))
    .filter(range => range.size <= 128 * 1024 * 1024)
    .forEach(scanRange);
  send({ type: "scan_ranges", count: ranges.length });
}

installRegisterHook();
scanAll();
send({ type: "scan_started" });
setInterval(scanAll, 1000);
"""


def handle_message(message: dict[str, Any], data: bytes | None, output: Path, records: list[DumpRecord]) -> None:
    if message.get("type") == "error":
        print(json.dumps(message, ensure_ascii=False), flush=True)
        return
    payload = message.get("payload", {})
    if not isinstance(payload, dict):
        return
    if payload.get("type") == "scan_error":
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return
    if payload.get("type") in {"scan_started", "scan_ranges", "hook_missing", "hook_installed", "hook_offset_fallback", "dex_registered", "register_error"}:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return
    if payload.get("type") != "dex" or data is None:
        return
    digest = hashlib.sha256(data).hexdigest()
    target = output / f"memory-{len(records):03d}-{payload['address'].replace('0x', '')}.dex"
    target.write_bytes(data)
    record = DumpRecord(str(target.resolve()), str(payload["address"]), len(data), int(payload["class_defs"]), digest)
    records.append(record)
    print(json.dumps(asdict(record), ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 Frida 扫描 Android 进程内存并导出 DEX")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--package")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--host", default="127.0.0.1:27042")
    args = parser.parse_args()
    if args.pid is None and args.package is None:
        parser.error("--pid or --package is required")
    args.output.mkdir(parents=True, exist_ok=True)
    frida = load_frida()
    device = frida.get_device_manager().add_remote_device(args.host)
    spawned = args.package is not None
    target_pid = device.spawn([args.package]) if spawned else args.pid
    session = device.attach(target_pid)
    records: list[DumpRecord] = []
    script = session.create_script(javascript())
    script.on("message", lambda message, data: handle_message(message, data, args.output, records))
    script.load()
    if spawned:
        device.resume(target_pid)
    time.sleep(args.seconds)
    session.detach()
    index = args.output / "memory-dex-index.json"
    index.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"captured={len(records)} output={args.output.resolve()}")
    return 0 if records else 6


if __name__ == "__main__":
    raise SystemExit(main())
