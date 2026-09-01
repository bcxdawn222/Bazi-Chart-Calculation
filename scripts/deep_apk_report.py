from __future__ import annotations

import argparse
import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ToolOutput:
    command: List[str]
    output: str
    returncode: int


@dataclass
class DeepReport:
    apk: str
    badging: ToolOutput
    manifest_tree: ToolOutput
    signing: ToolOutput


def find_tool(name: str) -> Optional[Path]:
    sdk = Path.home() / "AppData/Local/Android/Sdk"
    candidates = sorted(sdk.glob(f"build-tools/*/{name}"), reverse=True)
    return candidates[0] if candidates else None


def run(command: List[str]) -> ToolOutput:
    logging.info("执行: %s", " ".join(command))
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return ToolOutput(command, completed.stdout + completed.stderr, completed.returncode)


def inspect(apk: Path) -> DeepReport:
    aapt = find_tool("aapt.exe")
    apksigner = find_tool("apksigner.bat")
    missing = ["tool unavailable"]
    badging = run([str(aapt), "dump", "badging", str(apk)]) if aapt else ToolOutput(missing, "aapt.exe not found", 127)
    manifest = run([str(aapt), "dump", "xmltree", str(apk), "AndroidManifest.xml"]) if aapt else ToolOutput(missing, "aapt.exe not found", 127)
    signing = run([str(apksigner), "verify", "--verbose", "--print-certs", str(apk)]) if apksigner else ToolOutput(missing, "apksigner.bat not found", 127)
    return DeepReport(str(apk.resolve()), badging, manifest, signing)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 APK 组件、权限和签名报告")
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/deep-apk-analysis.json"))
    parser.add_argument("--log", type=Path, default=Path("logs/deep-apk-analysis.log"))
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(args.log, encoding="utf-8"), logging.StreamHandler()])
    reports = [inspect(apk) for apk in args.apks]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(report) for report in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("报告已写入: %s", args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
