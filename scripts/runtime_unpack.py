from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from scan_android_memory import dump_private_mappings, scan_process


@dataclass
class CommandResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    raw_stdout: bytes = b""


@dataclass
class StepResult:
    name: str
    status: str
    returncode: int
    detail: str
    log_path: str


@dataclass
class Artifact:
    path: str
    kind: str
    size: int
    sha256: str
    source: str


@dataclass
class TaskManifest:
    task_id: str
    sample_path: str
    sample_sha256: str
    package_name: str
    avd_id: str
    device_serial: str = ""
    android_release: str = ""
    abi: str = ""
    status: str = "running"
    steps: List[StepResult] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sdk_tool(name: str) -> Path:
    root = Path.home() / "AppData/Local/Android/Sdk"
    path = root / ("emulator" if name == "emulator" else "platform-tools") / (name + (".exe" if os.name == "nt" else ""))
    if not path.exists():
        raise FileNotFoundError(f"Android SDK tool missing: {path}")
    return path


def run(command: List[str], timeout: int = 60, binary: bool = False) -> CommandResult:
    logging.info("执行: %s", " ".join(command))
    completed = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    if binary:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        return CommandResult(command, completed.returncode, stdout, stderr, completed.stdout)
    else:
        stdout = completed.stdout.decode("utf-8", errors="replace") if isinstance(completed.stdout, bytes) else completed.stdout
        stderr = completed.stderr.decode("utf-8", errors="replace") if isinstance(completed.stderr, bytes) else completed.stderr
    return CommandResult(command, completed.returncode, stdout, stderr)


def adb(adb_path: Path, serial: str, args: List[str], timeout: int = 60, binary: bool = False) -> CommandResult:
    command = [str(adb_path)] + (["-s", serial] if serial else []) + args
    return run(command, timeout=timeout, binary=binary)


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="replace")
    return path


def add_artifact(manifest: TaskManifest, path: Path, kind: str, source: str) -> None:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"artifact missing: {path}")
    manifest.artifacts.append(Artifact(str(path.resolve()), kind, path.stat().st_size, sha256_file(path), source))


def device_serial(adb_path: Path) -> str:
    result = run([str(adb_path), "devices"], timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "adb devices failed")
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return ""


def wait_boot(adb_path: Path, serial: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = adb(adb_path, serial, ["shell", "getprop", "sys.boot_completed"], timeout=20)
        if result.returncode == 0 and result.stdout.strip() == "1":
            return
        time.sleep(3)
    raise TimeoutError("Android boot did not complete before timeout")


def start_avd(emulator: Path, avd: str, output: Path, memory_mb: int, headless: bool) -> subprocess.Popen[bytes]:
    log_file = (output / "emulator.log").open("wb")
    command = [str(emulator), "-avd", avd, "-no-snapshot", "-no-boot-anim", "-memory", str(memory_mb)]
    if headless:
        command.extend(["-no-window", "-no-audio", "-gpu", "swiftshader_indirect"])
    logging.info("启动 AVD: %s", " ".join(command))
    return subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)


def capture_process(adb_path: Path, serial: str, package: str, output: Path) -> tuple[str, str, Optional[Path]]:
    pid_result = adb(adb_path, serial, ["shell", "pidof", package], timeout=20)
    pid = pid_result.stdout.strip().split()[0] if pid_result.returncode == 0 and pid_result.stdout.strip() else ""
    maps = ""
    maps_error: Optional[Path] = None
    if pid:
        maps_result = adb(adb_path, serial, ["shell", "cat", f"/proc/{pid}/maps"], timeout=30)
        maps = maps_result.stdout
        if maps_result.returncode == 0 and maps.strip():
            write_text(output / "proc" / f"{pid}.maps", maps)
        else:
            maps_error = write_text(output / "proc" / f"{pid}.maps.error.txt", maps_result.stderr.strip() or "maps unavailable")
        write_text(output / "proc" / f"{pid}.cmdline", adb(adb_path, serial, ["shell", "cat", f"/proc/{pid}/cmdline"], timeout=20).stdout)
    return pid, maps, maps_error


