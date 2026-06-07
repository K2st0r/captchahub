<div align="center">

# CaptchaHub

**Enterprise CAPTCHA Recognition Platform**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.1.0-purple.svg)](https://github.com/K2st0r/captchahub/releases)
[![Donate](https://img.shields.io/badge/Donate-USDT-red.svg)](#donate)

</div>

---

## Table of Contents

- [English](#english)
  - [What is CaptchaHub?](#what-is-captchahub)
  - [Features](#features)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [API Reference](#api-reference)
  - [Configuration](#configuration)
  - [Screenshots](#screenshots)
- [中文](#chinese)
  - [概述](#概述)
  - [功能特性](#功能特性)
  - [安装](#安装)
  - [快速开始](#快速开始)
  - [API 文档](#api-文档)
  - [配置说明](#配置说明)
- [Donate / 打赏](#donate--打赏)
- [License](#license)

---

## 📡 Live API Service

CaptchaHub is running 24/7 as a **paid API service**:

| Tier     | Price    | Daily Limit | Try It                                                                  |
|----------|----------|-------------|-------------------------------------------------------------------------|
| **Free** | $0       | 100 req     | `curl https://suse-collar-rats-foot.trycloudflare.com/api/v1/health`    |
| **Pro**  | **$10/mo** | 10,000 req  | Buy: k2st0r@users.noreply.github.com                                    |
| **Unlimited** | **$50/mo** | Unlimited | Buy: k2st0r@users.noreply.github.com                                    |

```bash
# Test the live API
curl https://suse-collar-rats-foot.trycloudflare.com/api/v1/health

# Check your usage (anonymous = Free tier)
curl https://suse-collar-rats-foot.trycloudflare.com/api/v1/usage

# With a Pro API key
curl -H "X-API-Key: sk_pro_YOUR_KEY" https://suse-collar-rats-foot.trycloudflare.com/api/v1/usage
```

**Pay with USDT (ERC20):** `0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697`

---

## English

### What is CaptchaHub?

CaptchaHub is an **enterprise-grade CAPTCHA recognition platform** built on Flask and [ddddocr](https://github.com/sml2h3/ddddocr). It provides:

- A **web dashboard** with real-time monitoring
- A **RESTful API** for programmatic access
- **OCR recognition** for digits, letters, and Chinese characters
- **Slide captcha** gap detection
- Request logging with daily statistics

Whether you're automating form submissions, testing CAPTCHA services, or building an anti-bot research pipeline, CaptchaHub gives you a clean, production-ready API.

### Features

| Category | Description |
|----------|-------------|
| **OCR Recognition** | Digits, letters, and Chinese characters — two models (standard / beta) |
| **Slide Detection** | Auto-detect the gap position in slider CAPTCHAs |
| **Web Dashboard** | Real-time stats: total requests, success rate, avg latency, uptime |
| **Live Testing** | Paste base64 image data directly in the browser to test |
| **Batch Processing** | Submit up to 100 images per request |
| **File Upload** | Multipart/form-data upload endpoint |
| **Request Logging** | SQLite-backed log with daily-aggregated statistics |
| **CORS** | Pre-configured for cross-origin access |
| **Optional Auth** | API key authentication via environment variable |

### Installation

```bash
# Clone the repository
git clone https://github.com/K2st0r/captchahub.git
cd captchahub

# Install dependencies
pip install -r requirements.txt

# Or install manually
pip install ddddocr pillow flask flask-cors
```

### Quick Start

```bash
python captchahub.py
```

Open your browser at **http://localhost:9527** — you'll see the dashboard.

Try the API directly:

```bash
# Health check
curl http://localhost:9527/health

# Recognize a captcha (replace with actual base64)
curl -X POST http://localhost:9527/api/v1/recognize \
  -H "Content-Type: application/json" \
  -d '{"image": "base64_image_data_here"}'

# Upload an image file
curl -X POST http://localhost:9527/api/v1/upload \
  -F "file=@captcha.png"

# Batch recognition
curl -X POST http://localhost:9527/api/v1/batch \
  -H "Content-Type: application/json" \
  -d '{"images": ["base64_1", "base64_2", "base64_3"]}'
```

### API Reference

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| `GET` | `/health` | Health check | — |
| `GET` | `/api/v1/stats` | Platform statistics | — |
| `POST` | `/api/v1/recognize` | Single CAPTCHA recognition | `image` (base64), `mode` (beta/standard) |
| `POST` | `/api/v1/slide` | Slide gap detection | `background` (base64), `slice` (base64) |
| `POST` | `/api/v1/batch` | Batch recognition (max 100) | `images` (base64[]), `mode` |
| `POST` | `/api/v1/upload` | File upload recognition | `file` (multipart), `mode` (form field) |

#### Response Format

```json
// OCR — success
{
  "success": true,
  "result": "AB3D",
  "time_ms": 45.2
}

// OCR — failure
{
  "success": false,
  "error": "Invalid base64 data"
}

// Slide — success
{
  "success": true,
  "target": [120, 0, 60, 60]
}

// Stats
{
  "version": "2.1.0",
  "started_at": "2026-06-06T16:00:00",
  "total_requests": 1523,
  "success_count": 1487,
  "fail_count": 36,
  "avg_time_ms": 42.3,
  "today": {
    "total_requests": 230,
    "success_count": 225,
    "fail_count": 5
  },
  "server_time": "2026-06-06T18:00:00"
}
```

### Configuration

```bash
# Custom port (default: 9527)
PORT=8080 python captchahub.py

# Enable API key authentication
CAPTCHAHUB_KEYS=sk-abc123,sk-xyz789 python captchahub.py

# Then include the key in requests:
curl -H "X-API-Key: sk-abc123" http://localhost:9527/api/v1/recognize -d '{"image":"..."}'
```

---

## 中文

### 概述

CaptchaHub 是一个基于 Flask + ddddocr 的**企业级验证码识别平台**。提供：

- **Web 管理后台**，实时显示请求量、成功率、平均耗时
- **RESTful API**，方便程序调用
- **OCR 识别**：数字、字母、中文验证码
- **滑块检测**：自动识别滑块验证码缺口位置
- **请求日志**：SQLite 存储，按日统计

### 功能特性

| 类别 | 说明 |
|------|------|
| **OCR 识别** | 支持数字、字母、中文，提供标准/Beta 两种模型 |
| **滑块检测** | 自动定位滑块验证码缺口坐标 |
| **Web 后台** | 实时仪表盘，请求量/成功率/平均耗时/运行时间 |
| **在线测试** | 浏览器直接粘贴 base64 图片即可测试 |
| **批量处理** | 单次最多 100 张图片 |
| **文件上传** | 支持 multipart/form-data 上传 |
| **请求日志** | SQLite 记录每次请求，按日汇总统计 |
| **跨域支持** | 预配置 CORS，可从任何前端调用 |
| **可选认证** | 通过环境变量开启 API Key 校验 |

### 安装

```bash
git clone https://github.com/K2st0r/captchahub.git
cd captchahub
pip install -r requirements.txt
```

或手动安装依赖：

```bash
pip install ddddocr pillow flask flask-cors
```

### 快速开始

```bash
python captchahub.py
```

浏览器打开 **http://localhost:9527** 即可看到管理后台。

API 调用示例：

```bash
# 健康检查
curl http://localhost:9527/health

# 识别验证码
curl -X POST http://localhost:9527/api/v1/recognize \
  -H "Content-Type: application/json" \
  -d '{"image": "base64编码的图片数据"}'

# 上传图片文件
curl -X POST http://localhost:9527/api/v1/upload \
  -F "file=@captcha.png"

# 批量识别
curl -X POST http://localhost:9527/api/v1/batch \
  -H "Content-Type: application/json" \
  -d '{"images": ["base64_1", "base64_2", "base64_3"]}'

# 滑块检测
curl -X POST http://localhost:9527/api/v1/slide \
  -H "Content-Type: application/json" \
  -d '{"background": "base64背景图", "slice": "base64滑块图"}'
```

### API 文档

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| `GET` | `/health` | 健康检查 | 无 |
| `GET` | `/api/v1/stats` | 平台统计 | 无 |
| `POST` | `/api/v1/recognize` | 单张验证码识别 | `image` (base64), `mode` (beta/standard) |
| `POST` | `/api/v1/slide` | 滑块缺口检测 | `background` (base64), `slice` (base64) |
| `POST` | `/api/v1/batch` | 批量识别（最多100张） | `images` (base64数组), `mode` |
| `POST` | `/api/v1/upload` | 文件上传识别 | `file` (multipart), `mode` (form字段) |

### 配置说明

```bash
# 自定义端口
PORT=8080 python captchahub.py

# 启用 API Key 认证
CAPTCHAHUB_KEYS=sk-abc123,sk-xyz789 python captchahub.py

# 调用时携带 Key
curl -H "X-API-Key: sk-abc123" http://localhost:9527/api/v1/recognize -d '{"image":"..."}'
```

---

## Donate / 打赏

如果这个项目帮到了您，欢迎打赏支持！

If this project helps you, please consider supporting:

<div align="center">
<img src="https://raw.githubusercontent.com/K2st0r/captchahub/main/static/zan.png" width="200" alt="WeChat Pay">

📱 微信扫码赞赏

**USDT (ERC20):** `0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697`

</div>

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Made with ❤️ by [K2st0r](https://github.com/K2st0r)
