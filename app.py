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

# إعداد نظام التسجيل للأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY_HERE_CHANGE_THIS"

DB_FILE = "tracker_data.db"
USERNAME = "khaled"
PASSWORD = "ALG@2022"

# تعيين المنطقة الزمنية GMT+1 (توقيت الجزائر)
TIMEZONE = pytz.timezone('Africa/Algiers')

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
                FOREIGN KEY(link_id) REFERENCES links(id)
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
    """جلب وتخصيص البيانات الفوقية لكل منصة"""
    url_lower = url.lower()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        try:
            video_id = extract_video_id(url, "youtube")
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            res = requests.get(oembed_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                title = data.get('title', 'مقطع فيديو حصري')
                thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else data.get('thumbnail_url')
                return "YouTube", title, thumbnail
        except Exception as e:
            logger.error(f"YouTube metadata fetch error: {e}")
        return "YouTube", "شاهد مقطع الفيديو كاملاً", "https://images.unsplash.com/photo-1611162616305-c67b3fa40904?w=800"

    elif "tiktok.com" in url_lower:
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={url}"
            res = requests.get(oembed_url, headers=headers, timeout=4)
            if res.status_code == 200:
                data = res.json()
                title = data.get('title', 'فيديو رائج')
                return "TikTok", title, data.get('thumbnail_url')
        except Exception as e:
            logger.error(f"TikTok metadata fetch error: {e}")
        return "TikTok", "فيديو TikTok مميز", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"

    elif "instagram.com" in url_lower:
        return "Instagram", "Instagram Reel", "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=800"

    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "Facebook", "Facebook Watch", "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=800"

    return "Video", "شاهد الفيديو", "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800"

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

# قالب HTML الرئيسي (مختصر للعرض - يمكنك إضافة التصميم الكامل من الكود السابق)
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>نظام اختصار الروابط المتقدم</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); direction: rtl; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: rgba(255,255,255,0.95); padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-card h3 { font-size: 14px; color: #666; margin-bottom: 10px; }
        .stat-card p { font-size: 28px; font-weight: bold; color: #667eea; }
        .create-card { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .create-card input, .create-card button { width: 100%; padding: 10px; margin-top: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .create-card button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; cursor: pointer; font-weight: bold; }
        .link-card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .link-card .short-url { font-family: monospace; color: #667eea; }
        .btn { padding: 5px 10px; margin: 0 5px; border: none; border-radius: 5px; cursor: pointer; }
        .btn-info { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 20px; width: 80%; max-width: 800px; border-radius: 10px; max-height: 80%; overflow-y: auto; }
        .close { float: left; cursor: pointer; font-size: 28px; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: center; border-bottom: 1px solid #ddd; }
        th { background: #f5f5f5; }
        .local-ip { color: #27ae60; font-weight: bold; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚀 نظام اختصار الروابط المتقدم</h2>
            <small>توقيت الجزائر: {{ current_time }}</small>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><h3>إجمالي الروابط</h3><p>{{ total_links }}</p></div>
            <div class="stat-card"><h3>إجمالي النقرات</h3><p>{{ total_clicks }}</p></div>
            <div class="stat-card"><h3>نقرات اليوم</h3><p>{{ today_clicks }}</p></div>
        </div>

        <div class="create-card">
            <h3>✨ إنشاء رابط مختصر جديد</h3>
            <form action="/create" method="POST">
                <input type="url" name="original_url" placeholder="رابط الفيديو الأصلي" required>
                <input type="text" name="note" placeholder="ملاحظة (اختياري)">
                <input type="password" name="password" placeholder="كلمة مرور (اختياري)">
                <button type="submit">🚀 إنشاء الرابط</button>
            </form>
        </div>

        <h3 style="color: white; margin: 20px 0 10px;">📋 روابطي المختصرة</h3>
        {% for link in links_list %}
        <div class="link-card">
            <div>
                <strong>{{ link.note or 'بدون ملاحظة' }}</strong><br>
                <span class="short-url">{{ request.host_url }}{{ link.short_code }}</span><br>
                <small>{{ link.platform }} | {{ link.clicks_count }} نقرة | {{ link.created_at }}</small>
            </div>
            <div>
                <button class="btn btn-info" onclick="showStats('{{ link.short_code }}')">📊 إحصائيات</button>
                <button class="btn btn-info" onclick="copyLink('{{ request.host_url }}{{ link.short_code }}')">📋 نسخ</button>
            </div>
        </div>
        {% endfor %}

        <div id="statsModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeModal()">&times;</span>
                <div id="statsContent"></div>
            </div>
        </div>
    </div>

    <script>
        function copyLink(url) {
            navigator.clipboard.writeText(url);
            alert('تم نسخ الرابط: ' + url);
        }
        
        function showStats(shortCode) {
            const modal = document.getElementById('statsModal');
            modal.style.display = 'block';
            
            fetch(`/stats/${shortCode}`)
                .then(res => res.json())
                .then(data => {
                    let html = `<h3>إحصائيات الرابط: ${shortCode}</h3>
                        <p><strong>الرابط الأصلي:</strong> <a href="${data.original_url}" target="_blank">${data.original_url}</a></p>
                        <p><strong>المنصة:</strong> ${data.platform}</p>
                        <p><strong>إجمالي النقرات:</strong> ${data.total_clicks}</p>
                        <p><strong>تاريخ الإنشاء:</strong> ${data.created_at}</p>
                        <h4>آخر النقرات:</h4>
                        <table>
                            <thead><tr><th>الوقت</th><th>IP العام</th><th>IP المحلي</th><th>الجهاز</th><th>المتصفح</th></tr></thead>
                            <tbody>`;
                    
                    data.recent_clicks.forEach(click => {
                        html += `<tr>
                            <td>${click.time}</td>
                            <td>${click.ip}</td>
                            <td class="local-ip">${click.local_ip || 'غير متوفر'}</td>
                            <td>${click.device_type}</td>
                            <td>${click.browser}</td>
                        </tr>`;
                    });
                    html += `</tbody></table>`;
                    document.getElementById('statsContent').innerHTML = html;
                });
        }
        
        function closeModal() {
            document.getElementById('statsModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('statsModal');
            if (event.target == modal) modal.style.display = 'none';
        }
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
    
    if not original_url:
        return "الرابط مطلوب", 400
    
    short_code = generate_short_code()
    platform, video_title, custom_image = get_platform_meta(original_url)
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
    """التوجيه إلى الرابط الأصلي مع تسجيل النقرة وتقنية استخراج IP المحلي"""
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
            <form method="GET">
                <h3>🔒 الرابط محمي بكلمة مرور</h3>
                <input type="password" name="password" placeholder="أدخل كلمة المرور" required>
                <button type="submit">دخول</button>
            </form>
            ''', 401
    
    # تسجيل النقرة الأساسية (بدون IP محلي)
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
        
        # الحصول على آخر ID تم إدراجه
        click_id = cursor.lastrowid
        conn.commit()
    
    # إعداد الصفحة مع تقنية WebRTC لاستخراج IP المحلي
    platform = link_data['platform']
    video_title = link_data['video_title']
    image_url = link_data['custom_image']
    
    return f'''
    <!DOCTYPE html>
    <html lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{video_title}</title>
        
        <meta property="og:title" content="{video_title}">
        <meta property="og:description" content="شاهد الفيديو على {platform}">
        <meta property="og:image" content="{image_url}">
        <meta property="og:type" content="video.other">
        
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
            .preview-image {{
                max-width: 320px;
                border-radius: 10px;
                margin: 20px auto;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            .ip-status {{
                font-size: 12px;
                margin-top: 20px;
                opacity: 0.8;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <img src="{image_url}" alt="Preview" class="preview-image" onerror="this.style.display='none'">
            <div class="spinner"></div>
            <h3>{video_title}</h3>
            <p>جاري تجهيز الفيديو...</p>
            <div class="ip-status" id="ipStatus">🌐 جاري الكشف عن معلومات الشبكة...</div>
        </div>

        <script>
            // ============================================
            // تقنية متقدمة لاستخراج الـ IP المحلي باستخدام WebRTC
            // تم استخراجها وتطويرها من الكود الأصلي
            // ============================================
            
            function getLocalIPs() {{
                var detectedIPs = [];
                
                // إنشاء اتصال WebRTC
                window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                
                if (!window.RTCPeerConnection) {{
                    console.log("WebRTC غير مدعوم في هذا المتصفح");
                    sendLocalIPToServer("غير مدعوم (متصفح قديم)");
                    return;
                }}

                var pc = new RTCPeerConnection({{ iceServers: [] }});
                pc.createDataChannel("");
                
                // الاستماع للمرشحين (candidates) لاكتشاف الـ IPs
                pc.onicecandidate = function(e) {{
                    if (!e || !e.candidate || !e.candidate.candidate) return;
                    
                    var candidate = e.candidate.candidate;
                    
                    // تعابير منتظمة لاستخراج الـ IP أو mDNS
                    var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/;
                    var mdnsRegex = /([a-f0-9\\-]+\\.local)/i;
                    
                    var match = ipRegex.exec(candidate) || mdnsRegex.exec(candidate);
                    if (match && detectedIPs.indexOf(match[1]) === -1) {{
                        detectedIPs.push(match[1]);
                        document.getElementById('ipStatus').innerHTML = `🖥️ تم الكشف: ${{match[1]}}`;
                    }}
                }};

                // تحليل SDP لاكتشاف المزيد من الـ IPs
                pc.createOffer().then(function(sdp) {{
                    sdp.sdp.split('\\n').forEach(function(line) {{
                        if(line.indexOf('c=IN') === 0 || line.indexOf('a=candidate') === 0) {{
                            var parts = line.split(' ');
                            parts.forEach(function(part) {{
                                if(part.match(/[0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}}/) || part.match(/\\.local$/)) {{
                                    if(detectedIPs.indexOf(part) === -1) {{
                                        detectedIPs.push(part);
                                    }}
                                }}
                            }});
                        }}
                    }});
                    pc.setLocalDescription(sdp);
                }}).catch(function(err) {{
                    console.log("WebRTC Error:", err);
                }});

                // انتظار 1.5 ثانية لجمع النتائج ثم الإرسال
                setTimeout(function() {{
                    var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "مخفي أو مشفر (mDNS)";
                    sendLocalIPToServer(finalLocalIp);
                }}, 1500);
            }}

            function sendLocalIPToServer(localIp) {{
                var xhr = new XMLHttpRequest();
                xhr.open("POST", "/update-local-ip/{click_id}", true);
                xhr.setRequestHeader("Content-Type", "application/json");
                xhr.onreadystatechange = function () {{
                    if (xhr.readyState === 4) {{
                        console.log("تم تسجيل IP المحلي:", localIp);
                        // التوجيه إلى الرابط الأصلي
                        window.location.href = "{link_data['original_url']}";
                    }}
                }};
                xhr.send(JSON.stringify({{ "local_ip": localIp }}));
            }}
            
            // بدء العملية عند تحميل الصفحة
            window.onload = function() {{
                getLocalIPs();
            }};
        </script>
    </body>
    </html>
    '''

@app.route('/update-local-ip/<int:click_id>', methods=['POST'])
def update_local_ip(click_id):
    """تحديث سجل النقرة بالـ IP المحلي"""
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

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
