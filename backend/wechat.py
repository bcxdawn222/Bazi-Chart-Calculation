from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass


CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


@dataclass(frozen=True)
class WechatIdentity:
    openid: str
    unionid: str


def exchange_code(app_id: str, app_secret: str, code: str) -> WechatIdentity:
    query = urllib.parse.urlencode({
        "appid": app_id,
        "secret": app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    })
    request = urllib.request.Request(f"{CODE2SESSION_URL}?{query}", method="GET")
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errcode"):
        raise ValueError(f"微信登录失败，错误码 {payload.get('errcode')}")
    openid = str(payload.get("openid", "")).strip()
    if not openid:
        raise ValueError("微信登录响应缺少 openid")
    return WechatIdentity(openid=openid, unionid=str(payload.get("unionid", "")).strip())
