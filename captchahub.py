#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
CaptchaHub v1.0 - 企业级验证码识别平台
=============================================================
功能: OCR识别 | 滑块识别 | 批量处理 | Web管理后台 | API服务
架构: Flask + ddddocr + RESTful API + Web Dashboard
打赏: 0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697 (ETH/USDT)
=============================================================
"""
import os, sys, json, time, base64, re, threading
from datetime import datetime
from io import BytesIO
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

__version__ = "1.0.0"
__wallet__ = "0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697"

# ─── Flask App ──────────────────────────────────────────────
from flask import Flask, request, jsonify, render_template_string, send_from_directory

app = Flask(__name__)

# ─── OCR Engine ────────────────────────────────────────────
class OCREngine:
    """验证码识别引擎"""
    def __init__(self):
        import ddddocr
        self.ocr_standard = ddddocr.DdddOcr(show_ad=False)
        self.ocr_beta = ddddocr.DdddOcr(show_ad=False, beta=True)
        self.detector = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
        self.stats = {
            "total_requests": 0,
            "success_count": 0,
            "fail_count": 0,
            "avg_time_ms": 0,
            "started_at": datetime.now().isoformat()
        }
    
    def decode_image(self, raw):
        if raw.startswith('data:'):
            raw = raw.split('base64,')[-1]
        return base64.b64decode(raw)
    
    def recognize(self, image_data, mode="beta"):
        t0 = time.time()
        try:
            img = self.decode_image(image_data)
            ocr = self.ocr_beta if mode == "beta" else self.ocr_standard
            result = ocr.classification(img)
            elapsed = (time.time() - t0) * 1000
            
            self.stats["total_requests"] += 1
            if result and result.strip():
                self.stats["success_count"] += 1
            else:
                self.stats["fail_count"] += 1
            
            n = self.stats["total_requests"]
            self.stats["avg_time_ms"] = (
                self.stats["avg_time_ms"] * (n-1) + elapsed
            ) / n if n > 1 else elapsed
            
            return {"success": True, "result": result.strip(), "time_ms": round(elapsed, 1)}
        except Exception as e:
            self.stats["total_requests"] += 1
            self.stats["fail_count"] += 1
            return {"success": False, "error": str(e)}
    
    def detect_slide(self, bg_data, slice_data):
        try:
            bg = self.decode_image(bg_data)
            sl = self.decode_image(slice_data)
            result = self.detector.slide_match(sl, bg, simple_target=True)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

engine = OCREngine()

# ─── Dashboard HTML ────────────────────────────────────────
# Add static file route
STATIC_DIR = Path(__file__).parent / 'static'

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(str(STATIC_DIR), filename)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CaptchaHub - 验证码识别平台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px}
.container{max-width:1000px;margin:0 auto}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}
.header h1{font-size:28px;background:linear-gradient(135deg,#58a6ff,#d2a8ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .wallet{font-size:12px;color:#8b949e}
.header .wallet span{color:#d2a8ff;font-family:monospace}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:30px}
.stat-card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;text-align:center}
.stat-card .num{font-size:32px;font-weight:700}
.stat-card .label{font-size:12px;color:#8b949e;margin-top:4px}
.stat-card.blue .num{color:#58a6ff}
.stat-card.green .num{color:#3fb950}
.stat-card.purple .num{color:#d2a8ff}
.stat-card.orange .num{color:#d29922}
.api-section{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px}
.api-section h2{font-size:16px;margin-bottom:15px}
.api-section code{display:block;background:#0d1117;padding:12px;border-radius:8px;font-size:13px;margin-bottom:10px;border:1px solid #30363d}
.endpoints{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.endpoint{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px}
.endpoint .method{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-right:8px}
.endpoint .method.post{background:#1f6feb33;color:#58a6ff}
.endpoint .method.get{background:#3fb95033;color:#3fb950}
.endpoint .path{font-family:monospace;font-size:13px}
.endpoint .desc{font-size:11px;color:#8b949e;margin-top:4px}
.footer{text-align:center;color:#484f58;font-size:12px;margin-top:30px}
.try-section{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px}
.try-section h2{font-size:16px;margin-bottom:15px}
.try-section textarea{width:100%;height:80px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#c9d1d9;padding:10px;font-family:monospace;font-size:12px;margin-bottom:10px}
.try-section button{background:#238636;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px}
.try-section button:hover{background:#2ea043}
.try-section .result{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px;margin-top:10px;font-family:monospace;font-size:13px;min-height:40px}
</style>
</head>
<body>
<div class="container">
<div class="header">
<div>
<h1>CaptchaHub</h1>
<div style="font-size:12px;color:#8b949e">企业级验证码识别平台</div>
</div>
<div class="wallet">
打赏: <span>0xAfe9B67B...f26697</span> (ETH/USDT)
</div>
</div>

<div class="stats-grid">
<div class="stat-card blue"><div class="num" id="totalReqs">0</div><div class="label">总请求</div></div>
<div class="stat-card green"><div class="num" id="successRate">0%</div><div class="label">成功率</div></div>
<div class="stat-card purple"><div class="num" id="avgTime">0ms</div><div class="label">平均耗时</div></div>
<div class="stat-card orange"><div class="num" id="uptime">0h</div><div class="label">运行时间</div></div>
</div>

<div class="api-section">
<h2>API 接口</h2>
<div class="endpoints">
<div class="endpoint">
<span class="method post">POST</span><span class="path">/api/v1/recognize</span>
<div class="desc">识别验证码</div>
</div>
<div class="endpoint">
<span class="method post">POST</span><span class="path">/api/v1/slide</span>
<div class="desc">滑块验证码检测</div>
</div>
<div class="endpoint">
<span class="method get">GET</span><span class="path">/api/v1/stats</span>
<div class="desc">平台统计</div>
</div>
<div class="endpoint">
<span class="method get">GET</span><span class="path">/health</span>
<div class="desc">健康检查</div>
</div>
</div>
</div>

<div class="try-section">
<h2>在线测试</h2>
<textarea id="inputImage" placeholder="粘贴base64图片数据或data:image/png;base64,..."></textarea>
<br>
<button onclick="testRecognize()">识别验证码</button>
<div class="result" id="resultBox">等待输入...</div>
</div>

<div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:20px;text-align:center">
<h2 style="font-size:16px;margin-bottom:10px">打赏支持</h2>
<p style="font-size:13px;color:#8b949e;margin-bottom:10px">如果这个工具帮到了您，欢迎打赏支持持续开发！</p>
<img src="/static/zan.png" style="max-width:200px;border-radius:8px;margin-bottom:10px" alt="赞赏码">
<p style="font-size:12px;color:#8b949e">USDT (ERC20): 0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697</p>
</div>

<div class="footer">
Powered by CaptchaHub
</div>
</div>

<script>
async function refreshStats() {
try {
const r = await fetch('/api/v1/stats');
const d = await r.json();
document.getElementById('totalReqs').textContent = d.total_requests || 0;
const rate = d.total_requests > 0 ? Math.round(d.success_count/d.total_requests*100) : 0;
document.getElementById('successRate').textContent = rate + '%';
document.getElementById('avgTime').textContent = (d.avg_time_ms||0).toFixed(1) + 'ms';
const hours = ((Date.now()-new Date(d.started_at).getTime())/3600000).toFixed(1);
document.getElementById('uptime').textContent = hours + 'h';
} catch(e) {}
}
setInterval(refreshStats, 3000);
refreshStats();

async function testRecognize() {
const img = document.getElementById('inputImage').value;
if(!img) { document.getElementById('resultBox').textContent = '请输入图片数据'; return; }
document.getElementById('resultBox').textContent = '识别中...';
try {
const r = await fetch('/api/v1/recognize', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:img})});
const d = await r.json();
document.getElementById('resultBox').textContent = JSON.stringify(d, null, 2);
} catch(e) {
document.getElementById('resultBox').textContent = 'Error: ' + e;
}
}
</script>
</body>
</html>
"""

