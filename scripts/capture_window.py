from __future__ import annotations

import argparse
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab


PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 3)]


def capture_window(handle: int) -> Image.Image:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(handle), ctypes.byref(rect)):
        raise OSError("读取窗口尺寸失败")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise ValueError("窗口尺寸无效")

    window_dc = user32.GetWindowDC(wintypes.HWND(handle))
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    previous = gdi32.SelectObject(memory_dc, bitmap)
    try:
        rendered = user32.PrintWindow(wintypes.HWND(handle), memory_dc, PW_RENDERFULLCONTENT)
        if not rendered:
            gdi32.BitBlt(memory_dc, 0, 0, width, height, window_dc, 0, 0, SRCCOPY)
        info = BitmapInfo()
        info.bmiHeader.biSize = ctypes.sizeof(BitmapInfoHeader)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        pixels = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            pixels,
            ctypes.byref(info),
            DIB_RGB_COLORS,
        )
        if lines != height:
            raise OSError("读取窗口像素失败")
        return Image.frombuffer("RGBA", (width, height), pixels, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.SelectObject(memory_dc, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(wintypes.HWND(handle), window_dc)


def capture_screen_window(handle: int) -> Image.Image:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    target = wintypes.HWND(handle)
    previous = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    foreground_thread = user32.GetWindowThreadProcessId(previous, None) if previous else 0
    target_thread = user32.GetWindowThreadProcessId(target, None)
    if foreground_thread:
        user32.AttachThreadInput(current_thread, foreground_thread, True)
    if target_thread:
        user32.AttachThreadInput(current_thread, target_thread, True)
    try:
        user32.ShowWindowAsync(target, SW_RESTORE)
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        user32.SetWindowPos(target, HWND_TOPMOST, 0, 0, 0, 0, flags)
        user32.BringWindowToTop(target)
        user32.SetActiveWindow(target)
        user32.SetForegroundWindow(target)
        user32.SetFocus(target)
        time.sleep(0.12)
        rect = wintypes.RECT()
        if not user32.GetWindowRect(target, ctypes.byref(rect)):
            raise OSError("读取窗口尺寸失败")
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)
        return image.convert("RGB")
    finally:
        user32.SetWindowPos(target, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        if previous and previous != handle:
            user32.SetForegroundWindow(wintypes.HWND(previous))
        if target_thread:
            user32.AttachThreadInput(current_thread, target_thread, False)
        if foreground_thread:
            user32.AttachThreadInput(current_thread, foreground_thread, False)


def main() -> int:
    parser = argparse.ArgumentParser(description="按 Windows 窗口句柄保存截图")
    parser.add_argument("handle", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--crop", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--screen", action="store_true", help="置顶窗口后从屏幕抓取，适用于 GPU 窗口")
    args = parser.parse_args()
    image = capture_screen_window(args.handle) if args.screen else capture_window(args.handle)
    if args.crop:
        x, y, width, height = args.crop
        image = image.crop((x, y, x + width, y + height))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"已保存窗口截图：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
