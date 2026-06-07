#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
CaptchaHub v2.1 — Enterprise CAPTCHA Recognition Platform
   企业级验证码识别平台
=============================================================
Category:   Web Application (Flask)
License:    MIT
Donate:     0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697 (ETH/USDT)
=============================================================
Features:
  - OCR recognition (digits, letters, Chinese characters)
  - Slide captcha gap detection
  - Web dashboard with real-time monitoring
  - RESTful API with JSON responses
  - SQLite request logging + daily statistics
  - File upload support (multipart/form-data)
  - Batch processing (up to 100 images/request)
  - CORS support for cross-origin requests
  - Optional API key authentication
  - Graceful error handling throughout
=============================================================
"""
import os, sys, json, time, base64, sqlite3, logging
from datetime import datetime
from pathlib import Path
from functools import wraps
from typing import Dict, List, Optional, Tuple, Union

import ddddocr
from flask import Flask, request, jsonify, render_template_string, send_from_directory, g
from flask_cors import CORS

# ─── Pricing / Monetization ────────────────────────────
# "free"   — 100 req/day, no API key needed
# "pro"    — 10,000 req/day, needs API key
# "unlimited" — no limit, needs API key
# Set CAPTCHAHUB_PLANS={"sk_pro":"pro","sk_unl":"unlimited"} in env
# Each tier's daily limit is enforced by the rate limiter below.

PLANS = {
    "free":      {"daily_limit": 100,   "price_usdt": 0,   "label": "Free"},
    "pro":       {"daily_limit": 10000, "price_usdt": 10,  "label": "Pro"},
    "unlimited": {"daily_limit": 0,     "price_usdt": 50,  "label": "Unlimited"},
}

# ─── Metadata ───────────────────────────────────────────────
__version__ = "2.2.0"
__author__  = "K2st0r"
__license__ = "MIT"
__wallet__  = "0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697"

# ─── App Initialization ─────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

WORK_DIR = Path(__file__).resolve().parent
STATIC_DIR = WORK_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("captchahub")

# ─── Database ───────────────────────────────────────────────
DB_PATH = WORK_DIR / "captchahub.db"

def get_db() -> sqlite3.Connection:
    """Return a thread-safe database connection."""
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db() -> None:
    """Create database tables if they don't exist."""
    db = sqlite3.connect(str(DB_PATH))
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            endpoint      TEXT    NOT NULL,
            method        TEXT    NOT NULL DEFAULT 'POST',
            success       INTEGER NOT NULL DEFAULT 1,
            result        TEXT,
            time_ms       REAL,
            ip            TEXT,
            api_identity  TEXT    DEFAULT 'anonymous'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id    TEXT PRIMARY KEY,
            plan      TEXT NOT NULL DEFAULT 'pro',
            owner     TEXT DEFAULT '',
            created   TEXT NOT NULL,
            enabled   INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date           TEXT PRIMARY KEY,
            total_requests INTEGER DEFAULT 0,
            success_count  INTEGER DEFAULT 0,
            fail_count     INTEGER DEFAULT 0,
            avg_time_ms    REAL    DEFAULT 0
        )
    """)
    db.commit()
    db.close()
    log.info("Database initialized at %s", DB_PATH)

def record_request(endpoint: str, method: str, success: bool,
                   result: str, time_ms: float, ip: str) -> None:
    """Log a single API request to the database."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        cursor = db.cursor()
        now = datetime.now()
        identity = request.headers.get("X-API-Key") or request.args.get("api_key") or ip
    cursor.execute(
        "INSERT INTO request_log (timestamp, endpoint, method, success, result, time_ms, ip, api_identity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (now.isoformat(), endpoint, method, int(success),
         str(result)[:200], time_ms, ip, identity)
    )
        today = now.strftime("%Y-%m-%d")
        cursor.execute(
            """INSERT INTO daily_stats (date, total_requests, success_count, fail_count, avg_time_ms)
               VALUES (?, 1, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                 total_requests = total_requests + 1,
                 success_count  = success_count  + ?,
                 fail_count     = fail_count     + ?,
                 avg_time_ms    = (avg_time_ms * total_requests + ?) / (total_requests + 1)""",
            (today, int(success), int(not success), time_ms,
             int(success), int(not success), time_ms)
        )
        db.commit()
        db.close()
    except Exception as exc:
        log.warning("Failed to record request: %s", exc)

init_db()

