# CaptchaHub

> 企业级验证码识别平台 | Enterprise CAPTCHA Recognition Platform

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- OCR: digits, letters, Chinese characters
- Slide captcha: gap detection
- Web dashboard: real-time monitoring + live test
- RESTful API: single/batch/slide
- Statistics: requests/success rate/avg time

## Quick Start

```bash
pip install ddddocr pillow flask
python captchahub.py
```

Open http://localhost:9527

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/recognize | OCR recognition |
| POST | /api/v1/slide | Slide detection |
| POST | /api/v1/batch | Batch processing |
| GET | /api/v1/stats | Platform stats |
| GET | /health | Health check |

## Donate

**USDT (ERC20):** `0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697`
