from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def load_frida() -> Any:
    tool_root = Path(__file__).resolve().parents[1] / ".tools" / "reverse" / "python"
    sys.path.insert(0, str(tool_root))
    import frida

    return frida


def javascript() -> str:
    return r"""
function inspectClassLoaders() {
  if (typeof Java === "undefined") {
    send({type: "java_not_ready"});
    return;
  }
  if (!Java.available) {
    send({type: "java_unavailable"});
    return;
  }
  const run = function () {
    const result = {type: "classloaders", loaders: [], classes: []};
    const names = Java.enumerateLoadedClassesSync();
    result.classes = names.filter(function (name) {
      return /^(yiqi\.|com\.stub\.|com\.tianyu\.|com\.bun\.)/.test(name);
    }).sort();

    function readField(object, name) {
      let current = object.getClass();
      while (current !== null) {
        try {
          const field = current.getDeclaredField(name);
          field.setAccessible(true);
          return field.get(object);
        } catch (error) {
          current = current.getSuperclass();
        }
      }
      return null;
    }

    function inspectLoader(loader) {
      const item = {loader: String(loader), dex: [], error: ""};
      try {
        const pathList = readField(loader, "pathList");
        const elements = pathList === null ? null : readField(pathList, "dexElements");
        if (elements !== null) {
          for (let index = 0; index < elements.length; index += 1) {
            const element = elements[index];
            const dexFile = readField(element, "dexFile");
            if (dexFile !== null) {
              let name = "";
              try { name = String(dexFile.getName()); } catch (error) { name = String(error); }
              item.dex.push({index: index, name: name, class: String(dexFile.$className)});
            }
          }
        }
      } catch (error) {
        item.error = String(error);
      }
      return item;
    }

    Java.enumerateClassLoaders({
      onMatch: function (loader) { result.loaders.push(inspectLoader(loader)); },
      onComplete: function () {
        result.loaders.sort(function (left, right) { return left.loader.localeCompare(right.loader); });
        send(result);
      }
    });
  };
  try {
    if (typeof Java.performNow === "function") {
      Java.performNow(run);
    } else {
      Java.perform(run);
    }
  } catch (error) {
    send({type: "java_inspect_error", error: String(error)});
  }
}

send({type: "script_loaded"});
let attempts = 0;
const javaPoll = setInterval(function () {
  attempts += 1;
  if (typeof Java !== "undefined") {
    clearInterval(javaPoll);
    inspectClassLoaders();
    setInterval(inspectClassLoaders, 3000);
  } else if (attempts > 100) {
    clearInterval(javaPoll);
  }
}, 50);
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="枚举 Android 进程运行时 ClassLoader 和 DexFile")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--package")
    parser.add_argument("--host", default="127.0.0.1:27042")
    parser.add_argument("--seconds", type=int, default=12)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.pid is None and args.package is None:
        parser.error("--pid or --package is required")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frida = load_frida()
    device = frida.get_device_manager().add_remote_device(args.host)
    spawned = args.package is not None
    target_pid = device.spawn([args.package]) if spawned else args.pid
    session = device.attach(target_pid)
    messages: list[dict[str, Any]] = []

    def on_message(message: dict[str, Any], data: bytes | None) -> None:
        if message.get("type") != "send":
            messages.append(message)
            print(json.dumps(message, ensure_ascii=False), flush=True)
            return
        payload = message.get("payload")
        if isinstance(payload, dict):
            messages.append(payload)
            print(json.dumps(payload, ensure_ascii=False), flush=True)

    script = session.create_script(javascript())
    script.on("message", on_message)
    script.load()
    if spawned:
        device.resume(target_pid)
    time.sleep(args.seconds)
    session.detach()
    args.output.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
