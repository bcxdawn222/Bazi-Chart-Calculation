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
class CaptureRecord:
    path: str
    source: str
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
const emitted = new Set();
const dexPatterns = [
  "64 65 78 0a 30 33 35 00",
  "64 65 78 0a 30 33 37 00",
  "63 64 65 78 30 30 31 00"
];

function report(payload, data) {
  send(payload, data || null);
}

function safeReadDex(address, source) {
  try {
    const magic = address.readByteArray(8);
    if (magic === null) return;
    const fileSize = address.add(32).readU32();
    const headerSize = address.add(36).readU32();
    const classDefs = address.add(96).readU32();
    if (headerSize !== 112 || fileSize < 112 || fileSize > 128 * 1024 * 1024) return;
    const key = address.toString() + ":" + fileSize;
    if (emitted.has(key)) return;
    const bytes = address.readByteArray(fileSize);
    if (bytes === null) return;
    emitted.add(key);
    report({type: "dex", source: source, address: address.toString(), size: fileSize, class_defs: classDefs}, bytes);
  } catch (error) {
    report({type: "read_error", source: source, address: address.toString(), error: String(error)});
  }
}

function scanBuffer(address, size, source) {
  if (address === null || size < 8 || size > 128 * 1024 * 1024) return;
  for (const pattern of dexPatterns) {
    try {
      const matches = Memory.scanSync(address, size, pattern);
      for (const match of matches) safeReadDex(match.address, source);
    } catch (error) {
      report({type: "scan_error", source: source, address: address.toString(), size: size, error: String(error)});
    }
  }
}

function hookExport(name, callbacks) {
  let target = null;
  try {
    target = Module.findExportByName(null, name);
  } catch (error) {}
  if (target === null) {
    try {
      for (const module of Process.enumerateModules()) {
        if (!/libc\.so|libz\.so|linker64|linker$|libart(\.base)?\.so/.test(module.name)) continue;
        const item = module.enumerateExports().find(exported => exported.name === name);
        if (item) { target = item.address; break; }
      }
    } catch (error) {}
  }
  if (target === null) {
    report({type: "hook_missing", name: name});
    return;
  }
  try {
    Interceptor.attach(target, callbacks);
    report({type: "hook_installed", name: name, address: target.toString()});
  } catch (error) {
    report({type: "hook_error", name: name, address: target.toString(), error: String(error)});
  }
}

function hookExportAliases(names, callbacks) {
  for (const name of names) {
    let target = null;
    try {
      for (const module of Process.enumerateModules()) {
        if (!/libc\.so|libz\.so|linker64|linker$/.test(module.name)) continue;
        const item = module.enumerateExports().find(exported => exported.name === name);
        if (item) { target = item.address; break; }
      }
    } catch (error) {}
    if (target === null) continue;
    try {
      Interceptor.attach(target, callbacks);
      report({type: "hook_installed", name: name, address: target.toString()});
    } catch (error) {
      report({type: "hook_error", name: name, address: target.toString(), error: String(error)});
    }
    return;
  }
  report({type: "hook_missing", name: names.join("|"), aliases: true});
}

function hookDlopen(name) {
  hookExport(name, {
    onEnter(args) {
      try {
        this.path = args[0].isNull() ? "" : args[0].readCString();
      } catch (error) { this.path = ""; }
    },
    onLeave(retval) {
      report({type: "dlopen", name: name, path: this.path || "", result: retval.toString()});
    }
  });
}

function hookOpen(name) {
  hookExport(name, {
    onEnter(args) {
      try {
        this.path = args[0].isNull() ? "" : args[0].readCString();
      } catch (error) { this.path = ""; }
    },
    onLeave(retval) {
      if (this.path && /dex|jiagu|jgob|fsgk|oab|enc|base\.apk|vdex|odex/i.test(this.path)) {
        report({type: "open", name: name, path: this.path, fd: retval.toInt32()});
      }
    }
  });
}

function hookRead(name) {
  hookExport(name, {
    onEnter(args) {
      this.fd = args[0].toInt32();
      this.buffer = args[1];
      this.requested = args[2].toUInt32();
      this.source = name + " fd=" + this.fd;
    },
    onLeave(retval) {
      const count = retval.toInt32();
      if (count > 0 && count <= 128 * 1024 * 1024 && this.buffer) {
        scanBuffer(this.buffer, Math.min(count, 16 * 1024 * 1024), this.source);
      }
    }
  });
}

