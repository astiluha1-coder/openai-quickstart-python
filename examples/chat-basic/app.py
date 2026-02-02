import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)

# 👇 Бот берет ключ из Railway Variables
client = OpenAI() 

# --- НАСТРОЙКИ ---
MODEL = "gpt-4o-mini"
CURRENT_ACCESS_KEY = "START-2026"  
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- ЛИМИТЫ ---
HARD_LIMIT_FREE = 30
HARD_LIMIT_PAID = 60

# --- ПАМЯТЬ ---
user_limits = defaultdict(lambda: {
    'count': 0, 
    'last_reset': datetime.now()
})

# --- PWA MANIFEST ---
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Personal Coach",
        "short_name": "Coach",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "https://img.icons8.com/ios-filled/500/2563eb/dumbbell.png",
                "sizes": "192x192",
                "type": "image/png"
            }
        ]
    })

@app.route('/service-worker.js')
def service_worker():
    js_code = """
    const CACHE_NAME = 'coach-app-v3';
    self.addEventListener('fetch', (e) => {
      e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    });
    """
    return js_code, 200, {'Content-Type': 'application/javascript'}

# --- PROMPTS ---
SYSTEM_SALES = """You are the empathetic Assistant to a Premium Online Coach.
ROLE: Navigator.
RULES:
1. ❌ NO "I CANNOT".
2. 🛑 LIMIT PROTOCOL:
   - <8 msgs: Validate, Listen, Ask 1 question.
   - 8-15 msgs: REALITY CHECK ("I see patterns keeping you stuck. 1. Guessing 2. Full Plan. Choose.").
   - 20 msgs: CLOSE ("Limit reached. Upgrade here: " + link).
   - Use **bold** for emphasis.
"""

SYSTEM_COACH = """You are an elite Personal Fitness Architect.
GOAL: Deliver value.
LIMIT: 60 msgs/day.
- Use **bold** for key metrics.
"""

