from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="枚举 Android 运行时 DexFile 方法")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--host", default="127.0.0.1:27042")
    parser.add_argument("--seconds", type=int, default=3)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python"))
    import frida

    device = frida.get_device_manager().add_remote_device(args.host)
    session = device.attach(args.pid)
    source = r"""
const result = {
  java_defined: typeof Java !== "undefined",
  modules: Process.enumerateModules().map(function (module) { return module.name; })
    .filter(function (name) { return /art|c\.so|jiagu/i.test(name); }),
  exports: {}
};
["libart.so", "libartbase.so", "libc.so", "libjiagu_64.so"].forEach(function (name) {
  try {
    result.exports[name] = Module.enumerateExports(name)
      .filter(function (item) { return /dex|openmemory|loaddex|mmap|openat|dlopen/i.test(item.name); })
      .map(function (item) { return item.type + " " + item.name + " " + item.address; });
  } catch (error) {
    result.exports[name] = String(error);
  }
});
send(result);
"""
    script = session.create_script(source)
    script.on("message", lambda message, data: print(json.dumps(message, ensure_ascii=False)))
    script.load()
    time.sleep(args.seconds)
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
