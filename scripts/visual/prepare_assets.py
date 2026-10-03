from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "ui-reference-20261002"
DEST = ROOT / "miniprogram" / "assets" / "compass"
PALETTE: tuple[tuple[str, str], ...] = ()
SHADOW = re.compile(r"drop-shadow\(0 0 ([\d.]+)px rgba\(([\d.,\s]+)\)\)")


def preserve_shadow(root: ET.Element, node: ET.Element, value: str, index: int) -> None:
    matched = SHADOW.fullmatch(value)
    if matched is None:
        raise ValueError(f"未支持的来源阴影：{value}")
    channels = tuple(float(part) for part in matched.group(2).split(","))
    if len(channels) != 4 or not all(0 <= part <= 255 for part in channels[:3]) or not 0 <= channels[3] <= 1:
        raise ValueError("来源阴影颜色无效")
    defs = root.find("defs")
    if defs is None:
        defs = ET.SubElement(root, "defs")
    identifier = f"source-shadow-{index}"
    effect = ET.SubElement(defs, "filter", id=identifier, x="-200%", y="-200%", width="500%", height="500%")
    ET.SubElement(effect, "feGaussianBlur", attrib={"in": "SourceAlpha", "stdDeviation": matched.group(1), "result": "blur"})
    ET.SubElement(effect, "feFlood", attrib={
        "flood-color": f"rgb({channels[0]:g},{channels[1]:g},{channels[2]:g})",
        "flood-opacity": f"{channels[3]:g}", "result": "color",
    })
    ET.SubElement(effect, "feComposite", attrib={"in": "color", "in2": "blur", "operator": "in", "result": "shadow"})
    merged = ET.SubElement(effect, "feMerge")
    ET.SubElement(merged, "feMergeNode", attrib={"in": "shadow"})
    ET.SubElement(merged, "feMergeNode", attrib={"in": "SourceGraphic"})
    node.set("filter", f"url(#{identifier})")


def recolor(element: ET.Element) -> None:
    for index, node in enumerate(list(element.iter())):
        declarations = (part.partition(":") for part in node.get("style", "").split(";"))
        for name, separator, value in declarations:
            if separator and name.strip() == "filter" and value.strip().startswith("drop-shadow"):
                # 将来源 CSS 阴影转为栅格器支持的 SVG 滤镜，不重绘图形。
                preserve_shadow(element, node, value.strip(), index)
        for name in list(node.attrib):
            if name.startswith("data-") or name == "style":
                del node.attrib[name]
        if node.tag.endswith("g") and "font-family" in node.attrib:
            node.set("font-family", "SimSun,serif")
        for name, value in list(node.attrib.items()):
            for before, after in PALETTE:
                value = value.replace(before, after)
            node.set(name, value)


def main() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "logs" / "ui-assets.log", level=logging.INFO,
        encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s",
    )
    DEST.mkdir(parents=True, exist_ok=True)
    layers = cast(list[str], json.loads((SOURCE / "wheel-layers.json").read_text("utf-8")))
    # Preserve the reference's actual geometry; palette and raster density only.
    wheel = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", viewBox="-200 -200 400 400")
    for layer in layers[:8]:
        parsed = ET.fromstring(layer)
        recolor(parsed)
        wheel.extend(list(parsed))
    center = ET.fromstring((SOURCE / "taiji-source.svg").read_text("utf-8"))
    center.set("xmlns", "http://www.w3.org/2000/svg")
    recolor(center)
    node = os.environ.get("NODE_EXE", "node")
    with tempfile.TemporaryDirectory(prefix="miniprogram-assets-") as temporary:
        work = Path(temporary)
        ET.ElementTree(wheel).write(work / "wheel.svg", encoding="utf-8")
        ET.ElementTree(center).write(work / "taiji.svg", encoding="utf-8")
        completed = subprocess.run(
            [node, str(Path(__file__).with_name("render_assets.mjs")), str(work), str(DEST)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        logging.info("%s\n%s", completed.stdout, completed.stderr)
        if completed.returncode:
            raise RuntimeError(completed.stderr)
    print(f"UI assets: {DEST}")


if __name__ == "__main__":
    main()
