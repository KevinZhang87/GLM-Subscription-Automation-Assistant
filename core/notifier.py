"""结果通知：终端高亮打印（始终开启）+ 可选企业微信/钉钉 webhook。

设计要点：
- 下单结果（成功/失败）都要立刻让人知道。终端用 rich 高亮 + 响铃（\\a）。
- webhook 为可选项，配置为空则跳过；网络失败不影响主流程。
"""
from __future__ import annotations

import json
from typing import Any

try:
    import httpx  # type: ignore
except ImportError:  # 未装 httpx 时仅禁用 webhook，终端打印不受影响
    httpx = None  # type: ignore

try:
    from rich.console import Console
    from rich.panel import Panel

    _console = Console()
except ImportError:  # rich 不可用时降级为 print
    _console = None  # type: ignore


def _term_print(message: str, *, success: bool) -> None:
    """终端输出：成功绿色 / 失败红色，并响铃提醒。"""
    bell = "\a"
    if _console is not None:
        color = "green" if success else "red"
        title = "自动化下单成功" if success else "自动化下单失败/需人工介入"
        _console.print(Panel(message, title=title, style=color, border_style=color))
        _console.print(bell, end="")
    else:
        tag = "[OK]" if success else "[FAIL]"
        print(f"{tag} {message}{bell}")


def _post_webhook(url: str, payload: dict[str, Any], timeout: float = 3.0) -> None:
    """发送一次 webhook，失败静默（不阻断主流程）。"""
    if not url or httpx is None:
        return
    try:
        with httpx.Client(timeout=timeout) as client:
            client.post(url, json=payload)
    except Exception:
        pass  # 通知失败不影响主流程


def notify(message: str, *, success: bool, notifier_cfg: dict[str, Any]) -> None:
    """统一通知入口。

    Args:
        message: 通知正文
        success: True=成功（绿），False=失败/需人工（红）
        notifier_cfg: config.yaml 里的 notifier 段
    """
    _term_print(message, success=success)

    text = ("【自动化下单成功】" if success else "【自动化下单失败】") + message

    wecom = (notifier_cfg or {}).get("wecom_webhook", "")
    if wecom:
        _post_webhook(wecom, {"msgtype": "text", "text": {"content": text}})

    ding = (notifier_cfg or {}).get("dingtalk_webhook", "")
    if ding:
        _post_webhook(ding, {"msgtype": "text", "text": {"content": text}})