def dump_run_as_files(adb_path: Path, serial: str, package: str, output: Path, manifest: TaskManifest) -> None:
    listing = adb(adb_path, serial, ["exec-out", "run-as", package, "find", ".", "-type", "f"], timeout=30)
    listing_text = (listing.stdout + "\n" + listing.stderr).strip()
    if listing.returncode != 0 or listing_text.startswith("run-as:") or "package not debuggable" in listing_text:
        raise RuntimeError(f"run-as file listing failed: {listing.stderr.strip()}")
    files = [line.strip() for line in listing.stdout.splitlines() if line.strip()]
    if not files:
        raise RuntimeError("run-as returned no private files")
    for relative in files:
        if ".." in Path(relative).parts:
            raise RuntimeError(f"unsafe private path: {relative}")
        target = output / "private" / relative.lstrip("./").replace("/", "_")
        result = adb(adb_path, serial, ["exec-out", "run-as", package, "cat", relative], timeout=60, binary=True)
        if result.returncode != 0:
            logging.warning("跳过无法读取的私有文件 %s: %s", relative, result.stderr.strip())
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.raw_stdout)
        add_artifact(manifest, target, "private_file", f"run-as:{relative}")


def remote_target(remote_path: str, output: Path, prefix: str) -> Path:
    safe_name = remote_path.lstrip("/").replace("/", "__").replace(":", "_")
    return output / prefix / safe_name


def dump_remote_file(adb_path: Path, serial: str, remote_path: str, output: Path, manifest: TaskManifest, kind: str, source: str) -> bool:
    if any(item.source == source for item in manifest.artifacts):
        return True
    result = adb(adb_path, serial, ["exec-out", "cat", remote_path], timeout=90, binary=True)
    if result.returncode != 0:
        logging.warning("远端文件读取失败 %s: %s", remote_path, result.stderr.strip())
        return False
    target = remote_target(remote_path, output, "runtime")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.raw_stdout)
    add_artifact(manifest, target, kind, source)
    return True


def dump_root_private_files(adb_path: Path, serial: str, package: str, output: Path, manifest: TaskManifest) -> int:
    private_root = f"/data/data/{package}"
    listing = adb(adb_path, serial, ["shell", "find", private_root, "-type", "f"], timeout=30)
    if listing.returncode != 0:
        raise RuntimeError(f"root private listing failed: {listing.stderr.strip()}")
    paths = [
        line.strip() for line in listing.stdout.splitlines()
        if line.strip() and (
            f"/{package}/.jiagu/" in line
            or f"/{package}/.oabugaij/" in line
            or line.rstrip() == f"/data/data/{package}/files/jgobfppppp"
            or f"/{package}/app_lib/" in line
        )
    ]
    if not paths:
        raise RuntimeError(f"root payload directories are empty: {private_root}")
    count = 0
    for remote_path in paths:
        if not remote_path.startswith(private_root + "/"):
            raise RuntimeError(f"unexpected private path: {remote_path}")
        suffix = Path(remote_path).suffix.lower()
        kind = "runtime_dex" if suffix == ".dex" else "private_file"
        if dump_remote_file(adb_path, serial, remote_path, output, manifest, kind, f"root:{remote_path}"):
            count += 1
    if count == 0:
        raise RuntimeError(f"root private files were listed but none were readable: {private_root}")
    return count


def mapped_paths(maps: str, package: str) -> List[str]:
    allowed_prefixes = (f"/data/data/{package}/", "/data/app/")
    paths: list[str] = []
    for line in maps.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 6:
            continue
        remote_path = parts[5].removesuffix(" (deleted)")
        if not remote_path.startswith(allowed_prefixes):
            continue
        suffix = Path(remote_path).suffix.lower()
        is_known_payload = suffix in {".dex", ".vdex", ".odex", ".so", ".jiagu"}
        is_deleted_jiagu_payload = remote_path.endswith("/files/jgobfppppp")
        if is_known_payload or "/.jiagu/" in remote_path or is_deleted_jiagu_payload:
            if remote_path not in paths:
                paths.append(remote_path)
    return paths


