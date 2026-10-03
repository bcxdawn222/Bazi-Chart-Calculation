from __future__ import annotations

import json
import math
import urllib.error
import urllib.request

from .analysis_store import SECTION_KEYS
from .config import Settings


DISCLAIMER = "传统文化研究与娱乐参考"


class AnalysisAIError(Exception):
    """模型调用或返回无法写成五类详细解读。"""


def _is_object(value: object) -> bool:
    return isinstance(value, dict)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and len(value) > 0


def _is_text_list(value: object) -> bool:
    return isinstance(value, list) and all(_is_text(item) for item in value)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def is_valid_chart(result: object) -> bool:
    if not _is_object(result):
        return False
    chart = result
    if not all(_is_object(chart.get(key)) for key in ("input", "normalizedTime", "bazi", "ziwei", "analysis")):
        return False
    time = chart["normalizedTime"]
    if not all(_is_object(time.get(key)) for key in ("solar", "lunar", "solarTimeCorrection")):
        return False
    if not all(_is_int(time["solar"].get(key)) and _is_int(time["lunar"].get(key)) for key in ("year", "month", "day")):
        return False
    if not _is_int(time.get("hour")) or not _is_int(time.get("minute")):
        return False
    bazi = chart["bazi"]
    details = bazi.get("details")
    if not all(_is_object(bazi.get(key)) for key in ("pillars", "tenGods", "dayun")) or not _is_object(details):
        return False
    if not _is_object(details.get("elementCounts")):
        return False
    pillars = bazi["pillars"]
    ten_gods = bazi["tenGods"]
    if not all(
        _is_text(pillars.get(key)) and len(str(pillars.get(key))) == 2 and _is_text(ten_gods.get(key))
        for key in ("year", "month", "day", "hour")
    ):
        return False
    counts = details["elementCounts"]
    if not all(_is_finite_number(counts.get(key)) and counts[key] >= 0 for key in ("wood", "fire", "earth", "metal", "water")):
        return False
    detail_pillars = details.get("pillars")
    if not isinstance(detail_pillars, list) or len(detail_pillars) != 4:
        return False
    for item in detail_pillars:
        hidden = item.get("hiddenStems") if _is_object(item) else None
        if not isinstance(hidden, list):
            return False
        if not all(_is_object(entry) and _is_text(entry.get("stem")) and _is_text(entry.get("tenGod")) for entry in hidden):
            return False
    if not isinstance(bazi["dayun"].get("items"), list) or not isinstance(bazi.get("shensha"), list):
        return False
    ziwei = chart["ziwei"]
    palaces = ziwei.get("palaces")
    if not _is_object(ziwei.get("details")) or not isinstance(ziwei.get("liunian"), list):
        return False
    if not isinstance(palaces, list) or len(palaces) != 12:
        return False
    for palace in palaces:
        if not _is_object(palace):
            return False
        if not all(_is_text_list(palace.get(key)) for key in ("mainStars", "auxiliaryStars", "luckyStars", "maleficStars")):
            return False
        brightness = palace.get("brightness")
        transformations = palace.get("transformations")
        related = palace.get("relatedPalaces")
        if not isinstance(brightness, list) or not isinstance(transformations, list) or not _is_object(related):
            return False
        if not all(_is_object(item) and _is_text(item.get("star")) and _is_text(item.get("level")) for item in brightness):
            return False
        if not all(_is_object(item) and _is_text(item.get("name")) and _is_text(item.get("star")) for item in transformations):
            return False
        if not _is_text(related.get("opposite")) or not _is_text_list(related.get("trines")):
            return False
    analysis = chart["analysis"]
    return all(_is_text(analysis.get(key)) for key in SECTION_KEYS)


def compact_chart_facts(chart: dict[str, object]) -> dict[str, object]:
    bazi = chart["bazi"]
    details = bazi["details"]
    palaces = []
    for palace in chart["ziwei"]["palaces"]:
        name = palace.get("name") if _is_object(palace) else ""
        palaces.append({
            "name": name if isinstance(name, str) else "",
            "mainStars": palace.get("mainStars") if _is_object(palace) else [],
            "auxiliaryStars": palace.get("auxiliaryStars") if _is_object(palace) else [],
        })
    return {
        "pillars": bazi.get("pillars"),
        "tenGods": bazi.get("tenGods"),
        "elementCounts": details.get("elementCounts") if _is_object(details) else {},
        "palaces": palaces,
    }


def _http_post(url: str, api_key: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        raise AnalysisAIError("模型接口暂不可用") from error
    if not isinstance(parsed, dict):
        raise AnalysisAIError("模型返回内容无效")
    return parsed


def _parse_sections(response: dict[str, object]) -> dict[str, str]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not _is_object(choices[0]):
        raise AnalysisAIError("模型返回内容无效")
    message = choices[0].get("message", choices[0])
    if not _is_object(message):
        raise AnalysisAIError("模型返回内容无效")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AnalysisAIError("模型返回内容无效")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise AnalysisAIError("模型返回不是 JSON") from error
    if not _is_object(parsed):
        raise AnalysisAIError("模型返回不是 JSON 对象")
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip() or DISCLAIMER not in value:
            raise AnalysisAIError("模型返回缺少有效解读段落")
        sections[key] = value
    return sections


def generate_analysis_sections(
    chart: dict[str, object],
    settings: Settings,
    http_post: object = None,
) -> dict[str, str]:
    post = _http_post if http_post is None else http_post
    if http_post is None and (not settings.ai_api_url or not settings.ai_api_key):
        raise AnalysisAIError("AI 未配置")
    payload = {
        "model": settings.ai_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "根据命盘结构写财富、婚姻、事业、性格、健康五类详细解读。"
                    "只返回 JSON 对象，键为 wealth、marriage、career、personality、health。"
                    "每段必须是非空中文，并原样包含：传统文化研究与娱乐参考。"
                    "不作保证或决策建议。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(compact_chart_facts(chart), ensure_ascii=False),
            },
        ],
    }
    response = post(settings.ai_api_url, settings.ai_api_key, payload)
    if not isinstance(response, dict):
        raise AnalysisAIError("模型返回内容无效")
    return _parse_sections(response)