# ─── Authentication (optional) ──────────────────────────────
API_KEYS: Dict[str, str] = {}  # key -> plan (pro|unlimited)
_env_keys = os.environ.get("CAPTCHAHUB_KEYS", "")
_env_plans = os.environ.get("CAPTCHAHUB_PLANS", "")
if _env_keys:
    for k in _env_keys.split(","):
        k = k.strip()
        if k:
            API_KEYS[k] = "pro"  # default plan
if _env_plans:
    try:
        parsed = json.loads(_env_plans)
        if isinstance(parsed, dict):
            API_KEYS.update(parsed)
    except json.JSONDecodeError:
        log.warning("Invalid CAPTCHAHUB_PLANS JSON, using defaults")

def get_key_info():
    """Return (api_key, plan) for the current request, or (None, 'free') if no key."""
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if key and key in API_KEYS:
        return key, API_KEYS[key]
    return None, "free"

def rate_limited(f):
    """Decorator: enforce daily rate limit per API key / IP."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key, plan = get_key_info()
        plan_cfg = PLANS.get(plan, PLANS["free"])
        limit = plan_cfg["daily_limit"]
        if limit == 0:  # unlimited
            return f(*args, **kwargs)
        # Count today's usage (key-based if available, else IP-based)
        identity = key or request.remote_addr or "unknown"
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            db = sqlite3.connect(str(DB_PATH))
            row = db.execute(
                "SELECT COUNT(*) as cnt FROM request_log WHERE date(api_identity)=? AND api_identity=?",
                (today, identity)
            ).fetchone()
            count = row[0] if row else 0
            db.close()
        except Exception:
            count = 0
        if count >= limit:
            retry = datetime.now().replace(hour=23, minute=59, second=59)
            reset_utc = int(retry.timestamp())
            return jsonify({
                "success": False,
                "error": f"Daily limit reached ({limit}/day). Upgrade at /pricing",
                "plan": plan,
                "used_today": count,
                "limit": limit,
                "resets_at": reset_utc,
            }), 429
        return f(*args, **kwargs)
    return decorated

def require_auth(f):
    """Decorator: enforce API key authentication if configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key, plan = get_key_info()
        if not API_KEYS:
            return f(*args, **kwargs)
        if key and key in API_KEYS:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Valid API key required. Get one at /pricing"}), 401
    return decorated