# ─── Routes ─────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "version": __version__})

@app.route('/api/v1/recognize', methods=['POST'])
def api_recognize():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"success": False, "error": "Missing image field"}), 400
    result = engine.recognize(data['image'], mode=data.get('mode', 'beta'))
    return jsonify(result)

@app.route('/api/v1/slide', methods=['POST'])
def api_slide():
    data = request.get_json()
    if not data or 'background' not in data or 'slice' not in data:
        return jsonify({"success": False, "error": "Missing background/slice"}), 400
    result = engine.detect_slide(data['background'], data['slice'])
    return jsonify(result)

@app.route('/api/v1/stats')
def api_stats():
    return jsonify(engine.stats)

@app.route('/api/v1/batch', methods=['POST'])
def api_batch():
    data = request.get_json()
    if not data or 'images' not in data or not isinstance(data['images'], list):
        return jsonify({"success": False, "error": "Missing images list"}), 400
    results = []
    for img in data['images']:
        results.append(engine.recognize(img, mode=data.get('mode', 'beta')))
    return jsonify({"success": True, "results": results, "count": len(results)})

# ─── Main ───────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 9527))
    print(f'''
╔══════════════════════════════════════════════════╗
║         CaptchaHub v{__version__}                  ║
║     企业级验证码识别平台                          ║
╠══════════════════════════════════════════════════╣
║  Web:    http://0.0.0.0:{port}                  ║
║  API:    http://0.0.0.0:{port}/api/v1/recognize ║
║  Stats:  http://0.0.0.0:{port}/api/v1/stats     ║
║  Health: http://0.0.0.0:{port}/health            ║
╠══════════════════════════════════════════════════╣
║  打赏: {__wallet__}  ║
║  (ETH/USDT)                                      ║
╚══════════════════════════════════════════════════╝
    ''')
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
