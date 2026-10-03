from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence, cast

from support.miniprogram_types import AppConfig, SampleResult
from style_checks.wxss import check_wxml, check_wxss


ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM = ROOT / "miniprogram"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "check-miniprogram.log"


@dataclass(frozen=True)
class CheckResult:
    name: str
    detail: str


class WxmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag, attrs

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1] != tag:
            expected = self.stack[-1] if self.stack else "无"
            raise ValueError(f"WXML 结束标签 {tag} 与当前标签 {expected} 不匹配")
        self.stack.pop()

    def ensure_complete(self) -> None:
        if self.stack:
            raise ValueError(f"WXML 标签未闭合：{self.stack[-1]}")


def configure_logging() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


def run_command(args: Sequence[str]) -> str:
    completed = subprocess.run(
        list(args),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        output = (completed.stdout + completed.stderr).strip()
        raise RuntimeError(f"命令执行失败：{' '.join(args)}\n{output}")
    return completed.stdout.strip()


def find_node() -> str:
    candidates = [
        shutil.which("node"),
        os.environ.get("NODE_EXE"),
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise RuntimeError("未找到 node，请安装 Node.js 或通过 NODE_EXE 指定 node.exe")


def load_app_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise ValueError("app.json 缺少 pages 数组")
    return cast(AppConfig, data)


def check_required_files() -> CheckResult:
    required = [
        "app.js", "app.json", "app.wxss", "project.config.json", "sitemap.json",
        "core/calendar.js", "core/solar_terms.js", "core/bazi.js",
        "core/ziwei.js", "core/format.js",
        "core/solar_time.js", "core/bazi_details.js", "core/ziwei_details.js",
        "core/features/fortune.js", "core/features/divination.js",
        "core/features/compatibility.js", "core/features/naming.js",
        "core/api.js", "data/kangxi-strokes.js",
    ]
    missing = [item for item in required if not (MINIPROGRAM / item).is_file()]
    if missing:
        raise FileNotFoundError("缺少小程序文件：" + "、".join(missing))
    return CheckResult("工程文件", f"基础文件 {len(required)} 项齐全")


def check_json_and_routes() -> CheckResult:
    for path in MINIPROGRAM.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    config = load_app_config(MINIPROGRAM / "app.json")
    if not config["pages"] or not all(isinstance(page, str) for page in config["pages"]):
        raise ValueError("app.json pages 内容无效")
    for page in config["pages"]:
        for suffix in (".js", ".json", ".wxml", ".wxss"):
            target = MINIPROGRAM / f"{page}{suffix}"
            if not target.is_file():
                raise FileNotFoundError(f"页面路由缺少文件：{target}")
    return CheckResult("JSON 与路由", f"{len(config['pages'])} 个页面配置完整")


def check_templates() -> CheckResult:
    checked = 0
    for path in MINIPROGRAM.rglob("*.wxml"):
        source = path.read_text(encoding="utf-8")
        if ".join(" in source:
            raise ValueError(f"WXML 中存在不兼容的方法调用：{path}")
        parser = WxmlParser()
        parser.feed(source)
        parser.close()
        parser.ensure_complete()
        checked += 1
    return CheckResult("WXML", f"{checked} 个模板标签结构有效")


def check_javascript() -> CheckResult:
    node = find_node()
    files = sorted(MINIPROGRAM.rglob("*.js")) + sorted((ROOT / "admin").glob("*.js"))
    for path in files:
        run_command((node, "--check", str(path)))
    return CheckResult("JavaScript", f"{len(files)} 个文件通过 node --check")


def check_core_sample() -> CheckResult:
    node = find_node()
    fixture = ROOT / "scripts" / "fixtures" / "miniprogram_core_check.js"
    sample = cast(SampleResult, json.loads(run_command((node, str(fixture)))))
    expected_pillars = ["己巳", "丙子", "丙寅", "甲午"]
    if sample["solar"] != {"year": 1990, "month": 1, "day": 1}:
        raise AssertionError("固定样例日期发生回归")
    if (sample["hour"], sample["minute"]) != (11, 41):
        raise AssertionError("固定样例真太阳时发生回归")
    if sample["correction"] != {
        "longitudeMinutes": -14.4,
        "equationOfTimeMinutes": -3.61,
        "totalCorrectionMinutes": -18.01,
        "crossedDateBoundary": False,
    }:
        raise AssertionError("真太阳时修正明细发生回归")
    if sample["crossDateCorrection"] != {
        "solar": {"year": 1989, "month": 12, "day": 31},
        "totalCorrectionMinutes": -163.61,
        "crossedDateBoundary": True,
    }:
        raise AssertionError("真太阳时跨日处理发生回归")
    if sample["pillars"] != expected_pillars or not all(sample["tenGods"]):
        raise AssertionError("固定样例四柱或十神发生回归")
    if sample["hiddenStemCount"] != 9 or sample["nayinCount"] != 4:
        raise AssertionError("八字藏干或纳音明细发生回归")
    if sample["elementCounts"] != {"wood": 2, "fire": 5, "earth": 4, "metal": 1, "water": 1}:
        raise AssertionError("五行统计发生回归")
    if sample["palaceCount"] != 12 or sample["mainStarCount"] != 14:
        raise AssertionError("紫微十二宫或主星结果不完整")
    if sample["auxiliaryStarCount"] <= 0 or sample["transformationCount"] != 4:
        raise AssertionError("辅星或四化结果不完整")
    if sample["brightnessCount"] != 22 or sample["relatedPalaceCount"] != 12:
        raise AssertionError("紫微亮度或三方四正关系发生回归")
    if not all((sample["bureau"], sample["lifePalace"], sample["ziweiPosition"])):
        raise AssertionError("紫微关键字段为空")
    if sample["analysisCount"] != 5:
        raise AssertionError("解读区域结果不完整")
    if sample["leapRoundTripCases"] <= 0:
        raise AssertionError("没有完成闰月往返检查")
    if sample["boundaryRejectCount"] != 2:
        raise AssertionError("历法边界输入未按预期拒绝")
    if not sample["ziHourDiffers"]:
        raise AssertionError("早晚子时模式没有产生日期边界差异")
    if sample["invalidInputRejectCount"] != 6:
        raise AssertionError("非法日期、时间或经度未按预期拒绝")
    if not sample["unsupportedSolarTermYearRejected"]:
        raise AssertionError("1900 年节气外推未按恢复源码范围拒绝")
    if sample["lifeDaxian"] != "6-15" or sample["ziweiLiunianCount"] != 6:
        raise AssertionError("紫微命宫大限或流年字段发生回归")
    if sample["solarTermBoundaryCount"] != 2 or not sample["dayunVaries"]:
        raise AssertionError("节气切柱或动态起运年龄发生回归")
    if (not sample["resultPageLiunianBound"]
            or not sample["resultPageDetailsBound"]
            or not sample["invalidResultHandled"]
            or not sample["indexFlowValidated"]
            or not sample["featureNavigationValidated"]):
        raise AssertionError("输入提交、错误弹窗或结果页新增字段绑定发生回归")
    if (not sample["dailyFortuneValidated"]
            or not sample["yearFortuneValidated"]
            or not sample["divinationValidated"]
            or not sample["compatibilityValidated"]
            or not sample["namingValidated"]):
        raise AssertionError("红圈功能核心固定样例发生回归")
    return CheckResult(
        "核心样例",
        f"{sample['roundTripCases']} 组常规日期和 {sample['leapRoundTripCases']} 组闰月往返一致；"
        f"四柱 {' '.join(sample['pillars'])}；十二宫完整",
    )


def check_consultation_flow() -> CheckResult:
    node = find_node()
    fixture = ROOT / "scripts" / "fixtures" / "consultation_flow_check.js"
    result = json.loads(run_command((node, str(fixture))))
    if not result.get("validated"):
        raise AssertionError("咨询加载、支付取消和继续支付流程发生回归")
    return CheckResult("咨询流程", "并行加载、筛选排班、取消后继续支付通过")


def check_paid_analysis() -> CheckResult:
    node = find_node()
    fixture = ROOT / "scripts" / "fixtures" / "paid_analysis_check.js"
    result = json.loads(run_command((node, str(fixture))))
    if not result.get("validated"):
        raise AssertionError("付费解读基础句、解锁条或揭文守卫发生回归")
    return CheckResult("付费解读", "基础五句、无支付宝、取消不揭文通过")


def main() -> int:
    configure_logging()
    checks = (check_required_files, check_json_and_routes, check_templates,
              check_javascript, check_styles, check_core_sample, check_consultation_flow,
              check_paid_analysis, check_ui_refine, check_ui_motion)
    try:
        for check in checks:
            result = check()
            logging.info("通过 [%s] %s", result.name, result.detail)
    except (OSError, ValueError, RuntimeError, AssertionError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        logging.exception("小程序检查失败：%s", error)
        return 1
    logging.info("全部检查通过；日志：%s", LOG_FILE)
    return 0


def check_ui_refine() -> CheckResult:
    fixture = ROOT / "scripts" / "fixtures" / "ui_refine_check.mjs"
    run_command((find_node(), str(fixture)))
    return CheckResult("界面交互回归", "字段错误、输入保留、清空确认、Tab 与空状态通过")


def check_ui_motion() -> CheckResult:
    fixture = ROOT / "scripts" / "fixtures" / "ui-motion" / "check.mjs"
    run_command((find_node(), str(fixture)))
    return CheckResult("参考动效回归", "八个延时入口、重复点击保护、隐藏取消跳转与素材检查通过")


def check_styles() -> CheckResult:
    config = load_app_config(MINIPROGRAM / "app.json")
    result = check_wxss(MINIPROGRAM, [page + ".wxss" for page in config["pages"]])
    templates = check_wxml(MINIPROGRAM)
    return CheckResult("微信视图编译", f"{result.file_count} 个样式和 {templates.file_count} 个模板通过微信编译器")


if __name__ == "__main__":
    raise SystemExit(main())
