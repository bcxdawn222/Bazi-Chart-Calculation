from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description="制作参考图与实际截图对照，不生成模拟界面")
    parser.add_argument("implementation", type=Path)
    parser.add_argument("--label", choices=("before", "after"), default="before")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    implementation = args.implementation.resolve()
    if not implementation.is_file():
        raise FileNotFoundError(implementation)
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "logs" / "ui-comparison.log", level=logging.INFO,
        encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s",
    )
    completed = subprocess.run(
        [os.environ.get("NODE_EXE", "node"), str(Path(__file__).with_suffix(".mjs")),
         str(implementation), args.label],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=False,
    )
    logging.info("%s\n%s", completed.stdout, completed.stderr)
    print(completed.stdout)
    if completed.returncode:
        print(completed.stderr, file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
