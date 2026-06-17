"""HTTP 接口自动化下单辅助模块（可选）。

本模块是自动化辅助工具的 HTTP 执行路径，用于在已掌握目标网站下单接口的情况下，
跳过浏览器渲染层直接发起请求，以降低响应延迟。

适用场景：使用者已用 DevTools 抓包到「下单/购买」接口。

边界说明（重要）：
- 仅复用浏览器登录后已持有的 token（从 storage_state.json 提取 cookie）。
- 不提供任何逆向签名/加密能力。
- 若目标接口需要动态签名（如带时间戳+sign 的请求体），本模块无法工作，
  会自动跳过并提示使用者回退浏览器路径。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None  # type: ignore


def _load_cookies(storage_state_path: str) -> dict[str, str]:
    """从 Playwright storage_state.json 提取 cookie 为简单 dict。"""
    if not os.path.exists(storage_state_path):
        return {}
    try:
        with open(storage_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    cookies = {}
    for c in data.get("cookies", []):
        cookies[c.get("name", "")] = c.get("value", "")
    return cookies


async def http_run(cfg: dict[str, Any]) -> dict[str, Any]:
    """执行接口自动化下单。

    Returns:
        {"ok": bool, "message": str, "detail": str}
        若 httpx 未安装或未启用，返回 ok=False 且 skipped=True。
    """
    http_cfg = (cfg.get("http_auto") or {})
    if not http_cfg.get("enabled", False):
        return {"ok": False, "skipped": True, "message": "http_auto 未启用"}

    if httpx is None:
        return {"ok": False, "skipped": True, "message": "httpx 未安装"}

    url = http_cfg.get("url", "")
    method = str(http_cfg.get("method", "POST")).upper()
    payload_tpl = http_cfg.get("payload_template", "{}")
    concurrency = max(1, int(http_cfg.get("concurrency", 2)))
    storage_state = cfg.get("storage_state", "data/storage_state.json")

    cookies = _load_cookies(storage_state)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(8.0, connect=3.0),
        cookies=cookies,
        headers=headers,
        follow_redirects=False,
    ) as client:

        async def _once() -> dict[str, Any]:
            try:
                resp = await client.request(method, url, content=payload_tpl.encode("utf-8"))
                ok = 200 <= resp.status_code < 300
                # 业务层成功信号通常在 JSON body 中
                body_snippet = resp.text[:200]
                biz_ok = ok
                try:
                    j = resp.json()
                    # 兼容常见封装 {success:true} / {code:0} / {ok:true}
                    if isinstance(j, dict):
                        biz_ok = biz_ok and (
                            j.get("success") is True
                            or j.get("ok") is True
                            or j.get("code") in (0, 200, "0", "200")
                        )
                except Exception:
                    pass
                return {
                    "ok": biz_ok,
                    "status": resp.status_code,
                    "body": body_snippet,
                }
            except Exception as e:
                return {"ok": False, "status": -1, "body": repr(e)}

        # 并发发起
        results = await asyncio.gather(*[_once() for _ in range(concurrency)])

    any_ok = any(r.get("ok") for r in results)
    best = next((r for r in results if r.get("ok")), results[0] if results else {})
    detail = json.dumps(best, ensure_ascii=False)
    return {
        "ok": any_ok,
        "skipped": False,
        "message": ("接口自动化下单成功" if any_ok else "接口自动化下单未返回明确成功"),
        "detail": detail,
    }
