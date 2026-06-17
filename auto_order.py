"""GLM 订阅自动化下单辅助工具 - 主入口。

免责声明：本工具仅提供自动化辅助功能，旨在帮助使用者以程序方式完成网页上的
常规点击与表单提交操作。本工具不提供绕过验证码、逆向接口签名、突破网站风控
或任何非授权访问的能力。使用者应自行评估并承担使用本工具的一切法律风险与后果，
包括但不限于遵守目标网站用户协议及适用法律法规。禁止用于批量抢购倒卖、破坏
公平机制、规避付费等目的。

流程：
  1. 加载 config.yaml
  2. NTP 对齐时钟
  3. 启动浏览器（异步），预热目标页面
  4. 到点（忙等精确触发）
  5. 同时发起：浏览器自动化下单（主） + 接口自动化下单（可选）
  6. 汇总结果，通知

用法：
  python auto_order.py                 # 使用 config.yaml
  python auto_order.py -c my.yaml      # 指定配置
  python auto_order.py --dry-run       # 仅走流程做演练，不真正下单
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    print("缺少依赖，请先执行：pip install -r requirements.txt")
    sys.exit(2)

from core.browser_auto import BrowserAuto, OrderResult
from core.http_auto import http_run
from core.notifier import notify
from core.time_sync import sync_clock, parse_trigger_time, sleep_until, ClockOffset

CONFIG_PATH_DEFAULT = "config.yaml"

DISCLAIMER_BANNER = """
==============================================================================
  GLM 订阅自动化辅助工具
------------------------------------------------------------------------------
  本工具仅提供自动化辅助功能，帮助使用者以程序方式完成网页上的常规
  点击与表单提交操作。本工具不提供绕过验证码、逆向接口签名、突破
  网站风控或任何非授权访问的能力。

  使用本工具即表示您知悉并同意：
    - 所有实际下单、支付及由此产生的法律效果，均由您本人（使用者）承担。
    - 您应确保使用行为符合目标网站用户协议及适用法律法规。
    - 因使用本工具产生的一切法律风险与后果，由使用者自行承担。
    - 禁止用于批量抢购倒卖、破坏公平机制、规避付费等目的。

  若不同意上述条款，请立即停止使用并删除本工具。
==============================================================================
""".strip("\n")


def print_disclaimer() -> None:
    """启动时打印免责声明，确保使用者知悉法律风险由其自行承担。"""
    try:
        from rich.console import Console
        from rich.panel import Panel
        Console().print(Panel(DISCLAIMER_BANNER, title="免责声明", style="yellow", border_style="yellow"))
    except ImportError:
        print(DISCLAIMER_BANNER)
        print("=" * 78)


def load_config(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        print(f"配置文件不存在：{path}")
        print("请先复制：copy config.example.yaml config.yaml  （Windows）")
        print("        cp config.example.yaml config.yaml  （Linux/Mac）")
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


async def _orchestrate(cfg: dict[str, Any], dry_run: bool) -> int:
    # 1) 时钟对齐
    ts_cfg = cfg.get("time_sync", {})
    if ts_cfg.get("enabled", True):
        clock = sync_clock(ntp_server=ts_cfg.get("ntp_server", "ntp.aliyun.com"))
    else:
        print("[auto] time_sync 已禁用，使用本地时钟（可能有偏移）")
        clock = ClockOffset(offset=0.0, source="local")

    target_text = cfg.get("trigger_time", "")
    if not target_text:
        print("config.yaml 缺少 trigger_time")
        return 2
    target_ts = parse_trigger_time(target_text)
    busy_ms = int(ts_cfg.get("busy_wait_ms", 200))

    now_real = clock.real_now()
    lead = now_real - target_ts
    print(f"[auto] 目标触发时间：{target_text.strip()}")
    print(f"[auto] 距离到点：{lead:.1f} 秒（{'已过期' if lead > 0 else '未到'}）")
    if lead > 0:
        print("[auto] 警告：目标时间已过，仍会立即尝试一次。")

    if dry_run:
        print("[auto][dry-run] 演练模式：不真正下单，流程到此为止。")
        return 0

    # 2) 启动浏览器并预热
    async with BrowserAuto(cfg) as auto:
        await auto.prewarm()
        print("[auto] 预热完成，等待到点……")

        # 3) 精确等到点
        err = sleep_until(target_ts, clock, busy_wait_ms=busy_ms)
        print(f"[auto] 已到点，触发！实际误差 {err * 1000:+.1f} ms")

        # 4) 同时发起浏览器 + HTTP（如启用），取任一成功
        tasks = []
        tasks.append(("browser", auto.run()))
        if (cfg.get("http_auto") or {}).get("enabled"):
            tasks.append(("http", http_run(cfg)))

        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    # 5) 汇总
    success = False
    msgs = []
    for (name, _), r in zip(tasks, results):
        if isinstance(r, Exception):
            msgs.append(f"[{name}] 异常：{r!r}")
            continue
        if name == "browser":
            sr: OrderResult = r
            msgs.append(f"[browser] {'成功' if sr.success else '失败'} - {sr.message}")
            success = success or sr.success
        else:
            hr = r  # dict
            skipped = hr.get("skipped")
            if skipped:
                msgs.append(f"[http] 跳过：{hr.get('message')}")
            else:
                ok = bool(hr.get("ok"))
                msgs.append(
                    f"[http] {'成功' if ok else '未成功'} - {hr.get('message')} | {hr.get('detail','')}"
                )
                success = success or ok

    summary = "\n".join(msgs)
    notify(summary, success=success, notifier_cfg=cfg.get("notifier", {}))

    if not success:
        print("\n[auto] 未确认成功。如果是页面跳转/支付确认较慢，")
        print("       可手动查看刚才的浏览器窗口（脚本已退出，浏览器已关闭）。")
        print("       建议：把 config.yaml -> browser.headless 设为 false，")
        print("             并优先排查登录态是否有效（重跑 login.py）。")
    return 0 if success else 1


def main() -> int:
    print_disclaimer()
    ap = argparse.ArgumentParser(description="GLM 订阅自动化下单辅助工具")
    ap.add_argument("-c", "--config", default=CONFIG_PATH_DEFAULT, help="配置文件路径")
    ap.add_argument("--dry-run", action="store_true", help="演练模式，不真正下单")
    args = ap.parse_args()

    cfg = load_config(args.config)
    try:
        return asyncio.run(_orchestrate(cfg, args.dry_run))
    except KeyboardInterrupt:
        print("\n[auto] 已中止")
        return 130


if __name__ == "__main__":
    sys.exit(main())
