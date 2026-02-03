import os
import time
import json
import random
import sys
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from collections import defaultdict
from datetime import datetime, timedelta

# 👇 Импорт Redis с защитой
try:
    import redis
except ImportError:
    redis = None

app = Flask(__name__)

# --- CONFIG ---
# Ключ теперь строго проверяется на сервере
ACCESS_KEY = os.environ.get("ACCESS_KEY", "START-2026")
REDIS_URL = os.environ.get("REDIS_URL") 
client = OpenAI() 
MODEL = "gpt-4o-mini"
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- LIMITS ---
HARD_LIMIT_FREE = 30
HARD_LIMIT_PAID = 60
MSG_INTERVAL_SEC = 2.0 

# ==========================================
# 📊 ANALYTICS & LOGGING
# ==========================================
def log_event(event_type, user_id, details=""):
    # Пишем в stdout, чтобы Railway/Docker подхватили это в свои логи
    print(f"[ANALYTICS] {datetime.now().isoformat()} | {event_type} | USER:{user_id} | {details}", file=sys.stdout)
    sys.stdout.flush()

# ==========================================
# 💾 PERSISTENCE LAYER
# ==========================================
class DataManager:
    def __init__(self):
        self.r = None
        if REDIS_URL and redis:
            try:
                self.r = redis.from_url(REDIS_URL, decode_responses=True)
                print("✅ CONNECTED TO REDIS")
            except Exception as e:
                print(f"⚠️ REDIS ERROR: {e}. Falling back to RAM.")
        
        self.local_cache = defaultdict(lambda: self._default_schema())

    def _default_schema(self):
        return {
            'count': 0, 
            'last_reset': time.time(),
            'last_msg_time': 0,
            'closed': False,
            'history': [] 
        }

    def get_user(self, uid):
        if self.r:
            try:
                data = self.r.get(f"user:{uid}")
                if data: return json.loads(data)
            except: pass
        
        if uid not in self.local_cache:
            self.local_cache[uid] = self._default_schema()
        return self.local_cache[uid]

    def save_user(self, uid, data):
        self.local_cache[uid] = data
        if self.r:
            try:
                self.r.set(f"user:{uid}", json.dumps(data), ex=172800) # 48h TTL
            except: pass

db = DataManager()

# ==========================================
# 🔌 NEW ENDPOINT: KEY VERIFICATION
# ==========================================
@app.route('/verify', methods=['POST'])
def verify_key():
    # Эндпоинт, чтобы фронтенд не верил пользователю на слово
    data = request.json
    key = data.get("access_key", "")
    is_valid = (key == ACCESS_KEY)
    return jsonify({"valid": is_valid})

# ==========================================
# 📱 PWA MODULE
# ==========================================

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Personal Coach", "short_name": "Coach", "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#2563eb", "orientation": "portrait-primary",
        "icons": [
            {"src": "https://img.icons8.com/ios-filled/192/2563eb/dumbbell.png", "sizes": "192x192", "type": "image/png"},
            {"src": "https://img.icons8.com/ios-filled/512/2563eb/dumbbell.png", "sizes": "512x512", "type": "image/png"}
        ]
    })

