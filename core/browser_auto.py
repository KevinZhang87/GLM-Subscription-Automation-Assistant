"""浏览器自动化下单辅助模块（Playwright 异步 chromium）。

本模块是自动化辅助工具的浏览器执行路径，帮助使用者自动完成页面操作流程，
以减少手动重复劳动。仅用于合法的个人自助下单场景。

职责：
1. prewarm()：到点前加载页面、定位套餐卡片和按钮，消除冷启动开销。
2. run()：用 JS 注入方式快速触发按钮点击，失败回退原生 click；
   连续触发 click_attempts 次。
3. detect_result()：检测是否跳转到支付/订单页判定成功。
4. 验证码兜底：检测到验证码即暂停 + 响铃，等人工处理（不绕过）。

注意：智谱页面若改版，主要维护点是下方的文案/选择器常量。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from playwright.async_api import async_playwright, BrowserContext, Page, TimeoutError as PWTimeout

# ---------- 可维护点：页面文案/选择器 ----------
# 成功判定：URL 中出现这些片段之一，视为已进入支付/订单流程
PAY_URL_HINTS = ("pay", "order", "cashier", "checkout", "confirm")
# 登录失效：URL 或页面出现这些信号
LOGIN_URL_HINTS = ("login", "signin")
# 验证码容器特征（腾讯防水墙 / 通用 iframe）
CAPTCHA_HINTS = ("tcaptcha", "captcha-verify", "tc-action-popup", "slider")


class OrderResult:
    """单次自动化下单的结果。"""

    def __init__(self, success: bool, message: str, final_url: str = ""):
        self.success = success
        self.message = message
        self.final_url = final_url


class BrowserAuto:
    """浏览器自动化下单辅助器。"""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        b = cfg.get("browser", {})
        self.headless: bool = b.get("headless", False)
        self.click_attempts: int = int(b.get("click_attempts", 2))
        self.fallback_native_click: bool = b.get("fallback_native_click", True)
        self.storage_state: str = cfg.get("storage_state", "data/storage_state.json")

        t = cfg.get("target", {})
        self.plan_keyword: str = t.get("plan_keyword", "Lite")
        self.buy_texts: list[str] = t.get("buy_button_texts", ["立即订阅"])

        pages = cfg.get("pages", {})
        self.url_coding_plan: str = pages.get(
            "coding_plan", "https://bigmodel.cn/glm-coding"
        )

        # 运行期持有
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ---------- 生命周期 ----------
    async def __aenter__(self) -> "BrowserAuto":
        self._playwright = await async_playwright().start()
        storage = (
            self.storage_state if os.path.exists(self.storage_state) else None
        )
        if storage is None:
            print("[browser] 警告：未找到登录态文件，将以未登录状态启动")
        self._context = await self._launch_with_storage(storage)
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        return self

    async def _launch_with_storage(self, storage: str | None) -> BrowserContext:
        """用 storage_state 启动一个非持久化上下文（更轻量）。"""
        browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        return await browser.new_context(
            storage_state=storage,
            viewport={"width": 1366, "height": 850},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._context:
                await self._context.close()
        finally:
            if self._playwright:
                await self._playwright.stop()

    @property
    def page(self) -> Page:
        assert self._page is not None, "BrowserAuto 未启动"
        return self._page

    # ---------- 预热 ----------
    async def prewarm(self) -> None:
        """到点前：打开页面并尽量让按钮处于「可点」状态。

        页面是 SPA，按钮可能在交互后才渲染，这里宽容等待。
        即使没立刻定位到按钮，也不阻塞——run() 时会再次尝试。
        """
        page = self.page
        print(f"[browser] 预热：打开 {self.url_coding_plan}")
        try:
            await page.goto(self.url_coding_plan, wait_until="domcontentloaded", timeout=15000)
        except PWTimeout:
            print("[browser] 预热：页面加载较慢，继续")

        # 先确认登录态是否有效
        await self._check_login()

        # 容错地尝试定位套餐卡片（失败不抛错，留给 run）
        await self._scroll_to_plan()

    async def _check_login(self) -> None:
        url = self.page.url
        if any(h in url for h in LOGIN_URL_HINTS):
            print("[browser] 警告：当前似乎在登录页，登录态可能已失效。")
            print("         请重新运行 login.py 扫码后再来。")

    async def _scroll_to_plan(self) -> None:
        """把目标套餐滚动到视口，提升点击命中率与渲染概率。"""
        keyword = self.plan_keyword
        try:
            await self.page.evaluate(
                """(kw) => {
                    const els = Array.from(document.querySelectorAll('*'));
                    const hit = els.find(e =>
                        e.children.length === 0 && (e.textContent || '').includes(kw));
                    if (hit) { hit.scrollIntoView({block: 'center'}); return true; }
                    return false;
                }""",
                keyword,
            )
        except Exception:
            pass  # 预热阶段失败不致命

    # ---------- 触发 ----------
    async def run(self) -> OrderResult:
        """执行自动化下单：JS 注入点击优先，失败回退原生 click。"""
        page = self.page

        # 先把目标套餐滚到视口（run 时再确保一次）
        await self._scroll_to_plan()

        # 点击前的快速预检：是否已经弹出验证码
        if await self._has_captcha():
            await self._await_human_captcha("触发前检测到验证码")

        clicked = False
        last_err = ""
        for i in range(max(1, self.click_attempts)):
            try:
                ok = await self._js_click_buy()
                if ok:
                    clicked = True
                    print(f"[browser] 第 {i + 1} 次 JS 注入点击成功")
                    break
            except Exception as e:
                last_err = repr(e)

        if not clicked and self.fallback_native_click:
            try:
                ok = await self._native_click_buy()
                if ok:
                    clicked = True
                    print("[browser] 原生 click 回退成功")
            except Exception as e:
                last_err = repr(e)

        if not clicked:
            return OrderResult(False, f"未能点击到购买按钮：{last_err}", page.url)

        # 点击后短暂等待跳转/弹窗
        await asyncio.sleep(0.4)

        # 验证码兜底
        if await self._has_captcha():
            await self._await_human_captcha("点击后弹出验证码")

        # 结果检测
        return await self._detect_result()

    async def _js_click_buy(self) -> bool:
        """注入 JS：在目标套餐卡片内找到购买按钮并原生 click()。

        返回是否真的点到了。
        """
        kw = self.plan_keyword
        return bool(
            await self.page.evaluate(
                """({kw, texts}) => {
                    const norm = s => (s || '').replace(/\\s+/g, '');
                    const matchText = (el) => {
                        const t = norm(el.textContent);
                        return texts.some(tx => t === norm(tx) || t.includes(norm(tx)));
                    };
                    // 1) 找到套餐卡片：文本含套餐关键词
                    const all = Array.from(document.querySelectorAll('div, section, article, li'));
                    const card = all.find(e =>
                        e.children.length > 0 && (e.textContent || '').includes(kw)
                        && e.querySelector('button, a'));
                    const scope = card || document;
                    // 2) 在卡片（或全页）内找按钮/链接
                    const candidates = Array.from(
                        scope.querySelectorAll('button, a, [role=button], .btn')
                    ).filter(matchText);
                    const btn = candidates[0];
                    if (!btn) return false;
                    btn.scrollIntoView({block: 'center'});
                    // 原生事件触发
                    for (const type of ['pointerdown','mousedown','pointerup','mouseup','click']) {
                        btn.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
                    }
                    return true;
                }""",
                {"kw": kw, "texts": self.buy_texts},
            )
        )

    async def _native_click_buy(self) -> bool:
        """回退：用 Playwright 原生 locator 点击首个匹配按钮。"""
        page = self.page
        loc = page.locator("button, a, [role=button]").filter(
            has_text=self.buy_texts[0]
        ).first
        try:
            await loc.scroll_into_view_if_needed(timeout=2000)
            await loc.click(timeout=2000)
            return True
        except Exception:
            return False

    # ---------- 结果检测 ----------
    async def _detect_result(self) -> OrderResult:
        page = self.page
        # 给页面一点时间完成跳转
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=4000)
        except PWTimeout:
            pass
        url = page.url
        if any(h in url.lower() for h in PAY_URL_HINTS):
            return OrderResult(True, f"已跳转到支付/订单页：{url}", url)
        # 有时不会跳转而是弹出确认框；简单探测一下页面是否出现「下单成功/订单号」
        try:
            got = await page.evaluate(
                """() => {
                    const t = document.body.innerText || '';
                    return /订单(?:号)?|下单成功|确认订单|去支付/.test(t);
                }"""
            )
            if got:
                return OrderResult(True, "页面出现订单/支付相关元素（可能需手动确认支付）", url)
        except Exception:
            pass
        if any(h in url for h in LOGIN_URL_HINTS):
            return OrderResult(False, "登录态失效，需重新登录", url)
        return OrderResult(False, "未检测到明确的成功信号，请人工查看浏览器", url)

    # ---------- 验证码兜底（不绕过，交由人工） ----------
    async def _has_captcha(self) -> bool:
        try:
            return bool(
                await self.page.evaluate(
                    """(hints) => {
                        const html = document.documentElement.outerHTML.toLowerCase();
                        if (hints.some(h => html.includes(h))) return true;
                        const ifr = Array.from(document.querySelectorAll('iframe'));
                        return ifr.some(f => hints.some(h => (f.src||'').toLowerCase().includes(h)));
                    }""",
                    CAPTCHA_HINTS,
                )
            )
        except Exception:
            return False

    async def _await_human_captcha(self, reason: str) -> None:
        """检测到验证码：响铃 + 终端提示，等人工在浏览器里完成（最多 120s）。"""
        print("\a")
        print(f"[browser][验证码] {reason} —— 请在浏览器窗口手动完成验证码")
        print("[browser][验证码] 等待人工处理，最长 120 秒……")
        try:
            for _ in range(120):
                await asyncio.sleep(1)
                if not await self._has_captcha():
                    print("[browser][验证码] 验证码已消失，继续")
                    return
        except Exception:
            pass
        print("[browser][验证码] 等待超时，继续后续流程")