# ─── OCR Engine ─────────────────────────────────────────────
class OCREngine:
    """
    Core CAPTCHA recognition engine backed by ddddocr.

    Provides two recognition modes:
      - ``standard`` — faster, good for simple captchas
      - ``beta``     — more accurate on complex/noisy captchas

    Also supports slide-captcha gap detection via ``slide_match``.
    """

    def __init__(self) -> None:
        self._ocr_standard = ddddocr.DdddOcr(show_ad=False)
        self._ocr_beta     = ddddocr.DdddOcr(show_ad=False, beta=True)
        self._detector     = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)

    # ── public stats (read with /api/v1/stats) ──────────
    @property
    def stats(self) -> Dict:
        return {
            "version":        __version__,
            "started_at":     self._started_at,
            "total_requests": self._total,
            "success_count":  self._success,
            "fail_count":     self._fail,
            "avg_time_ms":    round(self._avg, 1),
        }

    _started_at: str = datetime.now().isoformat()
    _total:   int = 0
    _success: int = 0
    _fail:    int = 0
    _avg:    float = 0.0

    # ── helpers ─────────────────────────────────────────
    @staticmethod
    def _decode(image_data: str) -> bytes:
        """Decode base64 (optionally with ``data:…;base64,`` prefix) to raw bytes."""
        if image_data.startswith("data:"):
            image_data = image_data.split("base64,", 1)[-1]
        return base64.b64decode(image_data)

    def _update_stats(self, success: bool, elapsed_ms: float) -> None:
        self._total += 1
        if success:
            self._success += 1
        else:
            self._fail += 1
        n = self._total
        self._avg = ((self._avg * (n - 1)) + elapsed_ms) / n if n > 1 else elapsed_ms

    # ── public API ──────────────────────────────────────
    def recognize(self, image_data: str, mode: str = "beta") -> Dict:
        """
        Perform OCR on a single CAPTCHA image.

        Args:
            image_data: Base64-encoded image (with or without data URI prefix).
            mode: ``"beta"`` (default, better accuracy) or ``"standard"``.

        Returns:
            ``{"success": bool, "result": str, "time_ms": float}``
        """
        t0 = time.perf_counter()
        try:
            img = self._decode(image_data)
            ocr = self._ocr_beta if mode == "beta" else self._ocr_standard
            text = (ocr.classification(img) or "").strip()
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            self._update_stats(False, elapsed)
            return {"success": False, "error": str(exc)}

        elapsed = (time.perf_counter() - t0) * 1000
        self._update_stats(bool(text), elapsed)
        return {"success": bool(text), "result": text, "time_ms": round(elapsed, 1)}

    def slide_detect(self, bg_data: str, slice_data: str) -> Dict:
        """
        Detect the gap position in a slide captcha.

        Args:
            bg_data:    Base64-encoded background image (with notch).
            slice_data: Base64-encoded slider piece image.

        Returns:
            ``{"success": True, "target": [x, y, w, h]}`` or ``{"success": False, "error": …}``
        """
        try:
            bg = self._decode(bg_data)
            sl = self._decode(slice_data)
            result = self._detector.slide_match(sl, bg, simple_target=True)
            return {"success": True, "target": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


engine = OCREngine()

# ─── Dashboard HTML ─────────────────────────────────────────
# Inline template kept for zero-dependency deployment.
# For production, consider extracting to a Jinja2 file.
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CaptchaHub – 验证码识别平台</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#c9d1d9;--muted:#8b949e;--blue:#58a6ff;--green:#3fb950;--purple:#d2a8ff;--orange:#d29922}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--fg);padding:24px}
.container{max-width:1080px;margin:0 auto}
/* header */
.hdr{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:28px}
.hdr h1{font-size:30px;background:linear-gradient(135deg,var(--blue),var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hdr .tag{display:inline-block;background:#1f6feb33;color:var(--blue);padding:2px 12px;border-radius:99px;font-size:12px;font-weight:600;margin-left:8px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.badge{font-size:10px;padding:2px 8px;border-radius:99px;font-weight:600}
.badge.py{background:#1f6feb22;color:var(--blue)}.badge.mit{background:#3fb95022;color:var(--green)}.badge.flask{background:#d2a8ff22;color:var(--purple)}
.wallet{font-size:11px;color:var(--muted)}.wallet code{color:var(--purple)}.wallet a{color:var(--green);text-decoration:none}.wallet a:hover{text-decoration:underline}
/* stats */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:18px;text-align:center}
.card .num{font-size:32px;font-weight:800}
.card .lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.card.b{box-shadow:inset 3px 0 0 var(--blue)}.card.b .num{color:var(--blue)}
.card.g{box-shadow:inset 3px 0 0 var(--green)}.card.g .num{color:var(--green)}
.card.p{box-shadow:inset 3px 0 0 var(--purple)}.card.p .num{color:var(--purple)}
.card.o{box-shadow:inset 3px 0 0 var(--orange)}.card.o .num{color:var(--orange)}
/* sections */
.sec{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:22px;margin-bottom:20px}
.sec h2{font-size:16px;margin-bottom:14px;display:flex;align-items:center;gap:6px}
.sec h2::before{content:'';display:inline-block;width:4px;height:16px;background:var(--blue);border-radius:2px}
/* endpoints */
.eps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
.ep{background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px}
.ep .m{display:inline-block;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:700;margin-right:6px;text-transform:uppercase}
.ep .m.post{background:#1f6feb33;color:var(--blue)}.ep .m.get{background:#3fb95033;color:var(--green)}
.ep .path{font-family:monospace;font-size:12px}
.ep .desc{font-size:11px;color:var(--muted);margin-top:4px}
/* try */
.try textarea{width:100%;height:76px;background:var(--bg);border:1px solid var(--bd);border-radius:8px;color:var(--fg);padding:10px;font-family:monospace;font-size:12px;resize:vertical}
.try textarea:focus{outline:none;border-color:var(--blue)}
.try .btns{margin-top:8px;display:flex;gap:8px;flex-wrap:wrap}
.try button{background:#238636;color:#fff;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600}.try button:hover{background:#2ea043}
.try button.btn2{background:#30363d}.try button.btn2:hover{background:#484f58}
.try .out{background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px;margin-top:10px;font-family:monospace;font-size:12px;min-height:44px;white-space:pre-wrap;word-break:break-all}
/* pricing */
.pricing-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0}
.pcard{background:var(--bg);border:1px solid var(--bd);border-radius:12px;padding:20px;text-align:center;position:relative}
.pcard:hover{border-color:var(--blue)}
.pcard.pro{border-color:var(--green);box-shadow:0 0 20px rgba(63,185,80,.15)}
.pcard .pop{position:absolute;top:-8px;left:50%;transform:translateX(-50%);background:var(--green);color:#000;font-size:9px;font-weight:800;padding:2px 12px;border-radius:99px;letter-spacing:1px}
.pcard h3{font-size:14px;margin-bottom:8px}
.pcard .price .amt{font-size:28px;font-weight:800;color:var(--fg)}
.pcard .price .per{font-size:11px;color:var(--muted)}
.pcard ul{list-style:none;margin:12px 0;padding:0;font-size:12px}
.pcard ul li{padding:4px 0;color:var(--fg2)}
.pcard ul li::before{content:'✓ ';color:var(--green)}
.buy-btn{background:linear-gradient(135deg,var(--green),#2ea043);color:#000;border:none;padding:10px 28px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700}
.buy-btn:hover{opacity:.9}
/* donate */
.donate{text-align:center}
.donate img{max-width:200px;border-radius:12px;margin:8px 0;border:2px solid var(--bd)}
.donate .hint{font-size:12px;color:var(--muted)}
/* footer */
.ft{text-align:center;color:#484f58;font-size:11px;margin-top:24px;padding-top:18px;border-top:1px solid var(--bd)}
.ft a{color:var(--blue)}
@media(max-width:600px){body{padding:10px}.stats{grid-template-columns:1fr 1fr}.card .num{font-size:24px}}
</style>
</head>
<body>
<div class="container">
<div class="hdr">
<div>
<h1>CaptchaHub<span class="tag">v2.1.0</span></h1>
<div class="badges"><span class="badge py">Python</span><span class="badge flask">Flask</span><span class="badge mit">MIT</span></div>
</div>
<div class="wallet">Donate: <code>0xAfe9B67B…f26697</code> (USDT/ERC20) | <a href="#pricing" style="color:var(--green)">Pricing</a></div>
</div>

<div class="stats">
<div class="card b"><div class="num" id="s_total">0</div><div class="lbl">Total Requests</div></div>
<div class="card g"><div class="num" id="s_rate">0%</div><div class="lbl">Success Rate</div></div>
<div class="card p"><div class="num" id="s_avg">0ms</div><div class="lbl">Avg Response</div></div>
<div class="card o"><div class="num" id="s_uptime">0h</div><div class="lbl">Uptime</div></div>
</div>

<div class="sec">
<h2>API Endpoints</h2>
<div class="eps">
<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/recognize</span><div class="desc">CAPTCHA recognition</div></div>
<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/slide</span><div class="desc">Slide gap detection</div></div>
<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/batch</span><div class="desc">Batch (max 100)</div></div>
<div class="ep"><span class="m post">POST</span><span class="path">/api/v1/upload</span><div class="desc">File upload</div></div>
<div class="ep"><span class="m get">GET</span><span class="path">/api/v1/stats</span><div class="desc">Statistics</div></div>
<div class="ep"><span class="m get">GET</span><span class="path">/health</span><div class="desc">Health check</div></div>
</div>
</div>

<div class="sec" id="pricing">
<h2>Pricing / 定价</h2>
<div class="pricing-cards" id="pricing-cards">
<div class="pcard free">
<h3>Free</h3>
<div class="price"><span class="amt">$0</span> <span class="per">/month</span></div>
<ul>
<li>100 requests/day</li>
<li>No API key needed</li>
<li>Basic OCR support</li>
</ul>
</div>
<div class="pcard pro">
<div class="pop">POPULAR</div>
<h3>Pro</h3>
<div class="price"><span class="amt">$10</span> <span class="per">/month</span></div>
<ul>
<li>10,000 requests/day</li>
<li>API key access</li>
<li>Batch processing</li>
<li>Priority support</li>
</ul>
</div>
<div class="pcard unl">
<h3>Unlimited</h3>
<div class="price"><span class="amt">$50</span> <span class="per">/month</span></div>
<ul>
<li>Unlimited requests</li>
<li>API key access</li>
<li>All features</li>
<li>24/7 support</li>
</ul>
</div>
</div>
<div class="usage-info" id="usage-info" style="text-align:center;margin-top:16px;font-size:13px;color:var(--muted)">
Checking usage...
</div>
<div style="text-align:center;margin-top:10px">
<button class="buy-btn" onclick="contactBuy()">Buy Pro / 购买 &rarr;</button>
</div>
</div>

<div class="sec try">
<h2>Quick Test</h2>
<textarea id="in" placeholder="Paste base64 image data (or data:image/…;base64,…)"></textarea>
<div class="btns">
<button onclick="test()">Recognize</button>
<button class="btn2" onclick="clearTest()">Clear</button>
</div>
<div class="out" id="out">Waiting for input…</div>
</div>

<div class="sec donate">
<h2>Support This Project</h2>
<img src="/static/zan.png" alt="WeChat Pay QR" onerror="this.style.display='none'">
<div class="hint">WeChat Pay · USDT (ERC20): 0xAfe9B67B1DF618FAeD32dC71E3458cf549f26697</div>
</div>

<div class="ft">
Powered by <a href="https://github.com/K2st0r/captchahub">CaptchaHub</a> — MIT License
</div>
</div>
<script>
async function refresh(){
 try{
  const r=await fetch('/api/v1/stats');const d=await r.json();
  document.getElementById('s_total').textContent=d.total_requests||0;
  const rate=d.total_requests?Math.round(d.success_count/d.total_requests*100):0;
  document.getElementById('s_rate').textContent=rate+'%';
  document.getElementById('s_avg').textContent=(d.avg_time_ms||0).toFixed(1)+'ms';
  const h=((Date.now()-new Date(d.started_at))/36e5).toFixed(1);
  document.getElementById('s_uptime').textContent=h+'h';
 }catch(e){}
}
setInterval(refresh,3000);refresh();
async function test(){
 const v=document.getElementById('in').value.trim();
 if(!v){document.getElementById('out').textContent='Please paste base64 image data';return}
 document.getElementById('out').textContent='Recognizing…';
 try{
  const r=await fetch('/api/v1/recognize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:v})});
  document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);
 }catch(e){document.getElementById('out').textContent='Error: '+e.message}
}
function clearTest(){document.getElementById('in').value='';document.getElementById('out').textContent='Waiting for input…'}
function contactBuy(){window.location.href='mailto:k2st0r@users.noreply.github.com?subject=CaptchaHub%20Pro%20Purchase&body=I%20want%20to%20buy%20a%20Pro%20or%20Unlimited%20plan.%20My%20preferred%20payment%20is%20USDT(ERC20).';}
async function checkUsage(){try{const r=await fetch('/api/v1/usage');const d=await r.json();const e=document.getElementById('usage-info');if(d.api_key){e.innerHTML='<span style="color:var(--green)">✔ Plan: <b>'+d.plan+'</b> &middot; Used: '+d.used_today+'/'+(d.limit||'∞')+' today</span>';}else{e.innerHTML='<span style="color:var(--blue)">ℹ Free tier: '+d.used_today+'/'+d.limit+' requests used today. <a href="#pricing" style="color:var(--green)">Upgrade</a> for more.</span>'}}catch(e){}}
setInterval(checkUsage,5000);checkUsage();
</script>
</body>
</html>"""

# ─── Routes ─────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the web dashboard."""
    return render_template_string(DASHBOARD_HTML)

@app.route("/health")
def health():
    """Health-check endpoint."""
    return jsonify({
        "status": "ok",
        "version": __version__,
        "uptime_s": round(
            (datetime.now() - datetime.fromisoformat(engine._started_at)).total_seconds(), 1
        )
    })

@app.route("/static/<path:filename>")
def static_files(filename: str):
    """Serve static assets (QR image, etc.)."""
    return send_from_directory(str(STATIC_DIR), filename)

# ── API v1 ──────────────────────────────────────────────

@app.route("/api/v1/recognize", methods=["POST"])
@rate_limited
@require_auth
def api_recognize():
    """
    POST /api/v1/recognize

    Request JSON:
        {"image": "<base64>", "mode": "beta|standard"}

    Response:
        {"success": true, "result": "AB3D", "time_ms": 45.2}
    """
    data: Dict = request.get_json(silent=True) or {}
    image = data.get("image", "")
    if not image:
        return jsonify({"success": False, "error": "Missing 'image' field (base64 or data URI)"}), 400
    mode = data.get("mode", "beta")
    result = engine.recognize(image, mode=mode)
    record_request("/api/v1/recognize", "POST",
                   result.get("success", False),
                   result.get("result", result.get("error", "")),
                   result.get("time_ms", 0),
                   request.remote_addr or "unknown")
    return jsonify(result)

@app.route("/api/v1/upload", methods=["POST"])
def api_upload():
    """
    POST /api/v1/upload

    Accepts multipart/form-data with field ``file``.
    Optional form field ``mode`` (beta|standard).
    """
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Missing file"}), 400
    try:
        img_bytes = file.read()
        img_b64 = base64.b64encode(img_bytes).decode()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    mode = request.form.get("mode", "beta")
    result = engine.recognize(img_b64, mode=mode)
    record_request("/api/v1/upload", "POST",
                   result.get("success", False),
                   result.get("result", result.get("error", "")),
                   result.get("time_ms", 0),
                   request.remote_addr or "unknown")
    return jsonify(result)

@app.route("/api/v1/slide", methods=["POST"])
def api_slide():
    """
    POST /api/v1/slide

    Request JSON:
        {"background": "<base64>", "slice": "<base64>"}

    Response:
        {"success": true, "target": [x, y, w, h]}
    """
    data: Dict = request.get_json(silent=True) or {}
    bg = data.get("background", "")
    sl = data.get("slice", "")
    if not bg or not sl:
        return jsonify({"success": False, "error": "Missing 'background' and/or 'slice'"}), 400
    result = engine.slide_detect(bg, sl)
    return jsonify(result)

@app.route("/api/v1/batch", methods=["POST"])
@rate_limited
@require_auth
def api_batch():
    """
    POST /api/v1/batch

    Request JSON:
        {"images": ["<base64>", "<base64>", …], "mode": "beta"}

    Maximum 100 images per batch.
    """
    data: Dict = request.get_json(silent=True) or {}
    images: List[str] = data.get("images", [])
    if not images or not isinstance(images, list):
        return jsonify({"success": False, "error": "Missing 'images' array"}), 400
    if len(images) > 100:
        return jsonify({"success": False, "error": "Max 100 images per batch"}), 400

    mode = data.get("mode", "beta")
    results = [engine.recognize(img, mode=mode) for img in images]
    ok = sum(1 for r in results if r.get("success"))
    record_request("/api/v1/batch", "POST", True, f"{ok}/{len(results)}", 0, request.remote_addr or "unknown")
    return jsonify({"success": True, "count": len(results), "success_count": ok, "results": results})

@app.route("/pricing")
def pricing_page():
    """Redirect to dashboard pricing section."""
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/v1/usage")
def api_usage():
    """Return usage info for the current key/IP (used by dashboard UI)."""
    key, plan = get_key_info()
    plan_cfg = PLANS.get(plan, PLANS["free"])
    limit = plan_cfg["daily_limit"]
    identity = key or request.remote_addr or "unknown"
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        db = sqlite3.connect(str(DB_PATH))
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM request_log WHERE date(timestamp)=? AND api_identity=?",
            (today, identity)
        ).fetchone()
        count = row[0] if row else 0
        db.close()
    except Exception:
        count = 0
    return jsonify({
        "api_key": bool(key),
        "plan": plan,
        "used_today": count,
        "limit": limit if limit else "unlimited",
        "plan_label": plan_cfg["label"],
    })

@app.route("/api/v1/stats")
def api_stats():
    """Return platform statistics (global + today)."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        db = sqlite3.connect(str(DB_PATH))
        row = db.execute("SELECT * FROM daily_stats WHERE date = ?", (today,)).fetchone()
        db.close()
        today_stats = dict(row) if row else {"total_requests": 0, "success_count": 0, "fail_count": 0}
    except Exception:
        today_stats = {"total_requests": 0, "success_count": 0, "fail_count": 0}
    return jsonify({**engine.stats, "today": today_stats, "server_time": datetime.now().isoformat()})

# ─── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9527"))

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   CaptchaHub v{__version__:<44}║
║   Enterprise OCR + Premium Pricing                            ║
╠══════════════════════════════════════════════════════════════╣
║   Web:    http://0.0.0.0:{port:<39}║
║   API:    http://0.0.0.0:{port}/api/v1/recognize{'':<22}║
║   Stats:  http://0.0.0.0:{port}/api/v1/stats{'':<25}║
║   Usage:  http://0.0.0.0:{port}/api/v1/usage{'':<26}║
║   Health: http://0.0.0.0:{port}/health{'':<29}║
╠══════════════════════════════════════════════════════════════╣
║   Pricing: Free (100/d) | Pro $10/mo (10k/d) | Unlimited $50/mo ║
║   DB:     {str(DB_PATH):<47}║
║   License: MIT                                                ║
║   Buy:    k2st0r@users.noreply.github.com                     ║
║   Donate: {__wallet__}  ║
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
