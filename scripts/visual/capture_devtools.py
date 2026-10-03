"""按窗口句柄抓取微信开发者工具模拟器画面，不依赖 automation 端口。

automation SDK 在本机长期无法连接（见 docs/design-qa.md），
该入口改用 Windows 窗口抓取 + 主题底色定位模拟器区域，
只读取画面，不提交表单、不建立订单、不清理用户缓存。
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_window import capture_screen_window, capture_window  # noqa: E402

LOG_FILE = ROOT / "logs" / "ui-capture-devtools.log"
# 首页主题底色 #100807，开发者工具自身的中性深灰不会命中
THEME_RGB = (16, 8, 7)
THEME_TOLERANCE = 4
MIN_THEME_SAMPLES = 500


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )


def find_devtools_window() -> tuple[int, str]:
    user32 = ctypes.windll.user32
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found: list[tuple[int, str, int]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if "开发者工具" not in title:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        if area <= 0:
            return True
        found.append((hwnd, title, area))
        return True

    user32.EnumWindows(proc_type(callback), 0)
    if not found:
        raise RuntimeError("未找到微信开发者工具窗口；请先用 scripts/open_miniprogram.py 打开工程")
    found.sort(key=lambda item: item[2], reverse=True)
    handle, title, _ = found[0]
    return handle, title


def locate_simulator(image) -> tuple[int, int, int, int]:
    width, height = image.size
    pixels = image.load()
    left, top = width, height
    right = bottom = 0
    samples = 0
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            red, green, blue = pixels[x, y]
            if (
                abs(red - THEME_RGB[0]) <= THEME_TOLERANCE
                and abs(green - THEME_RGB[1]) <= THEME_TOLERANCE
                and abs(blue - THEME_RGB[2]) <= THEME_TOLERANCE
            ):
                samples += 1
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
    if samples < MIN_THEME_SAMPLES:
        raise RuntimeError(
            f"主题像素仅 {samples} 个，模拟器可能白屏或未编译；请查看开发者工具内的报错"
        )
    logging.info("主题像素采样命中 %s 个", samples)
    pad = 6
    return (max(left - pad, 0), max(top - pad, 0), min(right + pad, width), min(bottom + pad, height))


def report_palette(image) -> None:
    pixels = list(image.getdata())
    total = len(pixels)
    targets = {
        "#100807": (16, 8, 7),
        "#f0a886": (240, 168, 134),
        "#f5ede6": (245, 237, 230),
        "#d96b4f": (217, 107, 79),
        "#b84a30": (184, 74, 48),
    }
    for name, target in targets.items():
        hit = sum(
            1 for pixel in pixels if all(abs(a - b) <= 26 for a, b in zip(pixel, target))
        )
        logging.info("参考色 %s 占比 %.2f%%", name, hit / total * 100)
    white = sum(1 for pixel in pixels if min(pixel) > 235)
    ratio = white / total * 100
    logging.info("接近白色占比 %.2f%%", ratio)
    if ratio > 60:
        raise RuntimeError("画面接近全白，判定为白屏")


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取开发者工具模拟器画面")
    parser.add_argument("output", type=Path, help="裁剪后的模拟器画面保存路径")
    parser.add_argument("--full", type=Path, help="同时保存整窗画面")
    parser.add_argument(
        "--print-window",
        action="store_true",
        help="使用 PrintWindow 而非置顶屏幕抓取；GPU 窗口通常需要默认的屏幕抓取",
    )
    args = parser.parse_args()
    configure_logging()

    handle, title = find_devtools_window()
    logging.info("窗口 hwnd=%s title=%s", handle, title)
    image = capture_window(handle) if args.print_window else capture_screen_window(handle)
    logging.info("整窗尺寸 %sx%s", image.size[0], image.size[1])
    if args.full:
        args.full.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.full)
        logging.info("已保存整窗画面：%s", args.full.resolve())

    box = locate_simulator(image)
    logging.info("模拟器区域 %s", box)
    crop = image.crop(box)
    report_palette(crop)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    crop.save(args.output)
    logging.info("已保存模拟器画面：%s 尺寸=%sx%s", args.output.resolve(), crop.size[0], crop.size[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
