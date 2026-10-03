from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class StyleCheck:
    file_count: int
    compiler: Path


def find_compiler(kind: str = "WXSS") -> Path:
    configured = os.environ.get(f"{kind}_COMPILER")
    executable = "wcsc.exe" if kind == "WXSS" else "wcc.exe"
    candidates = [
        Path(configured) if configured else None,
        Path(r"D:\微信web开发者工具\code\package.nw\node_modules\wcc-exec") / executable,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"未找到微信 {kind} 编译器，请通过 {kind}_COMPILER 指定 {executable}")


def check_wxss(project: Path, pages: Sequence[str]) -> StyleCheck:
    compiler = find_compiler()
    roots = ["app.wxss", *pages]
    all_styles = sorted(path.relative_to(project).as_posix() for path in project.rglob("*.wxss"))
    imported = [name for name in all_styles if name not in roots]
    with tempfile.TemporaryDirectory(prefix="wxss-check-") as temporary:
        output = Path(temporary) / "compiled.js"
        completed = subprocess.run(
            [str(compiler), "-pc", str(len(roots)), "-o", str(output), *roots, *imported],
            cwd=project, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, check=False,
        )
        diagnostics = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0 or "unexpected token" in diagnostics.lower():
            raise RuntimeError(f"微信样式编译失败（exit={completed.returncode}）：\n{diagnostics}")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("微信样式编译器没有生成有效输出")
    return StyleCheck(file_count=len(all_styles), compiler=compiler)


def check_wxml(project: Path) -> StyleCheck:
    compiler = find_compiler("WXML")
    files = sorted(path.relative_to(project).as_posix() for path in project.rglob("*.wxml"))
    with tempfile.TemporaryDirectory(prefix="wxml-check-") as temporary:
        output = Path(temporary) / "compiled.js"
        completed = subprocess.run(
            [str(compiler), "-o", str(output), *files],
            cwd=project, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, check=False,
        )
        diagnostics = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise RuntimeError(f"微信模板编译失败（exit={completed.returncode}）：\n{diagnostics}")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("微信模板编译器没有生成有效输出")
    return StyleCheck(file_count=len(files), compiler=compiler)


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="wxss-regression-") as temporary:
        project = Path(temporary)
        style = project / "app.wxss"
        style.write_text(".motion-paused * { animation-play-state: paused; }", encoding="utf-8")
        try:
            check_wxss(project, [])
        except RuntimeError as error:
            if "unexpected token" not in str(error):
                raise
        else:
            raise AssertionError("微信编译器未识别已知的不兼容选择器")
        style.write_text(".motion-paused view { animation-play-state: paused; }", encoding="utf-8")
        check_wxss(project, [])
    logging.info("选择器回归通过：拒绝通配符，允许显式元素选择器")


def main() -> int:
    parser = argparse.ArgumentParser(description="使用微信本机编译器检查 WXSS 和 WXML")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    (ROOT / "logs").mkdir(exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers: list[logging.Handler] = [
        logging.FileHandler(ROOT / "logs" / "wxss-compile.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers)
    project = ROOT / "miniprogram"
    pages = sorted(path.with_suffix(".wxss").relative_to(project).as_posix()
                   for path in (project / "pages").rglob("*.wxml"))
    try:
        if args.self_test:
            self_test()
        result = check_wxss(project, pages)
        templates = check_wxml(project)
    except (OSError, RuntimeError, AssertionError, subprocess.TimeoutExpired) as error:
        logging.error("%s", error)
        return 1
    logging.info("微信编译器通过：%s 个 WXSS 文件；编译器：%s", result.file_count, result.compiler)
    logging.info("微信模板编译通过：%s 个 WXML 文件", templates.file_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
