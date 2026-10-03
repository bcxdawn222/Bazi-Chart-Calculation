from __future__ import annotations

import copy
import argparse
import logging
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from prepare_assets import DEST, ROOT, recolor


SOURCE = ROOT / "docs" / "ui-reference-package-20261003" / "app" / "project"


class SourceSvgParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.images: list[str] = []
        self.depth = 0
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "svg":
            self.depth += 1
        if self.depth:
            source = self.get_starttag_text()
            self.tags.append(source[1:1 + len(tag)])
            self.parts.append(source)

    def handle_endtag(self, tag: str) -> None:
        if not self.depth:
            return
        original_tag = self.tags.pop()
        if original_tag.lower() != tag:
            raise ValueError("SVG 标签没有匹配")
        self.parts.append(f"</{original_tag}>")
        if tag == "svg":
            self.depth -= 1
            if not self.depth:
                self.images.append("".join(self.parts))
                self.parts.clear()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag, attrs
        if self.depth:
            self.parts.append(self.get_starttag_text())

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.depth:
            self.parts.append(f"&{name};")


def svg_root(viewbox: str) -> ET.Element:
    return ET.Element("svg", xmlns="http://www.w3.org/2000/svg", viewBox=viewbox)

def write_topic_icons(layers: list[ET.Element], defs: ET.Element, work: Path) -> None:
    groups = list(layers[2].findall("g/g"))
    if len(groups) != 8:
        raise ValueError("参考包的八卦图纹不完整")
    # 导航用图纹采用原始三爻，不沿用旧的符号图片。
    topics = ("bazi", "daily", "question", "wealth", "prayer", "compatibility", "liuyao", "wish")
    assignments = list(enumerate(topics)) + [(6, "naming")]
    for index, name in assignments:
        image = svg_root("-26 -142 52 40")
        image.append(copy.deepcopy(defs))
        group = copy.deepcopy(groups[index])
        group.attrib.pop("transform", None)
        group.set("fill", "#F0A886")
        image.append(group)
        ET.ElementTree(image).write(work / f"icon-{name}.svg", encoding="utf-8")

def write_motion_layers(layers: list[ET.Element], defs: ET.Element, images: list[ET.Element], work: Path) -> None:
    names = ("plate", "structure", "trigrams", "gua", "jieqi", "dizhi", "orbit", "outer")
    for name, layer in zip(names, layers[:8]):
        image = svg_root("-200 -200 400 400")
        if name != "plate":
            image.append(copy.deepcopy(defs))
        image.extend(copy.deepcopy(list(layer)))
        recolor(image)
        ET.ElementTree(image).write(work / f"layer-{name}.svg", encoding="utf-8")
    day_master = next(image for image in images if image.find("defs/linearGradient[@id='dmG']") is not None)
    intro = next(image for image in images if image.get("viewBox") == "0 0 402 874")
    intro = copy.deepcopy(intro)
    for path in intro.findall("path"):
        path.set("stroke-dashoffset", "0")
    star = next(node for node in layers[6] if node.tag == "circle" and node.get("r") == "2.8")
    point = svg_root("-8 -184 16 16")
    point.append(copy.deepcopy(star))
    for name, image in (("day-master", copy.deepcopy(day_master)), ("intro", copy.deepcopy(intro)), ("star", point)):
        image.set("xmlns", "http://www.w3.org/2000/svg")
        recolor(image)
        ET.ElementTree(image).write(work / f"effect-{name}.svg", encoding="utf-8")


def main() -> None:
    arguments = argparse.ArgumentParser(description="将来源图层转换为本地 PNG，保留几何与静态阴影")
    arguments.add_argument("--self-test", action="store_true")
    args = arguments.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "logs" / "ui-package-assets.log",
        encoding="utf-8", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = SourceSvgParser()
    parser.feed((SOURCE / "玄机 App.dc.html").read_text("utf-8"))
    images = [ET.fromstring(source) for source in parser.images]
    layers = [image for image in images if image.get("viewBox") == "-200 -200 400 400"]
    if len(layers) < 10:
        raise ValueError("参考包的罗盘图层不完整")
    defs = layers[0].find("defs")
    if defs is None or not any(node.get("points") == "0,-140 4.2,-98 0,-56 -4.2,-98" for node in layers[9]):
        raise ValueError("参考包的指针结构与预期不一致")
    if args.self_test:
        orbit = copy.deepcopy(layers[6])
        original = [tuple(node.attrib.items()) for node in orbit.findall("circle")]
        recolor(orbit)
        filters = orbit.findall("defs/filter")
        assert len(filters) == 2
        assert [node.find("feGaussianBlur").get("stdDeviation") for node in filters] == ["6", "7"]
        assert all(node.get("filter", "").startswith("url(#source-shadow-") for node in orbit.findall("circle"))
        for before, node in zip(original, orbit.findall("circle")):
            for name, value in before:
                if name != "style":
                    assert node.get(name) == value
        assert not any("style" in node.attrib for node in orbit.iter())
        logging.info("来源阴影、原始坐标、颜色和透明度自检通过")
        print("来源素材自检通过：阴影转换、原始坐标、颜色与透明度。")
        return
    wheel = svg_root("-200 -200 400 400")
    for layer in layers[:8]:
        wheel.extend(copy.deepcopy(list(layer)))
    needle = svg_root("-200 -200 400 400")
    needle.append(copy.deepcopy(defs))
    needle.extend(copy.deepcopy(list(layers[9])))
    wedge = svg_root("-200 -200 400 400")
    wedge.append(copy.deepcopy(defs))
    wedge.extend(copy.deepcopy(list(layers[8])))
    center = next(image for image in images if image.get("viewBox") == "-20 -20 40 40")
    center.set("xmlns", "http://www.w3.org/2000/svg")
    DEST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xuanji-package-assets-") as temporary:
        work = Path(temporary)
        for name, image in (("wheel", wheel), ("needle", needle), ("wedge", wedge), ("taiji", center)):
            recolor(image)
            ET.ElementTree(image).write(work / f"{name}.svg", encoding="utf-8")
        write_topic_icons(layers, defs, work)
        write_motion_layers(layers, defs, images, work)
        completed = subprocess.run(
            [os.environ.get("NODE_EXE", "node"), str(Path(__file__).with_name("render_assets.mjs")),
             str(work), str(DEST)],
            cwd=ROOT, capture_output=True, encoding="utf-8", check=False,
        )
        logging.info("%s\n%s", completed.stdout, completed.stderr)
        if completed.returncode:
            raise RuntimeError(completed.stderr)
    print(f"Source package assets: {DEST}")


if __name__ == "__main__":
    main()