function hookPread(name) {
  hookExport(name, {
    onEnter(args) {
      this.fd = args[0].toInt32();
      this.buffer = args[1];
      this.requested = args[2].toUInt32();
      this.source = name + " fd=" + this.fd;
    },
    onLeave(retval) {
      const count = retval.toInt32();
      if (count > 0 && this.buffer) scanBuffer(this.buffer, Math.min(count, 16 * 1024 * 1024), this.source);
    }
  });
}

function hookMmap(name) {
  hookExport(name, {
    onEnter(args) {
      this.length = args[1].toUInt32();
      this.prot = args[2].toInt32();
      this.flags = args[3].toInt32();
      this.fd = args[4].toInt32();
      this.offset = args[5].toUInt64().toString();
    },
    onLeave(retval) {
      if (retval.toString() === "0xffffffffffffffff") return;
      const length = this.length || 0;
      if (length > 0 && length <= 128 * 1024 * 1024) {
        report({type: "mmap", name: name, address: retval.toString(), size: length, prot: this.prot, flags: this.flags, fd: this.fd, offset: this.offset});
        scanBuffer(retval, Math.min(length, 16 * 1024 * 1024), name);
      }
    }
  });
}

function hookMprotect(name) {
  hookExport(name, {
    onEnter(args) {
      this.address = args[0];
      this.length = args[1].toUInt32();
      this.prot = args[2].toInt32();
    },
    onLeave(retval) {
      if (retval.toInt32() === 0 && this.address && this.length > 0 && this.length <= 128 * 1024 * 1024) {
        report({type: "mprotect", name: name, address: this.address.toString(), size: this.length, prot: this.prot});
        scanBuffer(this.address, Math.min(this.length, 16 * 1024 * 1024), name);
      }
    }
  });
}

function hookInflate() {
  hookExport("inflate", {
    onEnter(args) {
      this.stream = args[0];
      this.beforeOut = null;
      this.beforeAvail = 0;
      try {
        this.beforeOut = this.stream.add(16).readPointer();
        this.beforeAvail = this.stream.add(24).readU32();
      } catch (error) {}
    },
    onLeave(retval) {
      if (this.beforeOut === null || this.beforeAvail === 0) return;
      try {
        const afterAvail = this.stream.add(24).readU32();
        const produced = this.beforeAvail >= afterAvail ? this.beforeAvail - afterAvail : 0;
        if (produced > 0) scanBuffer(this.beforeOut, Math.min(produced, 16 * 1024 * 1024), "inflate");
      } catch (error) {
        report({type: "inflate_error", error: String(error)});
      }
    }
  });
}

function hookDexOpenSymbols() {
  for (const module of Process.enumerateModules()) {
    if (!/libart(\.base)?\.so$/.test(module.name)) continue;
    let symbols = [];
    try { symbols = module.enumerateSymbols(); } catch (error) { continue; }
    const candidates = symbols.filter(item => /DexFile|OpenMemory|OpenCommon|RegisterDex|DefineClass/i.test(item.name));
    report({type: "art_symbols", module: module.name, count: candidates.length, symbols: candidates.slice(0, 160).map(item => item.name + " @ " + item.address)});
  }
}