@app.route('/service-worker.js')
def service_worker():
    sw_code = """
    const CACHE_NAME = 'coach-v14-diamond';
    const OFFLINE_URL = '/offline.html';
    const STATIC_ASSETS = [
        '/', '/manifest.json', '/service-worker.js',
        'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
        'https://img.icons8.com/ios-filled/192/2563eb/dumbbell.png',
        'https://img.icons8.com/ios-filled/512/2563eb/dumbbell.png'
    ];
    self.addEventListener('install', event => {
        event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS.concat([OFFLINE_URL]))));
        self.skipWaiting();
    });
    self.addEventListener('activate', event => {
        event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
        self.clients.claim();
    });
    self.addEventListener('fetch', event => {
        // API FALLBACK
        if (event.request.method === 'POST' && (event.request.url.includes('/chat') || event.request.url.includes('/verify'))) {
             event.respondWith(
                 fetch(event.request).catch(() => {
                     return new Response(JSON.stringify({
                         reply: "⚠️ **Offline Mode**\\nI cannot analyze data without internet.", 
                         is_premium: false, error: "offline", valid: false
                     }), { headers: { 'Content-Type': 'application/json' } });
                 })
             );
             return;
        }
        if (event.request.method === 'GET') {
            event.respondWith(
                caches.match(event.request).then(cached => {
                    if (cached) return cached;
                    return fetch(event.request).then(r => {
                        if (r && r.status === 200 && r.type === 'basic') {
                            let clone = r.clone();
                            caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                        }
                        return r;
                    }).catch(() => {
                        if (event.request.mode === 'navigate') return caches.match(OFFLINE_URL);
                    });
                })
            );
        }
    });
    """
    return sw_code, 200, {'Content-Type': 'application/javascript'}

