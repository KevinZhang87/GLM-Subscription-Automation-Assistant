# GLM Subscription Automation Assistant / GLM 订阅自动化下单辅助工具

<p align="center">
  <a href="https://bigmodel.cn/glm-coding" target="_blank">
    <img src="https://img.shields.io/badge/Platform-GLM%20BigModel-blue?style=flat-square&logo=python" alt="Platform">
  </a>
  <a href="https://www.python.org/downloads/" target="_blank">
    <img src="https://img.shields.io/badge/Python-3.9%2B-green?style=flat-square&logo=python" alt="Python">
  </a>
  <a href="https://playwright.dev/python/" target="_blank">
    <img src="https://img.shields.io/badge/Automation-Playwright-orange?style=flat-square" alt="Playwright">
  </a>
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square" alt="License">
</p>

<p align="center">
  <b>English</b> | <a href="#中文介绍">中文</a>
</p>

---

## English

A browser/HTTP automation assistant that helps users automatically complete repetitive clicking and ordering processes on the [GLM Subscription](https://bigmodel.cn/glm-coding) page, reducing manual operations. Built with **Python + Playwright** (QR code login + browser automation) + **httpx** (optional API automation) + **NTP time synchronization**.

> ⚠️ **Disclaimer**: This tool is an **automation assistant** only. It does NOT provide capabilities to bypass CAPTCHAs, reverse-engineer API signatures, break through platform risk controls, or perform any unauthorized access. All actual ordering, payment, and legal consequences are the sole responsibility of the user. Please read the full disclaimer before use.

### ✨ Features

- 🤖 **Browser Automation** — Automated clicking and form submission via Playwright
- ⏱️ **Precise Timing** — NTP time synchronization with ±10ms busy-wait precision
- 🔐 **Persistent Login** — One-time QR code login, reusable session state
- 🌐 **Optional HTTP API** — Direct API calls for faster response (requires manual packet capture)
- 🔔 **Smart Notifications** — Terminal alerts + optional WeChat Work / DingTalk webhooks
- 🧪 **Dry Run Mode** — Test the full workflow without placing actual orders

### 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browser (one-time, ~100MB)
python -m playwright install chromium

# 3. First-time QR code login
python login.py

# 4. Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your target time and plan keyword

# 5. Run (start 30-60s before trigger_time)
python auto_order.py

# Dry run (test without real order)
python auto_order.py --dry-run
```

### 📁 Project Structure

```
GLM-Subscription-Automation/
├── requirements.txt
├── config.example.yaml      # Configuration template
├── config.yaml              # Your config (gitignored)
├── login.py                 # QR login → data/storage_state.json
├── auto_order.py            # Main entry point
├── core/
│   ├── time_sync.py         # NTP sync + precise busy-wait
│   ├── browser_auto.py      # Browser automation path
│   ├── http_auto.py         # HTTP API automation path (optional)
│   └── notifier.py          # Terminal + webhook notifications
└── data/
    └── storage_state.json   # Login state (gitignored)
```

### ⚙️ Configuration Highlights

| Key | Description |
|-----|-------------|
| `trigger_time` | Target trigger time, e.g. `2026-06-18 12:00:00` |
| `target.plan_keyword` | Plan keyword to match, default `Lite` |
| `target.buy_button_texts` | Candidate button texts to click |
| `browser.headless` | Recommend `false` to handle CAPTCHA manually |
| `time_sync.enabled` | Strongly recommend `true` for NTP sync |
| `http_auto.enabled` | Enable direct API path (requires captured endpoint) |
| `notifier.*` | Optional webhook URLs for notifications |

### 📌 FAQ

**Q: Session expired?**  
A: Re-run `python login.py` to refresh cookies.

**Q: Button not found?**  
A: Update `target.buy_button_texts` and `target.plan_keyword` in `config.yaml` to match the actual page text.

**Q: CAPTCHA appears?**  
A: The tool will pause and alert you. Complete it manually in the browser window — the tool does NOT auto-bypass CAPTCHAs.

**Q: NTP sync fails?**  
A: Check firewall for UDP 123. Try alternative servers like `cn.ntp.org.cn` or disable `time_sync.enabled` (less precise).

---

<p align="center">
  <a href="#english">English</a> | <b>中文</b>
</p>

---

## 中文介绍

一个浏览器/HTTP 自动化辅助工具，帮助使用者自动完成 [GLM 订阅](https://bigmodel.cn/glm-coding) 页面中的重复性点击与下单流程，减少手动操作。基于 **Python + Playwright**（扫码登录 + 浏览器自动化）+ **httpx**（可选接口自动化）+ **NTP 时间对齐**实现。

> ⚠️ **免责声明**：本工具仅提供**自动化辅助功能**，**不提供**绕过验证码、逆向接口签名、突破网站风控或任何非授权访问的能力。所有实际下单、支付及法律后果均由使用者自行承担。使用前请务必阅读完整免责声明。

### ✨ 功能特性

- 🤖 **浏览器自动化** — 通过 Playwright 实现自动点击与表单提交
- ⏱️ **精确对时** — NTP 时间同步，忙等精度 ±10ms
- 🔐 **持久登录** — 一次性扫码登录，会话状态可复用
- 🌐 **可选 HTTP 接口** — 直接调用 API 提速（需手动抓包配置）
- 🔔 **智能通知** — 终端提醒 + 可选企业微信/钉钉 Webhook
- 🧪 **演练模式** — 完整流程测试，不触发真实下单

### 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器内核（一次性，约 100MB）
python -m playwright install chromium

# 3. 首次扫码登录
python login.py

# 4. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml，设置目标时间和套餐关键词

# 5. 运行（建议在 trigger_time 前 30~60 秒启动）
python auto_order.py

# 演练模式（测试流程，不真下单）
python auto_order.py --dry-run
```

### 📁 项目结构

```
GLM-Subscription-Automation/
├── requirements.txt
├── config.example.yaml      # 配置模板
├── config.yaml              # 你的实际配置（gitignore）
├── login.py                 # 扫码登录，生成 data/storage_state.json
├── auto_order.py            # 主入口
├── core/
│   ├── time_sync.py         # NTP 对齐 + 精确忙等
│   ├── browser_auto.py      # 浏览器自动化路径
│   ├── http_auto.py         # 接口自动化路径（可选）
│   └── notifier.py          # 终端 + webhook 通知
└── data/
    └── storage_state.json   # 登录态（gitignore）
```

### ⚙️ 配置说明

| 字段 | 说明 |
|-----|------|
| `trigger_time` | 目标触发时间，如 `2026-06-18 12:00:00` |
| `target.plan_keyword` | 套餐关键词，默认 `Lite` |
| `target.buy_button_texts` | 购买按钮文案候选，命中其一即点击 |
| `browser.headless` | 建议 `false`，保留窗口便于处理验证码 |
| `time_sync.enabled` | 强烈建议 `true`，启用 NTP 对时 |
| `http_auto.enabled` | 启用接口自动化路径（需配置抓包接口） |
| `notifier.*` | 可选通知 Webhook 地址 |

### 📌 常见问题

**Q: 运行时提示未登录？**  
A: Cookie 过期，重新执行 `python login.py` 即可。

**Q: 点击不到购买按钮？**  
A: 多半是文案变了。修改 `config.yaml` 中 `target.buy_button_texts` 和 `target.plan_keyword`，与页面实际显示保持一致，无需改代码。

**Q: 跳出滑块验证码怎么办？**  
A: 工具会响铃并暂停，在浏览器窗口手动完成即可，工具会继续。**本工具不自动绕过验证码。**

**Q: 报 NTP 对齐失败？**  
A: 通常是防火墙拦截 UDP 123。更换 `ntp_server`（如 `cn.ntp.org.cn`），或在配置中将 `time_sync.enabled` 设为 `false`（精度依赖本地时钟）。

---

## ⚠️ 免责声明 / Disclaimer

**中文**：本工具仅为自动化辅助工具，所有实际下单、支付及由此产生的法律效果，均由使用者本人承担。使用者应确保行为符合目标网站用户协议及所在地区法律法规。因使用本工具产生的一切法律风险与后果，由使用者自行承担。不得用于批量抢购倒卖、破坏公平机制、规避付费或任何违法违规目的。

**English**: This tool is provided as an automation assistant only. All actual ordering, payment, and resulting legal effects are the sole responsibility of the user. Users must ensure compliance with the target platform's terms of service and all applicable laws. The author assumes no liability for any legal risks or consequences arising from use. This tool must not be used for bulk scalping, disrupting fair mechanisms, evading payments, or any illegal purposes.

---

<p align="center">
  Happy automating 🚀
</p>
