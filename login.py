"""一次性：扫码登录并保存登录态（storage_state.json）。

本工具仅提供自动化辅助功能，相关法律风险由使用者自行承担。

用法：python login.py
流程：
  1. 启动有头浏览器，打开 bigmodel.cn
  2. 你在浏览器里点「登录」并扫码（智谱 App / 微信 / 手机号均可，按页面实际走）
  3. 脚本轮询检测登录成功（出现用户头像 / 离开登录页）
  4. 保存 data/storage_state.json，后续 auto_order.py 直接复用

注意：cookie 有有效期，若运行时报「未登录」，重新跑一次本脚本即可。
"""
from __future__ import annotations

import asyncio
import os
import sys

from playwright.async_api import async_playwright

LOGIN_URL_DEFAULT = "https://bigmodel.cn/"
LOGIN_URL_HINTS = ("login", "signin", "sso")      # 处于登录流程的 URL 特征
LOGGED_IN_HINTS = ("avatar", "user-info", "nickname", "logout", "退出登录", "个人中心")
SUCCESS_TIMEOUT_S = 180


async def _looks_logged_in(page) -> bool:
    """判定是否已登录：URL 不在登录页 + 页面出现用户态元素。"""
    url = page.url.lower()
    if any(h in url for h in LOGIN_URL_HINTS):
        return False
    try:
        has = await page.evaluate(
            """(hints) => {
                const html = document.documentElement.outerHTML.toLowerCase();
                return hints.some(h => html.includes(h));
            }""",
            [h.lower() for h in LOGGED_IN_HINTS],
        )
        return bool(has)
    except Exception:
        return False


async def main(login_url: str = LOGIN_URL_DEFAULT, out_path: str = "data/storage_state.json") -> int:
    print("[login] 免责声明：本工具仅提供自动化辅助功能，相关法律风险由使用者自行承担。")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 820},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        print(f"[login] 打开 {login_url}")
        await page.goto(login_url)

        print("[login] 请在浏览器中完成登录（扫码 / 手机号等）。")
        print(f"[login] 最长等待 {SUCCESS_TIMEOUT_S} 秒检测登录成功……")

        ok = False
        for i in range(SUCCESS_TIMEOUT_S):
            await asyncio.sleep(1)
            try:
                if await _looks_logged_in(page):
                    ok = True
                    print(f"[login] 检测到登录成功（第 {i + 1} 秒）")
                    break
            except Exception:
                continue

        if not ok:
            print("[login] 超时未检测到登录成功，未保存登录态。")
            # 仍给用户保留浏览器看一眼，但这里自动关闭
            await context.close()
            await browser.close()
            return 1

        # 登录后再访问一次 glm-coding，确保相关域名的 cookie 都已写入
        try:
            await page.goto("https://bigmodel.cn/glm-coding", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        await context.storage_state(path=out_path)
        print(f"[login] 登录态已保存到 {out_path}")
        print("[login] 现在可以运行：python auto_order.py")

        await context.close()
        await browser.close()
        return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