@app.route('/offline.html')
def offline_page():
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Offline</title><style>body{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,sans-serif;background:#f8fafc;color:#0f172a;text-align:center;padding:20px;margin:0}button{background:#2563eb;color:white;border:none;padding:12px 24px;border-radius:10px;font-size:16px;cursor:pointer;font-weight:600;margin-top:20px}</style></head><body><h1>⚠️ No Connection</h1><p>Please check your internet.</p><button onclick="window.location.reload()">Try Again</button></body></html>"""

# ==========================================
# 🧠 BRAIN (PROMPT ENGINEERING v2)
# ==========================================

SYSTEM_SALES_BASE = """You are an Intake Specialist for an Elite Fitness Program.
ROLE: Diagnostic Tool. NOT a therapist. NOT a friend.
GOAL: Find the gap between user's goal and their reality.

ABSOLUTE RULES:
1. 🚫 NO EMOTIONS: Delete words like "Great", "I understand".
2. 🚫 NO MIRRORING: Do not validate feelings.
3. 📉 SHORT & COLD: Max 2 sentences. Clinical tone.
4. ⚡ ONE QUESTION ONLY: Every response must end with exactly ONE question.

ERROR RECOVERY:
If you ask >1 question, stop. Reformulate to ask ONLY the most critical one.
"""

SYSTEM_COACH = """You are an elite Personal Fitness Architect.
TONE: Authoritative, Scientific, Action-Oriented.
GOAL: Deliver value. LIMIT: 60 msgs/day.
Don't ask "How are you". Ask "Did you hit your macros?".
"""

# ==========================================
# 🎨 UI (HTML + JS + CSS)
# ==========================================

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
        .title { font-weight: 800; color: #0f172a; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px; }
        .badge { background: #e2e8f0; padding: 6px 12px; border-radius: 4px; font-size: 11px; font-weight: 700; color: #64748b; cursor: pointer; text-transform: uppercase; }
        .badge.premium { background: #0f172a; color: white; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; padding-bottom: 40px; }
        .message { max-width: 88%; padding: 14px 18px; border-radius: 4px; font-size: 15px; line-height: 1.4; opacity: 0; animation: fadeInUp 0.2s forwards; }
        .bot { align-self: flex-start; background: var(--bot-bg); color: #1e293b; border-left: 3px solid #0f172a; }
        .user { align-self: flex-end; background: var(--user-bg); color: white; }
        .message strong { font-weight: 800; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .typing { align-self: flex-start; background: var(--bot-bg); padding: 12px 20px; border-radius: 4px; display: none; gap: 5px; width: fit-content; margin-bottom: 10px; }
        .dot { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; } .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        .input-area { padding: 15px; background: white; display: flex; gap: 10px; border-top: 1px solid #e2e8f0; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        input { flex: 1; padding: 14px; border: 1px solid #e2e8f0; border-radius: 4px; outline: none; font-size: 16px; background: #f8fafc; }
        input:focus { border-color: #0f172a; background: white; }
        button { background: #0f172a; color: white; border: none; width: 50px; height: 50px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: opacity 0.2s; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        #toast { visibility: hidden; min-width: 200px; background-color: #333; color: #fff; text-align: center; border-radius: 50px; padding: 12px 20px; position: fixed; z-index: 1000; left: 50%; bottom: 80px; transform: translateX(-50%); font-size: 14px; opacity: 0; transition: opacity 0.3s, bottom 0.3s; box-shadow: 0 4px 12px rgba(0,0,0,0.3); font-weight: 600; }
        #toast.show { visibility: visible; opacity: 1; bottom: 100px; }
        #toast.error { background-color: #ef4444; }
        #modal { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); backdrop-filter: blur(2px); display:none; justify-content:center; align-items:center; z-index: 999; }
        .modal-content { background:white; padding:30px; border-radius:4px; text-align:center; width:85%; max-width:340px; }
        .modal-content input { width:100%; margin:20px 0; text-align:center; letter-spacing: 3px; font-weight: bold; font-size: 18px; padding: 10px; border: 2px solid #e2e8f0; }
        .btn-main { width:100%; background: #10b981; color:white; padding: 14px; font-weight: 700; border:none; margin-bottom: 12px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">INTAKE SPECIALIST</div>
        <div id="badge" class="badge" onclick="openModal()">DIAGNOSTIC</div>
    </div>
    <div id="chat-box"></div>
    <div class="typing" id="typing" style="margin-left: 20px; margin-bottom: 60px; display:none;">
        <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    </div>
    <div class="input-area">
        <input type="text" id="inp" placeholder="Type here..." autocomplete="off" onkeypress="if(event.key==='Enter') send()">
        <button id="sendBtn" onclick="send()"><svg viewBox="0 0 24 24" width="22" height="22" stroke="white" stroke-width="2.5" fill="none"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
    </div>
    <div id="modal">
        <div class="modal-content">
            <h3>ACCESS KEY</h3>
            <input type="text" id="key-val" placeholder="START-202X">
            <button class="btn-main" onclick="verifyAndSave()">ACTIVATE</button>
            <button onclick="document.getElementById('modal').style.display='none'" style="background:none; border:none; color:#64748b; cursor:pointer;">CANCEL</button>
            <br><a href="{{ shopify_url }}" target="_blank" style="font-size:13px; color:#0f172a; text-decoration:underline; margin-top:15px; display:block; font-weight:600;">Purchase Key ($20)</a>
        </div>
    </div>
    <div id="toast">Message</div>

    <script>
        if ('serviceWorker' in navigator) { window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js')); }
        
        function getUUID() {
            let id = localStorage.getItem('coach_uid');
            if (!id) {
                if (typeof crypto !== 'undefined' && crypto.randomUUID) { id = crypto.randomUUID(); } 
                else { id = 'user_' + Math.random().toString(36).substr(2, 9); }
                localStorage.setItem('coach_uid', id);
            }
            return id;
        }

        function showToast(msg, isError=false) {
            const t = document.getElementById("toast");
            t.innerText = msg;
            t.className = "show" + (isError ? " error" : "");
            setTimeout(function(){ t.className = t.className.replace("show", "").replace(" error", ""); }, 3000);
        }

        function loadHistory() {
            try {
                const raw = localStorage.getItem('coach_history');
                if (!raw) {
                    addMsg("I am your Intake Specialist.<br>Answer precisely.<br><br><strong>What is your primary fitness goal?</strong>", 'bot', false);
                    return;
                }
                const history = JSON.parse(raw);
                if (Array.isArray(history)) {
                    history.forEach(item => addMsg(item.text, item.type, false));
                }
            } catch (e) { localStorage.removeItem('coach_history'); }
        }

        function saveHistoryToLocal(text, type) {
            let history = [];
            try { history = JSON.parse(localStorage.getItem('coach_history') || "[]"); } catch(e) {}
            history.push({text: text, type: type});
            if (history.length > 30) history = history.slice(-30);
            localStorage.setItem('coach_history', JSON.stringify(history));
        }

        // 🔥 VALIDATE KEY ON LOAD
        let userKey = localStorage.getItem('coach_key') || ""; 
        if (userKey) {
            // Оптимистичное обновление UI, но лучше проверить при первом запросе
            document.getElementById('badge').innerText="COACH"; 
            document.getElementById('badge').classList.add("premium");
        }

        const chat = document.getElementById('chat-box'); 
        const typing = document.getElementById('typing');
        const sendBtn = document.getElementById('sendBtn');
        const deviceId = getUUID(); 

        loadHistory();

        function openModal() { document.getElementById('modal').style.display='flex'; }
        
        // 🔒 REAL SERVER VALIDATION
        function verifyAndSave() { 
            const val = document.getElementById('key-val').value.trim(); 
            if(!val) return;
            
            const btn = document.querySelector('.btn-main');
            btn.innerText = "VERIFYING...";
            btn.disabled = true;

            fetch('/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({access_key: val})
            })
            .then(r => r.json())
            .then(data => {
                if (data.valid) {
                    userKey = val; 
                    localStorage.setItem('coach_key', val); 
                    document.getElementById('badge').innerText="COACH"; 
                    document.getElementById('badge').classList.add("premium");
                    document.getElementById('modal').style.display='none'; 
                    showToast("Key Verified. Premium Active.");
                } else {
                    showToast("Invalid Key", true);
                }
            })
            .catch(() => showToast("Network Error", true))
            .finally(() => {
                btn.innerText = "ACTIVATE";
                btn.disabled = false;
            });
        }

        function addMsg(text, type, shouldSave = true) { 
            typing.style.display='none'; 
            const d=document.createElement('div'); d.className='message '+type; 
            if(type==='bot' && window.marked){ d.innerHTML=marked.parse(text); }
            else{ d.innerHTML=text.replace(/\\n/g,'<br>'); }
            chat.appendChild(d); 
            chat.appendChild(typing); 
            chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
            if (shouldSave) saveHistoryToLocal(text, type);
        }
        
        function send() { 
            const inp = document.getElementById('inp'); const val = inp.value.trim(); 
            if(!val) return; 
            if(sendBtn.disabled) return; 

            addMsg(val, 'user'); inp.value=''; typing.style.display='flex'; 
            chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
            
            sendBtn.disabled = true; sendBtn.style.opacity = "0.5";
            
            fetch('/chat', { 
                method:'POST', headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({message:val, access_key:userKey, device_id: deviceId}) 
            })
            .then(r=>r.json()).then(d=>{ 
                if (d.error) {
                    showToast(d.reply, true); 
                    typing.style.display='none';
                } else {
                    if(d.is_premium){ 
                        document.getElementById('badge').innerText="COACH"; 
                        document.getElementById('badge').classList.add("premium"); 
                    }
                    addMsg(d.reply,'bot'); 
                }
            })
            .catch((e)=>{ typing.style.display='none'; showToast("⚠️ Network Error", true); })
            .finally(() => { sendBtn.disabled = false; sendBtn.style.opacity = "1"; });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, shopify_url=SHOPIFY_PRODUCT_URL)

# ==========================================
# 🔌 API ENDPOINTS
# ==========================================

@app.route('/verify', methods=['POST'])
def verify():
    key = request.json.get('access_key', '')
    return jsonify({"valid": key == ACCESS_KEY})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get("message", "")
    ukey = data.get("access_key", "")
    user_id = data.get("device_id") or request.remote_addr 
    
    # 🧹 CLEANUP & VALIDATION
    stop_words = ["hi", "hello", "hey", "hola", "start", "test"]
    if len(msg.strip()) < 2 or msg.lower().strip() in stop_words:
        return jsonify({"reply": "Be specific. Give me data.", "is_premium": False})

    # 💾 DB LOAD
    user = db.get_user(user_id)

    # ⏱️ THROTTLING
    current_time = time.time()
    if (current_time - user['last_msg_time']) < MSG_INTERVAL_SEC:
        return jsonify({"reply": "Too fast. Slow down.", "error": "rate_limit", "is_premium": False})
    
    user['last_msg_time'] = current_time

    # 🔒 AUTH & LIMITS
    is_paid = (ukey == ACCESS_KEY)
    
    # Garbage Collection
    if len(user['history']) > 20: user['history'] = user['history'][-10:]

    # Reset (24h)
    if (time.time() - user['last_reset']) > 86400:
        user['count'] = 0
        user['last_reset'] = time.time()
        user['closed'] = False
        user['history'] = []
    
    limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE
    count = user['count']
    
    if count >= limit:
        db.save_user(user_id, user)
        return jsonify({"reply": "Daily limit reached.", "is_premium": is_paid})
    
    user['count'] += 1
    
    # --- LOGIC ---
    system_instruction = ""
    stage = "UNKNOWN"
    
    if is_paid:
        stage = "COACH"
        system_instruction = SYSTEM_COACH
    else:
        if count <= 2:
            stage = "INTAKE"
            stage_instruction = "Tone: Neutral. Fact-finding."
        elif count <= 6:
            stage = "PROBING"
            stage_instruction = "Tone: Assertive. Dig deeper."
        elif count <= 15:
            stage = "GAP ANALYSIS"
            stage_instruction = "Tone: Cold hard truth. Show the mismatch."
        else:
            if not user['closed']:
                scripts = [
                    f"Diagnosis complete. Gap found. Fix it: {SHOPIFY_PRODUCT_URL}",
                    f"Stop talking. Build systems. Unlock protocol: {SHOPIFY_PRODUCT_URL}",
                    f"Reality check: Approach failing. Change it: {SHOPIFY_PRODUCT_URL}"
                ]
                selected_script = random.choice(scripts)
                stage = "CLOSE"
                # 🔥 XML-TAG PROMPTING (MODERN BEST PRACTICE)
                stage_instruction = f"""
                <current_stage>CLOSE (HARD SELL)</current_stage>
                <instruction>
                IGNORE all other instructions. 
                REPLY EXACTLY WITH THIS STRING (Do not add anything else):
                "{selected_script}"
                </instruction>
                """
                
                log_event("SALE_ATTEMPT", user_id, f"SCRIPT: {selected_script}")
                user['closed'] = True 
            else:
                stage = "POST-CLOSE"
                stage_instruction = "Repeat unlock link ONCE if asked. Otherwise brief."
        
        # Only wrap in XML if it's not the XML Close stage above to avoid double tagging
        if stage != "CLOSE":
            system_instruction = f"""{SYSTEM_SALES_BASE}
            <context>
            MSG {count}/{limit}
            STAGE: {stage}
            </context>
            <instruction>
            {stage_instruction}
            </instruction>
            """
        else:
            system_instruction = f"{SYSTEM_SALES_BASE}\n{stage_instruction}"

    # 🔁 AI RETRY LOGIC (3 Attempts + Exponential Backoff)
    reply = "System Error."
    for attempt in range(3):
        try:
            messages = [{"role": "system", "content": system_instruction}]
            context_len = 20 if is_paid else 6
            messages.extend(user['history'][-context_len:]) 
            messages.append({"role": "user", "content": msg})

            resp = client.chat.completions.create(model=MODEL, messages=messages)
            
            if not resp.choices: raise ValueError("Empty response")
            reply = resp.choices[0].message.content
            break 
        except Exception as e:
            print(f"API Error (Attempt {attempt+1}): {e}")
            if attempt == 2: # Failed all 3 times
                return jsonify({"reply": "AI is overloaded. Try in 5 sec.", "error": "api_fail", "is_premium": is_paid})
            time.sleep(0.5 * (attempt + 1)) # 0.5s, 1.0s wait

    user['history'].append({"role": "user", "content": msg})
    user['history'].append({"role": "assistant", "content": reply})
    
    db.save_user(user_id, user)

    return jsonify({"reply": reply, "is_premium": is_paid})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
