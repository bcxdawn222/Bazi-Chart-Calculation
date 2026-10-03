from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CommandResult:
    code: int
    output: str


def run_command(arguments: list[str], timeout: int) -> CommandResult:
    # A Windows batch child can retain stdout after its parent exits.
    # A file-backed stream allows a real deadline without waiting on that pipe.
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            arguments, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=10, check=False,
                )
            else:
                process.kill()
            process.wait(timeout=10)
            code = 124
        output.seek(0)
        text = output.read().decode("utf-8", errors="replace")
    logging.info("exit=%s\n%s", code, text)
    return CommandResult(code, text)


def cli_succeeded(result: CommandResult) -> bool:
    errors = ("#initialize-error", "wait ide port timeout", "[error]")
    return result.code == 0 and not any(marker in result.output.lower() for marker in errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="读取微信模拟器画面，不提交业务数据")
    parser.add_argument("--restart-ide", action="store_true")
    parser.add_argument("--connect-only", action="store_true")
    parser.add_argument("--open-only", action="store_true", help="只通过微信 CLI 打开当前工程")
    parser.add_argument("--trust-project", action="store_true", help="信任当前已审阅的本地工程")
    parser.add_argument("--diagnose", action="store_true", help="只读取模拟器系统和当前页面信息")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--timeout", type=int, default=130, help="画面采集的等待秒数")
    args = parser.parse_args()
    if args.timeout < 5:
        parser.error("--timeout 不能小于 5 秒")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "logs" / ("ui-capture-self-test.log" if args.self_test else "ui-capture.log"),
        encoding="utf-8",
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.self_test:
        normal = run_command([sys.executable, "-c", "print('ok')"], 5)
        reported_error = run_command(
            [sys.executable, "-c", "print('#initialize-error: wait IDE port timeout')"], 5,
        )
        timed_out = run_command([sys.executable, "-c", "import time; time.sleep(10)"], 1)
        assert cli_succeeded(normal)
        assert not cli_succeeded(reported_error)
        assert timed_out.code == 124
        print("采集脚本自检通过：正常退出、零退出码错误、超时终止。", flush=True)
        return 0
    cli = os.environ.get("WECHAT_CLI", "D:/微信web开发者工具/cli.bat")
    prefix = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", cli]
    if args.open_only:
        opened = run_command([*prefix, "open", "--project", str(ROOT / "miniprogram")], 60)
        print(opened.output, flush=True)
        return 0 if cli_succeeded(opened) else (opened.code or 1)
    if args.restart_ide:
        stopped = run_command([*prefix, "quit"], 30)
        if not cli_succeeded(stopped):
            print("退出开发者工具未成功，停止本次采集。", flush=True)
            return stopped.code or 1
    if not args.connect_only:
        trust_args = ["--trust-project"] if args.trust_project else []
        started = run_command(
            [*prefix, "auto", "--project", str(ROOT / "miniprogram"),
             "--auto-port", "9420", *trust_args],
            60,
        )
        if not cli_succeeded(started):
            print("微信 CLI 未启动自动化：" + started.output, flush=True)
            return started.code or 1
    os.environ["UI_CAPTURE_TIMEOUT_SECONDS"] = str(args.timeout)
    os.environ["UI_CAPTURE_DIAGNOSE"] = "1" if args.diagnose else "0"
    completed = run_command(
        [os.environ.get("NODE_EXE", "node"), str(Path(__file__).with_suffix(".mjs"))],
        args.timeout + 15,
    )
    print(completed.output, flush=True)
    return completed.code


if __name__ == "__main__":
    raise SystemExit(main())