hookExportAliases(["open", "open64", "__open_2", "__open64_2"], {
  onEnter(args) { try { this.path = args[0].readCString(); } catch (error) { this.path = ""; } },
  onLeave(retval) { if (this.path && /dex|jiagu|jgob|fsgk|oab|enc|base\.apk|vdex|odex/i.test(this.path)) report({type: "open", path: this.path, fd: retval.toInt32()}); }
});
hookExportAliases(["openat", "openat64", "__openat_2", "__openat64_2"], {
  onEnter(args) { try { this.path = args[1].readCString(); } catch (error) { this.path = ""; } },
  onLeave(retval) { if (this.path && /dex|jiagu|jgob|fsgk|oab|enc|base\.apk|vdex|odex/i.test(this.path)) report({type: "openat", path: this.path, fd: retval.toInt32()}); }
});
hookExportAliases(["read", "__read_chk"], {
  onEnter(args) { this.buffer = args[1]; this.source = "read"; },
  onLeave(retval) { const count = retval.toInt32(); if (count > 0 && this.buffer) scanBuffer(this.buffer, Math.min(count, 16 * 1024 * 1024), this.source); }
});
hookExportAliases(["pread64", "pread", "__pread64_chk"], {
  onEnter(args) { this.buffer = args[1]; this.source = "pread"; },
  onLeave(retval) { const count = retval.toInt32(); if (count > 0 && this.buffer) scanBuffer(this.buffer, Math.min(count, 16 * 1024 * 1024), this.source); }
});
hookExportAliases(["mmap", "mmap64", "__mmap2"], {
  onEnter(args) { this.length = args[1].toUInt32(); this.prot = args[2].toInt32(); this.flags = args[3].toInt32(); this.fd = args[4].toInt32(); },
  onLeave(retval) { if (retval.toString() !== "0xffffffffffffffff" && this.length > 0 && this.length <= 128 * 1024 * 1024) { report({type: "mmap", address: retval.toString(), size: this.length, prot: this.prot, flags: this.flags, fd: this.fd}); scanBuffer(retval, Math.min(this.length, 16 * 1024 * 1024), "mmap"); } }
});
hookExportAliases(["mprotect"], {
  onEnter(args) { this.address = args[0]; this.length = args[1].toUInt32(); this.prot = args[2].toInt32(); },
  onLeave(retval) { if (retval.toInt32() === 0 && this.address && this.length > 0 && this.length <= 128 * 1024 * 1024) { report({type: "mprotect", address: this.address.toString(), size: this.length, prot: this.prot}); scanBuffer(this.address, Math.min(this.length, 16 * 1024 * 1024), "mprotect"); } }
});
hookInflate();
hookExportAliases(["dlopen"], { onEnter(args) { try { this.path = args[0].readCString(); } catch (error) { this.path = ""; } }, onLeave(retval) { report({type: "dlopen", path: this.path || "", result: retval.toString()}); } });
hookExportAliases(["android_dlopen_ext", "__loader_dlopen"], { onEnter(args) { try { this.path = args[0].readCString(); } catch (error) { this.path = ""; } }, onLeave(retval) { report({type: "android_dlopen_ext", path: this.path || "", result: retval.toString()}); } });
hookExportAliases(["memfd_create"], {
  onEnter(args) {
    try { this.name = args[0].readCString(); } catch (error) { this.name = ""; }
  },
  onLeave(retval) { report({type: "memfd_create", name: this.name || "", fd: retval.toInt32()}); }
});
// ART symbol enumeration is diagnostic only. Intercepting ClassLinker methods
// on this Android image can disturb startup before the target loader runs.
hookDexOpenSymbols();
report({type: "trace_started", modules: Process.enumerateModules().map(item => item.name).filter(name => /jiagu|yiqi|art|zlib|c\.so/i.test(name))});
"""


def handle_message(message: dict[str, Any], data: bytes | None, output: Path, records: list[CaptureRecord]) -> None:
    if message.get("type") == "error":
        (output / "frida-errors.log").open("a", encoding="utf-8").write(json.dumps(message, ensure_ascii=False) + "\n")
        print(json.dumps(message, ensure_ascii=False), flush=True)
        return
    payload = message.get("payload")
    if not isinstance(payload, dict):
        return
    event_path = output / "events.jsonl"
    with event_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    if payload.get("type") != "dex" or data is None:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return
    digest = hashlib.sha256(data).hexdigest()
    existing = next((item for item in records if item.sha256 == digest), None)
    if existing is not None:
        print(json.dumps({"duplicate": asdict(existing), "source": payload.get("source")}, ensure_ascii=False), flush=True)
        return
    target = output / f"capture-{len(records):03d}-{digest[:16]}.dex"
    target.write_bytes(data)
    record = CaptureRecord(
        str(target.resolve()), str(payload.get("source", "unknown")),
        str(payload.get("address", "")), len(data), int(payload.get("class_defs", 0)), digest,
    )
    records.append(record)
    print(json.dumps(asdict(record), ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="早期追踪 Android Native 加载链并捕获运行时 DEX")
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--host", default="127.0.0.1:27042")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frida = load_frida()
    device = frida.get_device_manager().add_remote_device(args.host)
    target_pid = device.spawn([args.package])
    session = device.attach(target_pid)
    records: list[CaptureRecord] = []

    def on_message(message: dict[str, Any], data: bytes | None) -> None:
        handle_message(message, data, args.output, records)

    script = session.create_script(javascript())
    script.on("message", on_message)
    script.load()
    device.resume(target_pid)
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        time.sleep(0.25)
    session.detach()
    (args.output / "capture-index.json").write_text(
        json.dumps([asdict(item) for item in records], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"captured": len(records), "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0 if records else 6


if __name__ == "__main__":
    raise SystemExit(main())