def dump_mapped_files(adb_path: Path, serial: str, package: str, maps: str, output: Path, manifest: TaskManifest) -> int:
    paths = mapped_paths(maps, package)
    if not paths:
        raise RuntimeError("no readable file paths in process maps")
    count = 0
    for remote_path in paths:
        suffix = Path(remote_path).suffix.lower()
        if suffix == ".dex":
            kind = "runtime_dex"
        elif suffix in {".vdex", ".odex"}:
            kind = "runtime_container"
        elif suffix == ".so":
            kind = "native_library"
        else:
            kind = "mapped_file"
        if dump_remote_file(adb_path, serial, remote_path, output, manifest, kind, f"proc_maps:{remote_path}"):
            count += 1
    if count == 0:
        raise RuntimeError("process maps contained candidate files, but none were readable")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Android APK 运行时脱壳和 DEX 导出任务")
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--package", required=True)
    parser.add_argument("--avd", default="Pixel_6")
    parser.add_argument("--activity", default="")
    parser.add_argument("--output", type=Path, default=Path("artifacts/runtime"))
    parser.add_argument("--boot-timeout", type=int, default=180)
    parser.add_argument("--capture-seconds", type=int, default=12)
    parser.add_argument("--poll-interval", type=float, default=0.2)
    parser.add_argument("--emulator-memory", type=int, default=4096)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--scan-memory", action="store_true")
    parser.add_argument("--memory-scan-limit-mb", type=int, default=256)
    parser.add_argument("--try-adb-root", action="store_true")
    parser.add_argument("--keep-emulator", action="store_true")
    args = parser.parse_args()
    if not args.apk.is_file():
        logging.error("APK 文件不存在: %s", args.apk)
        return 2
    adb_path = sdk_tool("adb")
    emulator_path = sdk_tool("emulator")
    task_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + sha256_file(args.apk)[:12]
    output = args.output / task_id
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "runtime-unpack.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()])
    manifest = TaskManifest(task_id, str(args.apk.resolve()), sha256_file(args.apk), args.package, args.avd)
    emulator_process: Optional[subprocess.Popen[bytes]] = None
    started_here = False
    root_enabled = False

    def step(name: str, action) -> bool:
        try:
            action()
            manifest.steps.append(StepResult(name, "passed", 0, "", str(log_path.resolve())))
            return True
        except (OSError, RuntimeError, TimeoutError) as error:
            logging.exception("步骤失败: %s", name)
            manifest.steps.append(StepResult(name, "failed", 1, str(error), str(log_path.resolve())))
            return False

    try:
        if not step("device", lambda: None):
            manifest.status = "failed_device"
            return 3
        serial = device_serial(adb_path)
        if not serial:
            emulator_process = start_avd(emulator_path, args.avd, output, args.emulator_memory, args.headless)
            started_here = True
            wait_result = run([str(adb_path), "wait-for-device"], timeout=args.boot_timeout)
            if wait_result.returncode != 0:
                raise RuntimeError(wait_result.stderr.strip() or "adb wait-for-device failed")
            serial = device_serial(adb_path)
            if not serial:
                raise RuntimeError("ADB device did not appear")
            wait_boot(adb_path, serial, args.boot_timeout)
        manifest.device_serial = serial
        manifest.android_release = adb(adb_path, serial, ["shell", "getprop", "ro.build.version.release"], timeout=20).stdout.strip()
        manifest.abi = adb(adb_path, serial, ["shell", "getprop", "ro.product.cpu.abilist"], timeout=20).stdout.strip()
        write_text(output / "device-info.txt", f"serial={serial}\nrelease={manifest.android_release}\nabi={manifest.abi}\n")
        if args.try_adb_root:
            root_result = adb(adb_path, serial, ["root"], timeout=30)
            if root_result.returncode != 0 or "cannot run as root" in (root_result.stdout + root_result.stderr).lower():
                manifest.steps.append(StepResult("adb_root", "partial", root_result.returncode, root_result.stdout + root_result.stderr, str(log_path.resolve())))
                logging.warning("adb root 未启用: %s", root_result.stdout.strip() or root_result.stderr.strip())
            else:
                time.sleep(3)
                identity = adb(adb_path, serial, ["shell", "id"], timeout=20)
                root_enabled = identity.returncode == 0 and "uid=0" in identity.stdout
                root_status = "passed" if root_enabled else "partial"
                detail = (root_result.stdout + "\n" + identity.stdout + "\n" + identity.stderr).strip()
                manifest.steps.append(StepResult("adb_root", root_status, identity.returncode, detail, str(log_path.resolve())))
                if not root_enabled:
                    logging.warning("adb root 命令已返回，但 shell 身份仍非 root: %s", detail)
        else:
            identity = adb(adb_path, serial, ["shell", "id"], timeout=20)
            root_enabled = identity.returncode == 0 and "uid=0" in identity.stdout
            logging.info("检测已有设备 shell 身份: %s", identity.stdout.strip() or identity.stderr.strip())
        if not step("install", lambda: _install(adb_path, serial, args.apk, args.package)):
            manifest.status = "failed_install"
            return 4
        if not step("clear_logcat", lambda: _clear_logcat(adb_path, serial)):
            manifest.status = "failed_logcat"
            return 5
        if not step("launch", lambda: _launch(adb_path, serial, args.package, args.activity)):
            manifest.status = "failed_launch"
            return 5
        pid = ""
        maps = ""
        maps_error: Optional[Path] = None
        payload_started = False
        last_maps = ""
        next_private_capture = time.monotonic()
        memory_scan_started = False
        launch_time = time.monotonic()
        capture_deadline = time.monotonic() + args.capture_seconds
        while time.monotonic() < capture_deadline:
            candidate_pid, candidate_maps, candidate_error = capture_process(adb_path, serial, args.package, output)
            if candidate_pid:
                pid = candidate_pid
                if candidate_maps:
                    maps = candidate_maps
                maps_error = candidate_error
                map_file = output / "proc" / f"{pid}.maps"
                if map_file.exists() and not any(item.kind == "proc_maps" for item in manifest.artifacts):
                    add_artifact(manifest, map_file, "proc_maps", f"/proc/{pid}/maps")
                if maps_error and not any(item.kind == "proc_maps_error" for item in manifest.artifacts):
                    add_artifact(manifest, maps_error, "proc_maps_error", f"/proc/{pid}/maps")
                if not payload_started:
                    payload_started = True
                    if root_enabled:
                        try:
                            count = dump_root_private_files(adb_path, serial, args.package, output, manifest)
                            manifest.steps.append(StepResult("early_private_files", "passed", 0, f"captured {count} file(s)", str(log_path.resolve())))
                        except RuntimeError as error:
                            logging.warning("早期私有目录导出未完成: %s", error)
                            manifest.steps.append(StepResult("early_private_files", "partial", 1, str(error), str(log_path.resolve())))
                if root_enabled and maps and maps != last_maps:
                    try:
                        count = dump_mapped_files(adb_path, serial, args.package, maps, output, manifest)
                        manifest.steps.append(StepResult("mapped_files_sample", "passed", 0, f"captured {count} file(s)", str(log_path.resolve())))
                    except RuntimeError as error:
                        logging.warning("映射文件采样未完成: %s", error)
                        manifest.steps.append(StepResult("mapped_files_sample", "partial", 1, str(error), str(log_path.resolve())))
                    last_maps = maps
                if root_enabled and time.monotonic() >= next_private_capture:
                    try:
                        count = dump_root_private_files(adb_path, serial, args.package, output, manifest)
                        manifest.steps.append(StepResult("private_files_sample", "passed", 0, f"captured {count} file(s)", str(log_path.resolve())))
                    except RuntimeError as error:
                        logging.warning("私有目录采样未完成: %s", error)
                    next_private_capture = time.monotonic() + 0.8
                if root_enabled and args.scan_memory and not memory_scan_started and maps and time.monotonic() - launch_time >= 1.5:
                    memory_scan_started = True
                    try:
                        fresh_pid, fresh_maps, fresh_error = capture_process(adb_path, serial, args.package, output)
                        if fresh_pid and fresh_maps:
                            pid, maps, maps_error = fresh_pid, fresh_maps, fresh_error
                        memory_output = output / "memory-scan"
                        records = scan_process(
                            Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
                            serial, int(pid), args.package, maps, memory_output, args.memory_scan_limit_mb,
                        )
                        for record in records:
                            add_artifact(manifest, Path(record.path), "runtime_dex_memory", f"/proc/{pid}/mem:{record.address}")
                        mapped_records = dump_private_mappings(
                            Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
                            serial, int(pid), args.package, maps, memory_output,
                        )
                        for record in mapped_records:
                            add_artifact(manifest, Path(record.path), "mapped_private_memory", f"/proc/{pid}/mem:{record.source}:{record.address}")
                        manifest.steps.append(StepResult("memory_scan", "passed" if records else "partial", 0 if records else 6, f"captured {len(records)} DEX file(s)", str(log_path.resolve())))
                    except (OSError, RuntimeError, TimeoutError) as error:
                        logging.warning("进程内存 DEX 扫描失败: %s", error)
                        manifest.steps.append(StepResult("memory_scan", "partial", 1, str(error), str(log_path.resolve())))
            time.sleep(max(args.poll_interval, 0.05))
        if pid and maps:
            latest_maps = write_text(output / "proc" / f"{pid}.latest.maps", maps)
            if not any(item.source == f"/proc/{pid}/maps.latest" for item in manifest.artifacts):
                add_artifact(manifest, latest_maps, "proc_maps_latest", f"/proc/{pid}/maps.latest")
        logcat = adb(adb_path, serial, ["logcat", "-d", "-v", "threadtime"], timeout=60)
        write_text(output / "logcat.txt", logcat.stdout + logcat.stderr)
        if not pid:
            if re.search(r"ABI|native|UnsatisfiedLinkError|FATAL EXCEPTION", logcat.stdout + logcat.stderr, re.I):
                manifest.status = "blocked_abi"
            else:
                manifest.status = "failed_launch"
            raise RuntimeError(f"target process not found; status={manifest.status}")
        map_file = output / "proc" / f"{pid}.maps"
        if map_file.exists() and not any(item.kind == "proc_maps" for item in manifest.artifacts):
            add_artifact(manifest, map_file, "proc_maps", f"/proc/{pid}/maps")
        if maps_error and not any(item.kind == "proc_maps_error" for item in manifest.artifacts):
            add_artifact(manifest, maps_error, "proc_maps_error", f"/proc/{pid}/maps")
        add_artifact(manifest, output / "logcat.txt", "logcat", "adb logcat")
        if not payload_started:
            try:
                dump_run_as_files(adb_path, serial, args.package, output, manifest)
                manifest.steps.append(StepResult("private_files", "passed", 0, "", str(log_path.resolve())))
            except RuntimeError as error:
                logging.warning("私有目录导出未完成: %s", error)
                private_status = "partial"
                if root_enabled:
                    try:
                        count = dump_root_private_files(adb_path, serial, args.package, output, manifest)
                        private_status = "passed"
                        error = RuntimeError(f"run-as unavailable; root export captured {count} file(s)")
                    except RuntimeError as root_error:
                        error = RuntimeError(f"run-as: {error}; root: {root_error}")
                manifest.steps.append(StepResult("private_files", private_status, 0 if private_status == "passed" else 1, str(error), str(log_path.resolve())))
            if root_enabled:
                try:
                    count = dump_mapped_files(adb_path, serial, args.package, maps, output, manifest)
                    manifest.steps.append(StepResult("mapped_files", "passed", 0, f"captured {count} file(s)", str(log_path.resolve())))
                except RuntimeError as error:
                    logging.warning("映射文件导出未完成: %s", error)
                    manifest.steps.append(StepResult("mapped_files", "partial", 1, str(error), str(log_path.resolve())))
        has_payload = any(item.kind in {"runtime_dex", "runtime_container", "native_library", "mapped_file", "private_file"} for item in manifest.artifacts)
        if not has_payload:
            manifest.status = "captured_no_dex"
            raise RuntimeError("process was captured, but no runtime DEX/private payload was found")
        manifest.status = "captured"
        return 0
    except (OSError, RuntimeError, TimeoutError) as error:
        logging.error("运行时任务失败: %s", error)
        if manifest.status == "running":
            manifest.status = "failed"
        return 6
    finally:
        (output / "manifest.json").write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        if started_here and emulator_process and not args.keep_emulator:
            try:
                serial = manifest.device_serial or device_serial(adb_path)
                if serial:
                    adb(adb_path, serial, ["emu", "kill"], timeout=20)
            except (OSError, RuntimeError):
                logging.exception("停止 AVD 失败")


