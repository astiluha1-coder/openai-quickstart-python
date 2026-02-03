import os
import time
import json
import random
import sys
import re
import threading
import hmac
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from collections import defaultdict
from datetime import datetime

# 👇 Импорт Redis
try:
    import redis
except ImportError:
    redis = None

def safe_str_eq(a, b):
    if not a or not b: return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

app = Flask(__name__)

# --- CONFIG ---
ACCESS_KEY = os.environ.get("ACCESS_KEY", "START-2026")
REDIS_URL = os.environ.get("REDIS_URL") 
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try: client = OpenAI(api_key=OPENAI_API_KEY)
    except: pass

MODEL = "gpt-4o-mini"
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- SYSTEM SETTINGS ---
CHECKIN_INTERVAL_DAYS = 7
HARD_LIMIT_FREE = 30
HARD_LIMIT_PAID = 60
BACKUP_FILE = "backup_db.json"
MAX_HISTORY_LEN = 20 

# ==========================================
# 🛠️ HELPERS
# ==========================================
def extract_number(text):
    if not text: return None
    text = text.replace(',', '.')
    match = re.search(r"[-+]?\d*\.\d+|\d+", text)
    if match:
        try: return float(match.group())
        except: return None
    return None

# ==========================================
# 💾 DATA MANAGER (ASYNC & SECURE)
# ==========================================
class DataManager:
    def __init__(self):
        self.r = None
        self.local_cache = defaultdict(lambda: self._default_schema())
        self.lock = threading.Lock()
        
        if REDIS_URL and redis:
            try:
                self.r = redis.from_url(REDIS_URL, decode_responses=True)
                print("✅ REDIS ACTIVE")
            except: pass
        
        if not self.r:
            self._load_from_disk()

    def _default_schema(self):
        return {
            'count': 0, 'last_reset': time.time(), 'last_msg_time': 0,
            'history': [], 'onboarding_step': 'GOAL', 'goal': None,
            'baseline': {}, 'checkin_due': 0, 'checkin_state': None, 
            'checkin_data': {}, 'logs': [], 'compliance': {'overall': 100, 'trend': []} 
        }

    def _load_from_disk(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items(): self.local_cache[k] = v
                print("✅ DISK BACKUP LOADED")
            except: pass

    def _async_save(self):
        """Threaded save to avoid blocking Flask"""
        def save():
            with self.lock:
                try:
                    with open(BACKUP_FILE, 'w') as f:
                        json.dump(self.local_cache, f)
                except: pass
        threading.Thread(target=save).start()

    def get_user(self, uid):
        if self.r:
            try:
                data = self.r.get(f"user:{uid}")
                if data: return json.loads(data)
            except: pass
        return self.local_cache[uid]

    def save_user(self, uid, data):
        if len(data['history']) > MAX_HISTORY_LEN:
            data['history'] = data['history'][-MAX_HISTORY_LEN:]
        
        if self.r:
            try: self.r.set(f"user:{uid}", json.dumps(data), ex=604800)
            except: pass
        
        self.local_cache[uid] = data
        if not self.r: self._async_save()

    def reset_user(self, uid):
        self.local_cache[uid] = self._default_schema()
        self.save_user(uid, self.local_cache[uid])

db = DataManager()

# ==========================================
# 🧠 SYSTEM PROMPTS
# ==========================================
SYSTEM_COACH = """You are the SYSTEM. Biological Protocol Manager. TONE: Clinical, Binary.
RULES: 1. Locked parameters (Calories, Volume) fixed. 2. Ask MAX 1 question. 3. Structure response strictly."""

SYSTEM_CHECKIN_ANALYSIS = """ACT AS: System Logic. Weekly Protocol Evaluation.
OUTPUT FORMAT: **SYSTEM STATUS**, **Weight Delta**, **Compliance Trend**, **Adjustment**, **Reasoning**, **Projection**, **Fact-Based Feedback**."""

# ==========================================
# 🎨 UI (WITH LIMIT DISPLAY & HAPTIC)
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Coach</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="https://img.icons8.com/fluency/192/dumbbell.png">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <meta name="theme-color" content="#4f46e5">
    <style>
        :root { --primary: #4f46e5; --bg: #f8fafc; --user-bg: #4f46e5; --bot-bg: #f1f5f9; }
        body { font-family: -apple-system, sans-serif; background: var(--bg); height: 100vh; display: flex; flex-direction: column; margin: 0; overflow: hidden; }
        .header { background: white; padding: 15px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; padding-top: max(15px, env(safe-area-inset-top)); }
        .title { font-weight: 800; color: #0f172a; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
        .badge { background: #e2e8f0; padding: 6px 12px; border-radius: 4px; font-size: 10px; font-weight: 700; color: #64748b; cursor: pointer; }
        .badge.premium { background: #0f172a; color: white; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; padding-bottom: 40px; }
        .message { max-width: 85%; padding: 12px 16px; border-radius: 12px; font-size: 15px; line-height: 1.4; animation: fadeInUp 0.2s forwards; }
        .bot { align-self: flex-start; background: var(--bot-bg); color: #1e293b; border-bottom-left-radius: 2px; }
        .user { align-self: flex-end; background: var(--user-bg); color: white; border-bottom-right-radius: 2px; }
        .sys-event { align-self: center; color: #64748b; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 10px 0; text-align: center; }
        .sys-error { align-self: center; background: #fee2e2; color: #b91c1c; font-size: 11px; padding: 6px 12px; border-radius: 20px; }
        .sys-success { align-self: flex-start; background: #f0fdf4; border-left: 4px solid #16a34a; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.1); }
        .input-area { padding: 15px; background: white; display: flex; gap: 8px; border-top: 1px solid #e2e8f0; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        input { flex: 1; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 16px; outline: none; }
        button { background: var(--primary); color: white; border: none; width: 45px; height: 45px; border-radius: 8px; font-weight: bold; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        #modal { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); display:none; justify-content:center; align-items:center; z-index: 999; }
        .modal-content { background:white; padding:25px; border-radius:12px; text-align:center; width:80%; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">SYSTEM <span id="limit-info" style="opacity: 0.5;"></span></div>
        <div id="badge" class="badge" onclick="openModal()">STATUS</div>
    </div>
    <div id="chat-box"></div>
    <div class="input-area">
        <input type="text" id="inp" placeholder="Message..." autocomplete="off" onkeypress="if(event.key==='Enter') send()">
        <button id="sendBtn" onclick="send()">➔</button>
    </div>
    <div id="modal">
        <div class="modal-content">
            <h3>AUTHENTICATION</h3>
            <input type="text" id="key-val" placeholder="ENTER KEY" style="text-align:center; margin-bottom:15px;">
            <button style="width:100%;" onclick="verifyAndSave()">ACTIVATE</button>
            <p onclick="document.getElementById('modal').style.display='none'" style="margin-top:15px; color:#64748b; font-size:12px;">CANCEL</p>
        </div>
    </div>
    <script>
        const chat = document.getElementById('chat-box');
        const inp = document.getElementById('inp');
        const sendBtn = document.getElementById('sendBtn');
        
        function openModal() { document.getElementById('modal').style.display='flex'; }
        
        function verifyAndSave() {
            const val = document.getElementById('key-val').value.trim();
            fetch('/verify', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({access_key: val}) })
            .then(r => r.json()).then(d => {
                if (d.valid) { localStorage.setItem('coach_key', val); location.reload(); }
                else { alert("Invalid Key"); }
            });
        }

        function addMsg(text, type, shouldSave = true) {
            const d = document.createElement('div');
            d.className = 'message ' + type;
            if (type === 'user') d.innerText = text;
            else d.innerHTML = marked.parse(text);
            chat.appendChild(d);
            chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
            if (navigator.vibrate) navigator.vibrate(5);
        }

        function send(force=null) {
            let val = force || inp.value.trim(); if (!val) return;
            if (!force) addMsg(val, 'user');
            inp.value = ''; inp.disabled = true; sendBtn.disabled = true;
            
            fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({message:val, access_key: localStorage.getItem('coach_key'), device_id: 'dev_1'}) 
            })
            .then(r=>r.json()).then(d=>{
                if (d.limit_info) document.getElementById('limit-info').innerText = `(${d.limit_info})`;
                if (d.is_premium) { document.getElementById('badge').innerText="PREMIUM"; document.getElementById('badge').classList.add("premium"); }
                addMsg(d.reply, d.type || 'bot');
            })
            .finally(() => { inp.disabled = false; sendBtn.disabled = false; inp.focus(); });
        }

        // Init
        const hist = JSON.parse(localStorage.getItem('coach_history') || "[]");
        if (hist.length === 0) send("SYSTEM_INIT_TRIGGER");
        else hist.forEach(m => addMsg(m.text, m.type, false));
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_PAGE)

@app.route('/verify', methods=['POST'])
def verify():
    return jsonify({"valid": safe_str_eq(request.json.get('access_key', ''), ACCESS_KEY)})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get("message", "").strip()
    ukey = data.get("access_key", "")
    user_id = data.get("device_id") or request.remote_addr 
    
    if not client: return jsonify({"reply": "AI OFFLINE", "type": "sys-error"})

    user = db.get_user(user_id)
    current_time = time.time()
    is_paid = safe_str_eq(ukey, ACCESS_KEY)

    # Reset
    if (current_time - user['last_reset']) > 86400:
        user['count'] = 0; user['last_reset'] = current_time

    # ONBOARDING
    if user.get('onboarding_step') != 'DONE':
        if msg == "SYSTEM_INIT_TRIGGER":
            return jsonify({"reply": "⚙️ **SYSTEM INITIALIZED**\\n1. Fat Loss\\n2. Muscle Gain\\n3. Performance", "type": "system_event"})
        
        if user['onboarding_step'] == 'GOAL':
            user['goal'] = msg; user['onboarding_step'] = 'BASELINE'; db.save_user(user_id, user)
            return jsonify({"reply": "🎯 **GOAL LOCKED.**\\nProvide: Height, Weight, Age, Experience.", "type": "system_event"})
        
        if user['onboarding_step'] == 'BASELINE':
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", msg)
            if len(nums) < 3: return jsonify({"reply": "🛑 **INSUFFICIENT DATA**", "type": "sys-error"})
            user['baseline'] = msg; user['onboarding_step'] = 'DONE'; db.save_user(user_id, user)
            return jsonify({"reply": "✅ **READY.** Use format: Goal: ... Current: ... Question: ...", "type": "system_event"})

    # CHECK-IN
    if is_paid and (current_time > user.get('checkin_due', 0)):
        state = user.get('checkin_state')
        if state is None:
            user['checkin_state'] = 'WEIGHT'; db.save_user(user_id, user)
            return jsonify({"reply": "📉 **EVALUATION OPENED.**\\nStep 1/4: Bodyweight (kg).", "type": "system_event"})
        
        val = extract_number(msg)
        if state == 'WEIGHT':
            if val and 30 < val < 300:
                user['checkin_data']['weight'] = val; user['checkin_state'] = 'SLEEP'
                db.save_user(user_id, user)
                return jsonify({"reply": "Step 2/4: Sleep (hrs)."})
            return jsonify({"reply": "⚠️ INVALID WEIGHT", "type": "sys-error"})
        
        if state == 'SLEEP':
            if val is not None and 0 <= val <= 24:
                user['checkin_data']['sleep'] = val; user['checkin_state'] = 'ENERGY'
                db.save_user(user_id, user)
                return jsonify({"reply": "Step 3/4: Energy (1-5)."})
            return jsonify({"reply": "⚠️ INVALID SLEEP", "type": "sys-error"})

        if state == 'ENERGY':
            if val and 1 <= val <= 5:
                user['checkin_data']['energy'] = int(val); user['checkin_state'] = 'COMPLIANCE'
                db.save_user(user_id, user)
                return jsonify({"reply": "Step 4/4: Compliance (0-100%)."})
            return jsonify({"reply": "⚠️ INVALID ENERGY", "type": "sys-error"})

        if state == 'COMPLIANCE':
            if val is not None and 0 <= val <= 100:
                user['compliance']['trend'].append({'v': int(val)}); user['compliance']['trend'] = user['compliance']['trend'][-3:]
                avg_c = sum(x['v'] for x in user['compliance']['trend']) / len(user['compliance']['trend'])
                
                # Logic
                verdict = "STAGNATION"; m_type = "sys-warning"
                logs = [l for l in user['logs'] if isinstance(l.get('w'), (int,float))]
                if logs:
                    delta = val - (sum(l['w'] for l in logs[-3:]) / len(logs[-3:]))
                    if delta < -0.3: verdict = "OPTIMIZED"; m_type = "sys-success"
                
                prompt = SYSTEM_CHECKIN_ANALYSIS.format(weight_diff="N/A", verdict=verdict, fact_feedback="Data logged", compliance=int(avg_c), sleep=user['checkin_data']['sleep'], energy=user['checkin_data']['energy'])
                resp = client.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], temperature=0)
                
                user['logs'].append({'w': user['checkin_data']['weight']})
                user['checkin_due'] = current_time + (CHECKIN_INTERVAL_DAYS * 86400)
                user['checkin_state'] = None; db.save_user(user_id, user)
                return jsonify({"reply": resp.choices[0].message.content, "type": m_type})

    # CHAT
    limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE
    if user['count'] >= limit: return jsonify({"reply": "LIMIT REACHED"})
    
    user['count'] += 1
    messages = [{"role": "system", "content": SYSTEM_COACH}]
    messages.extend(user['history'][-6:])
    messages.append({"role": "user", "content": msg})
    
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
    reply = resp.choices[0].message.content
    
    user['history'].append({"role": "user", "content": msg})
    user['history'].append({"role": "assistant", "content": reply})
    db.save_user(user_id, user)
    
    return jsonify({"reply": reply, "is_premium": is_paid, "limit_info": f"{user['count']}/{limit}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