# --- HTML (ИСПРАВЛЕННЫЙ JS + STRUTURE) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Personal Coach</title>
    
    <link rel="manifest" href="/manifest.json">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <meta name="theme-color" content="#2563eb">
    <meta name="apple-mobile-web-app-capable" content="yes">

    <style>
        :root { --primary: #2563eb; --bg: #f8fafc; --user-bg: #2563eb; --bot-bg: #f1f5f9; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); height: 100vh; display: flex; flex-direction: column; margin: 0; overflow: hidden; }
        
        .header { background: white; padding: 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; padding-top: max(15px, env(safe-area-inset-top)); }
        .title { font-weight: 800; color: #0f172a; font-size: 16px; }
        .badge { background: #e2e8f0; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; color: #64748b; cursor: pointer; transition: 0.2s; }
        .badge.premium { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; }
        
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; padding-bottom: 40px; }
        
        .message { max-width: 88%; padding: 14px 18px; border-radius: 18px; font-size: 15px; line-height: 1.5; opacity: 0; animation: fadeInUp 0.3s forwards; word-wrap: break-word; }
        .bot { align-self: flex-start; background: var(--bot-bg); color: #1e293b; border-bottom-left-radius: 4px; }
        .user { align-self: flex-end; background: var(--user-bg); color: white; border-bottom-right-radius: 4px; }
        
        /* Markdown */
        .message strong { font-weight: 700; }
        .message ul, .message ol { margin: 5px 0 5px 20px; padding: 0; }
        .message p { margin: 0 0 8px 0; }
        
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* Typing inside chat now */
        .typing { align-self: flex-start; background: var(--bot-bg); padding: 12px 20px; border-radius: 18px; border-bottom-left-radius: 4px; display: none; gap: 5px; width: fit-content; animation: fadeInUp 0.3s forwards; margin-bottom: 10px; }
        .dot { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; } .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

        .input-area { padding: 15px; background: white; display: flex; gap: 10px; border-top: 1px solid #e2e8f0; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        input { flex: 1; padding: 14px; border: 1px solid #e2e8f0; border-radius: 25px; outline: none; font-size: 16px; background: #f8fafc; }
        input:focus { border-color: var(--primary); background: white; }
        button { background: var(--primary); color: white; border: none; width: 50px; height: 50px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        
        #modal { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); backdrop-filter: blur(4px); display:none; justify-content:center; align-items:center; z-index: 999; }
        .modal-content { background:white; padding:30px; border-radius:24px; text-align:center; width:85%; max-width:340px; }
        .modal-content input { width:100%; margin:20px 0; text-align:center; letter-spacing: 3px; font-weight: bold; font-size: 18px; padding: 10px; border: 2px solid #e2e8f0; border-radius: 12px; }
        .btn-main { width:100%; background: #10b981; color:white; padding: 14px; border-radius: 14px; font-weight: 600; border:none; margin-bottom: 12px; font-size: 16px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">PERSONAL COACH</div>
        <div id="badge" class="badge" onclick="openModal()">• FREE DIAGNOSTIC</div>
    </div>
    
    <div id="chat-box">
        <div class="message bot">Hello! 👋 Ready to transform?<br>What is your goal?</div>
        <div class="typing" id="typing">
            <div class="dot"></div><div class="dot"></div><div class="dot"></div>
        </div>
    </div>
    
    <div class="input-area">
        <input type="text" id="inp" placeholder="Message..." autocomplete="off" onkeypress="if(event.key==='Enter') send()">
        <button onclick="send()"><svg viewBox="0 0 24 24" width="22" height="22" stroke="white" stroke-width="2.5" fill="none"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
    </div>

    <div id="modal">
        <div class="modal-content">
            <h3>Enter Access Key</h3>
            <input type="text" id="key-val" placeholder="START-202X">
            <button class="btn-main" onclick="saveKey()">Activate Premium</button>
            <button onclick="document.getElementById('modal').style.display='none'" style="background:none; border:none; color:#64748b; cursor:pointer;">Close</button>
            <br>
            <a href="{{ shopify_url }}" target="_blank" style="font-size:13px; color:#2563eb; text-decoration:none; margin-top:15px; display:block; font-weight:500;">Get a key ($20)</a>
        </div>
    </div>

    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js'));
        }

        let userKey = "";
        const chat = document.getElementById('chat-box');
        const typing = document.getElementById('typing');

        function openModal() { document.getElementById('modal').style.display='flex'; }
        
        function saveKey() { 
            const val = document.getElementById('key-val').value.trim();
            if(val) {
                userKey = val; 
                document.getElementById('badge').innerText = "CHECKING...";
                document.getElementById('modal').style.display='none';
                alert("Key saved.");
            }
        }
        
        function addMsg(text, type) {
            // Безопасное скрытие индикатора
            typing.style.display = 'none';
            
            const d = document.createElement('div');
            d.className = 'message ' + type;
            
            if (type === 'bot' && window.marked) {
                d.innerHTML = marked.parse(text);
            } else {
                d.innerHTML = text.replace(/\\n/g, '<br>');
            }
            
            // Вставляем сообщение ПЕРЕД индикатором набора
            chat.insertBefore(d, typing);
            chat.scrollTop = chat.scrollHeight;
        }

        function send() {
            const inp = document.getElementById('inp');
            const val = inp.value.trim();
            if(!val) return;
            
            addMsg(val, 'user');
            inp.value = '';
            
            // Показываем индикатор
            typing.style.display = 'flex';
            chat.scrollTop = chat.scrollHeight;
            
            fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ message: val, access_key: userKey })
            })
            .then(res => res.json())
            .then(data => {
                if(data.is_premium) {
                    const b = document.getElementById('badge');
                    b.innerText = "PREMIUM COACH";
                    b.classList.add("premium");
                }
                addMsg(data.reply, 'bot');
            })
            .catch(e => {
                typing.style.display = 'none';
                // Добавляем сообщение об ошибке, если сеть упала
                const d = document.createElement('div');
                d.className = 'message bot';
                d.innerText = "Connection error. Please try again.";
                chat.insertBefore(d, typing);
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, shopify_url=SHOPIFY_PRODUCT_URL)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get("message", "")
    ukey = data.get("access_key", "")
    ip = request.remote_addr
    
    is_paid = (ukey == CURRENT_ACCESS_KEY)
    limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE
    
    # Reset
    if datetime.now() - user_limits[ip]['last_reset'] > timedelta(hours=24):
        user_limits[ip]['count'] = 0
        user_limits[ip]['last_reset'] = datetime.now()
    
    if user_limits[ip]['count'] >= limit:
        return jsonify({"reply": "Daily limit reached.", "is_premium": is_paid})
    
    user_limits[ip]['count'] += 1
    new_count = user_limits[ip]['count']
    print(f"LOG: IP={ip} | {new_count}/{limit}")

    sys_prompt = SYSTEM_COACH if is_paid else SYSTEM_SALES
    full_prompt = f"{sys_prompt}\n\nCURRENT MSG COUNT: {new_count}"
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": full_prompt}, {"role": "user", "content": msg}]
        )
        reply = resp.choices[0].message.content
    except Exception as e:
        reply = "Sorry, system error."
        print(f"Error: {e}")

    return jsonify({"reply": reply, "is_premium": is_paid})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
