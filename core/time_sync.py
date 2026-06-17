"""时间对齐：通过 NTP 估算本地时钟与服务器（真实时间）的偏移，
并在触发点前进入忙等，保证时间精度达 ±10ms 量级。

本工具仅提供自动化辅助功能，相关法律风险由使用者自行承担。

设计要点：
- 自动化操作对「到点时刻」非常敏感。本地电脑时钟可能快/慢几百 ms 甚至几秒，
  直接用 time.sleep 到点会偏。
- 这里用 NTP 一次性估算 offset = 真实时间 - 本地时间。
  之后「真实触发时刻 = 目标时刻」时，「本地时刻 = 目标时刻 - offset」。
- 到点前 busy_wait_ms 进入忙等（CPU 自旋），消除 sleep 的尾段抖动。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

try:
    import ntplib  # type: ignore
except ImportError:  # 运行期未装也不致命，降级为纯本地时钟
    ntplib = None  # type: ignore


@dataclass
class ClockOffset:
    """本地时钟偏移（秒）。real_time = local_time + offset。"""

    offset: float
    source: str  # "ntp" 或 "local"

    def real_now(self) -> float:
        """返回当前「真实时间」的时间戳（已对齐）。"""
        return time.time() + self.offset


def sync_clock(ntp_server: str = "ntp.aliyun.com", timeout: int = 5) -> ClockOffset:
    """与 NTP 服务器对齐，返回时钟偏移。失败则返回 0 偏移（纯本地时钟）。"""
    if ntplib is None:
        print("[time_sync] ntplib 未安装，使用本地时钟（可能有偏移）")
        return ClockOffset(offset=0.0, source="local")
    try:
        c = ntplib.NTPClient()
        resp = c.request(ntp_server, version=3, timeout=timeout)
        offset = float(resp.tx_time - time.time() + resp.delay / 2.0)
        print(
            f"[time_sync] NTP 对齐成功：本地时钟偏移 {offset * 1000:+.1f} ms "
            f"(server={ntp_server})"
        )
        return ClockOffset(offset=offset, source="ntp")
    except Exception as e:  # 网络不通 / 防火墙拦截
        print(f"[time_sync] NTP 对齐失败 ({e})，降级使用本地时钟")
        return ClockOffset(offset=0.0, source="local")


def parse_trigger_time(text: str) -> float:
    """把 '2026-06-18 12:00:00' 解析为时间戳。"""
    dt = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S")
    return dt.timestamp()


def sleep_until(
    target_real_ts: float,
    clock: ClockOffset,
    busy_wait_ms: int = 200,
) -> float:
    """阻塞直到「真实时间」到达 target_real_ts。

    - 距离到点 > busy_wait_ms 时：粗粒度 time.sleep（不占 CPU）
    - 进入 busy_wait_ms 窗口后：忙等自旋（精度 ±10ms）

    返回实际触发的真实时间戳与目标的误差（秒，负=提前，正=滞后）。
    """
    # 目标对应的「本地时间戳」
    target_local_ts = target_real_ts - clock.offset

    # 阶段 1：粗粒度 sleep，留出 busy_wait_ms 的忙等窗口
    lead = busy_wait_ms / 1000.0
    coarse_target = target_local_ts - lead
    while True:
        remaining = coarse_target - time.time()
        if remaining <= 0:
            break
        # 不要一次性 sleep 完，分段睡，便于中途被时钟漂移修正感知
        time.sleep(min(remaining, 1.0))

    # 阶段 2：忙等自旋到精确到点
    while time.time() < target_local_ts:
        pass

    fired_real = clock.real_now()
    return fired_real - target_real_ts