def _install(adb_path: Path, serial: str, apk: Path, package: str) -> None:
    result = adb(adb_path, serial, ["install", "-r", "-d", str(apk)], timeout=180)
    if result.returncode != 0 or "Success" not in result.stdout:
        raise RuntimeError(f"install failed: {result.stdout.strip()} {result.stderr.strip()}")
    package_path = adb(adb_path, serial, ["shell", "pm", "path", package], timeout=20)
    if package_path.returncode != 0:
        raise RuntimeError(f"package path check failed: {package_path.stderr.strip()}")


def _launch(adb_path: Path, serial: str, package: str, activity: str) -> None:
    if activity:
        component = activity if "/" in activity else f"{package}/{activity}"
        result = adb(adb_path, serial, ["shell", "am", "start", "-n", component], timeout=30)
    else:
        result = adb(adb_path, serial, ["shell", "monkey", "-p", package, "1"], timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"launch failed: {result.stdout.strip()} {result.stderr.strip()}")


def _clear_logcat(adb_path: Path, serial: str) -> None:
    result = adb(adb_path, serial, ["logcat", "-c"], timeout=20)
    if result.returncode != 0:
        raise RuntimeError(f"logcat clear failed: {result.stderr.strip()}")


if __name__ == "__main__":
    raise SystemExit(main())
