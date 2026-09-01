from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


ANDROID_NS = "http://schemas.android.com/apk/res/android"
URL_RE = re.compile(r"https?://[^\"'\s<>]+")
PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", re.MULTILINE)


@dataclass
class DexSummary:
    dex: str
    input_path: str
    sha256: str
    size: int
    class_defs: int
    java_files: int
    package_count: int
    packages: list[str] = field(default_factory=list)
    yiqi_classes: list[str] = field(default_factory=list)


@dataclass
class ManifestSummary:
    package_name: str
    application: str
    activities: list[str]
    services: list[str]
    providers: list[str]
    receivers: list[str]
    launch_components: list[str]


@dataclass
class Evidence:
    urls: list[str]
    webview_files: list[str]
    database_files: list[str]
    key_interface_hits: list[str]
    native_libraries: list[str]
    native_evidence_path: str


@dataclass
class Report:
    sample_path: str
    sample_sha256: str
    capture_index: str
    recovered_path: str
    manifest: ManifestSummary
    dex: list[DexSummary]
    evidence: Evidence
    source_roots: list[str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_capture_index(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def names_from_manifest(root: ET.Element, tag: str) -> list[str]:
    values: list[str] = []
    for item in root.findall(tag):
        name = item.attrib.get(f"{{{ANDROID_NS}}}name", "")
        if name:
            values.append(name)
    return sorted(set(values))


def parse_manifest(path: Path) -> ManifestSummary:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    activities = names_from_manifest(root, "application/activity")
    services = names_from_manifest(root, "application/service")
    providers = names_from_manifest(root, "application/provider")
    receivers = names_from_manifest(root, "application/receiver")
    launches: list[str] = []
    for activity in root.findall("application/activity"):
        for intent in activity.findall("intent-filter"):
            actions = [node.attrib.get(f"{{{ANDROID_NS}}}name", "") for node in intent.findall("action")]
            categories = [node.attrib.get(f"{{{ANDROID_NS}}}name", "") for node in intent.findall("category")]
            if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in categories:
                launches.append(activity.attrib.get(f"{{{ANDROID_NS}}}name", ""))
    app = root.find("application")
    application = "" if app is None else app.attrib.get(f"{{{ANDROID_NS}}}name", "")
    return ManifestSummary(
        root.attrib.get("package", ""), application, activities, services, providers, receivers, sorted(set(launches))
    )


def source_files(root: Path) -> Iterable[Path]:
    return root.rglob("*.java")


def class_name(path: Path, package: str) -> str:
    return f"{package}.{path.stem}" if package else path.stem


def summarize_dex(recovered: Path, captures: list[dict[str, object]]) -> list[DexSummary]:
    result: list[DexSummary] = []
    for index, record in enumerate(captures):
        input_path = Path(str(record["path"]))
        source_root = recovered / "java" / f"dex-{index:02d}" / "sources"
        packages: set[str] = set()
        yiqi: list[str] = []
        java_count = 0
        for source in source_files(source_root):
            java_count += 1
            text = source.read_text(encoding="utf-8", errors="replace")
            match = PACKAGE_RE.search(text)
            package = match.group(1) if match else ""
            if package:
                packages.add(package)
                name = class_name(source, package)
                if name.startswith("yiqi.bazi"):
                    yiqi.append(name)
        result.append(DexSummary(
            f"dex-{index:02d}", str(input_path.resolve()), str(record["sha256"]), int(record["size"]),
            int(record["class_defs"]), java_count, len(packages), sorted(packages), sorted(yiqi),
        ))
    return result


def collect_evidence(recovered: Path) -> Evidence:
    urls: set[str] = set()
    webview: set[str] = set()
    database: set[str] = set()
    key_hits: set[str] = set()
    markers = ("GetKey", "GetMasterPassword", "GetDecryptionPassword", "GetRsaPrivate", "MasterPassword", "RSA", "JNI_OnLoad")
    for source in source_files(recovered / "java"):
        text = source.read_text(encoding="utf-8", errors="replace")
        urls.update(URL_RE.findall(text))
        if re.search(r"WebView|loadUrl\s*\(|evaluateJavascript", text):
            webview.add(str(source.resolve()))
        if re.search(r"SQLite|RoomDatabase|SQLiteOpenHelper|\.sqlite|\.db\b", text, re.IGNORECASE):
            database.add(str(source.resolve()))
        for marker in markers:
            if marker in text:
                key_hits.add(f"{marker}: {source.resolve()}")
    native_files = sorted(str(path.resolve()) for path in (recovered / "native").glob("*.so"))
    native_evidence = recovered / "native-evidence.txt"
    if native_evidence.exists():
        text = native_evidence.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker in text:
                key_hits.add(f"{marker}: {native_evidence.resolve()}")
    return Evidence(sorted(urls), sorted(webview), sorted(database), sorted(key_hits), native_files, str(native_evidence.resolve()))


def markdown(report: Report, output: Path) -> None:
    manifest = report.manifest
    business = [item for item in report.dex if item.yiqi_classes]
    lines = [
        "# base.apk 运行时 DEX 与源码恢复报告",
        "",
        "## 样本与结论",
        "",
        f"- 原始 APK：`{report.sample_path}`",
        f"- SHA-256：`{report.sample_sha256}`",
        f"- 运行时捕获清单：`{report.capture_index}`",
        f"- 恢复目录：`{report.recovered_path}`",
        f"- Manifest 包名：`{manifest.package_name}`",
        f"- 含 `yiqi.bazi` 业务类的 DEX：{', '.join(item.dex for item in business) or '未发现'}",
        "",
        "直接证据表明：主样本的隐藏 DEX 已在 ART `RegisterDexFileLocked` 注册点导出；当前源码扫描直接命中 `yiqi.bazi` 包的 DEX 是 `dex-02` 和 `dex-05`。其他 DEX 保留为第三方或辅助代码候选，不把它们直接归类为业务源码。JADX 对部分 DEX 返回 1，但仍生成了可检索 Java 源码，具体状态以 `source-recovery.json` 为准。",
        "",
        "## DEX 清单",
        "",
        "| DEX | 大小 | class_defs | Java 文件 | yiqi.bazi 类 | SHA-256 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in report.dex:
        lines.append(f"| `{item.dex}` | {item.size:,} | {item.class_defs} | {item.java_files} | {len(item.yiqi_classes)} | `{item.sha256}` |")
    lines.extend([
        "",
        "## Manifest 入口",
        "",
        f"- Application：`{manifest.application}`",
        f"- Launcher：{', '.join(f'`{x}`' for x in manifest.launch_components) or '未解析到'}",
        f"- Activity：{len(manifest.activities)} 个",
        f"- Service：{len(manifest.services)} 个",
        f"- Provider：{len(manifest.providers)} 个",
        f"- Receiver：{len(manifest.receivers)} 个",
        "",
        "## 业务类与源码",
        "",
    ])
    for item in business:
        lines.append(f"- `{item.dex}` 源码目录：`{(Path(report.recovered_path) / 'java' / item.dex / 'sources').resolve()}`")
        lines.append(f"  - 业务类示例：{', '.join(f'`{x}`' for x in item.yiqi_classes[:20])}")
    lines.extend(["", "## 接口、WebView 与本地数据", ""])
    lines.append("- 静态 URL：")
    lines.extend(f"  - `{url}`" for url in report.evidence.urls[:200])
    lines.append("- WebView/网页加载相关源码文件：")
    lines.extend(f"  - `{path}`" for path in report.evidence.webview_files[:80])
    lines.append("- 数据库/SQLite 相关源码文件：")
    lines.extend(f"  - `{path}`" for path in report.evidence.database_files[:80])
    lines.extend(["", "## Native 关联", "", f"- Native 证据：`{report.evidence.native_evidence_path}`"])
    lines.extend(f"- `{path}`" for path in report.evidence.native_libraries)
    lines.append("- 关键接口/符号命中：")
    lines.extend(f"  - `{hit}`" for hit in report.evidence.key_interface_hits)
    lines.extend(["", "## 说明", "", "- `dex-00` 是 4-class 壳 DEX；`dex-01` 主要是 `com.jg.ids` 辅助库；`dex-02` 和 `dex-05` 直接包含 `yiqi.bazi` 业务包，其余 DEX 当前按包名和类名证据归为第三方或辅助代码候选。", "- Java 源码是 JADX 从运行时 DEX 生成的恢复结果，不等同于原始工程源码；少数类可能存在反编译错误。", "- `base1.apk` 的源码仍保存在独立目录，未作为主样本源码混入。", ""])
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总 base.apk 运行时 DEX 与恢复源码证据")
    parser.add_argument("--recovered", required=True, type=Path)
    parser.add_argument("--capture-index", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    args = parser.parse_args()
    capture = read_capture_index(args.capture_index)
    manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))
    sample = Path(str(manifest_data["sample_path"]))
    report = Report(
        str(sample.resolve()), sha256_file(sample), str(args.capture_index.resolve()), str(args.recovered.resolve()),
        parse_manifest(args.recovered / "resources" / "AndroidManifest.xml"),
        summarize_dex(args.recovered, capture), collect_evidence(args.recovered),
        [str((args.recovered / "java" / f"dex-{index:02d}" / "sources").resolve()) for index in range(len(capture))],
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown(report, args.markdown)
    print(json.dumps({"json": str(args.json.resolve()), "markdown": str(args.markdown.resolve()), "business_dex": [x.dex for x in report.dex if x.yiqi_classes]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
