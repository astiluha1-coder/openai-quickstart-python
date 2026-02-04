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

try: import redis
except ImportError: redis = None

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

# --- SYSTEM SETTINGS ---
PHOTO_UNLOCK_DAYS = 7 
PHOTO_INTERVAL_DAYS = 7
HARD_LIMIT_FREE = 30
HARD_LIMIT_PAID = 60
BACKUP_FILE = "backup_db.json"
MAX_HISTORY_LEN = 20 

# ==========================================
# 🛠️ HELPERS
# ==========================================
def parse_baseline(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if len(nums) >= 2:
        return {'raw': text, 'height': nums[0], 'weight': nums[1], 'updated': datetime.now().strftime("%Y-%m-%d")}
    return {'raw': text, 'updated': datetime.now().strftime("%Y-%m-%d")}

def detect_vibe(text):
    t = text.lower()
    if any(w in t for w in ['david', 'laid', 'zyzz', 'aesthetic', 'shredded', 'veins']): return "AESTHETIC_WARRIOR"
    if any(w in t for w in ['strong', 'power', 'bench', 'deadlift', 'squat']): return "POWERHOUSE"
    return "MENTOR"

# ==========================================
# 💾 DATA MANAGER
# ==========================================
class DataManager:
    def __init__(self):
        self.r = None
        self.local_cache = defaultdict(lambda: self._default_schema())
        self.lock = threading.Lock()
        if REDIS_URL and redis:
            try: self.r = redis.from_url(REDIS_URL, decode_responses=True)
            except: pass
        if not self.r: self._load_from_disk()

    def _default_schema(self):
        return {
            'joined_at': time.time(), 'count': 0, 'last_reset': time.time(),
            'history': [], 'onboarding_step': 'HOOK', 
            'profile': {'goal': None, 'stats': {}, 'vibe': 'MENTOR'}, 
            'coach_notes': [], 'last_photo_time': 0
        }

    def _load_from_disk(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items(): self.local_cache[k] = v
            except: pass

    def _async_save(self):
        def save():
            with self.lock:
                try: with open(BACKUP_FILE, 'w') as f: json.dump(self.local_cache, f)
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
        if len(data['history']) > MAX_HISTORY_LEN: data['history'] = data['history'][-MAX_HISTORY_LEN:]
        if self.r:
            try: self.r.set(f"user:{uid}", json.dumps(data), ex=604800)
            except: pass
        self.local_cache[uid] = data
        if not self.r: self._async_save()

db = DataManager()

# ==========================================
# 🧠 SYSTEM PROMPT (IMPERFECT & ALIVE)
# ==========================================
def get_system_prompt(profile):
    stats = profile.get('stats', {})
    goal = profile.get('goal', '—')
    vibe = profile.get('vibe', 'MENTOR')
    
    # 🔥 DYNAMIC MOOD (Human Variance)
    # The coach isn't always the same. Sometimes he's busy. Sometimes he listens.
    states = [
        "NORMAL: Direct, helpful but brief.",
        "RUSHED: Extremely short answers. 1-5 words. No explanations.",
        "STERN: No tolerance for weakness. Push back.",
        "LISTENING: Just acknowledge. Say 'Ok' or 'Go on'."
    ]
    current_state = random.choices(states, weights=[0.6, 0.15, 0.15, 0.1], k=1)[0]

    # Memory Injection
    notes = profile.get("coach_notes", [])
    memory = f"INTERNAL NOTE: {random.choice(notes)}" if notes else ""

    return f"""
    You are a personal coach. 1-on-1 text chat.
    
    CLIENT: {goal} | Vibe: {vibe}
    STATS: {stats.get('raw', 'N/A')}
    {memory}
    
    YOUR CURRENT STATE: {current_state}
    
    BEHAVIOR:
    - Text like a human (WhatsApp/iMessage). Lowercase ok. Fragments ok.
    - You DON'T always coach. Sometimes just acknowledge ("Ok", "Noted", "Good").
    - If a question is irrelevant, ignore it or say "Focus."
    - No corporate fluff. No "I hope this helps".
    - If they ask for a plan too early -> "No. I need more info."
    - If stats contradict -> "Wait. You said X before."
    
    Be real. Not perfect.
    """

# ==========================================
# 🎨 UI (PREMIUM DARK MODE)
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
    <meta name="theme-color" content="#0f172a">
    <style>
        :root { --bg: #0f172a; --chat-bg: #1e293b; --user-msg: #2563eb; --bot-msg: #334155; --text: #f8fafc; --accent: #3b82f6; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; margin: 0; overflow: hidden; }
        .header { background: var(--bg); padding: 15px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; padding-top: max(15px, env(safe-area-inset-top)); }
        .title { font-weight: 800; font-size: 14px; letter-spacing: 2px; color: #94a3b8; }
        .badge { background: #334155; padding: 5px 10px; border-radius: 6px; font-size: 10px; font-weight: 600; cursor: pointer; border: 1px solid #475569; }
        .badge.premium { background: var(--accent); color: white; border: none; }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; padding-bottom: 40px; }
        
        .message { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 16px; line-height: 1.4; animation: fadeIn 0.2s forwards; }
        .bot { align-self: flex-start; background: var(--bot-msg); border-bottom-left-radius: 4px; color: #e2e8f0; }
        .user { align-self: flex-end; background: var(--user-msg); color: white; border-bottom-right-radius: 4px; }
        .message img { max-width: 100%; border-radius: 12px; margin-top: 8px; }
        
        .sys-event { align-self: center; color: #64748b; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 20px 0; text-align: center; letter-spacing: 1px; }
        
        .input-area { padding: 15px; background: var(--bg); display: flex; gap: 10px; border-top: 1px solid #334155; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        input { flex: 1; padding: 14px; background: var(--chat-bg); border: 1px solid #475569; border-radius: 12px; font-size: 16px; color: white; outline: none; }
        input:focus { border-color: var(--accent); }
        
        .btn-icon { background: var(--bot-msg); color: #94a3b8; border: none; width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .btn-send { background: var(--accent); color: white; font-weight: bold; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        #modal { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); backdrop-filter: blur(5px); display:none; justify-content:center; align-items:center; z-index: 999; }
        .modal-content { background: var(--chat-bg); padding: 30px; border-radius: 16px; text-align:center; width: 85%; max-width: 320px; border: 1px solid #475569; }
        .modal-content input { width: 100%; margin: 20px 0; padding: 12px; background: #0f172a; border: 1px solid #475569; color: white; text-align: center; font-size: 18px; letter-spacing: 3px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">COACH</div>
        <div id="badge" class="badge" onclick="openModal()">ACCESS</div>
    </div>
    <div id="chat-box"></div>
    <div class="input-area">
        <input type="file" id="fileInp" accept="image/*" style="display:none" onchange="handleFile(this)">
        <button class="btn-icon" onclick="document.getElementById('fileInp').click()">📷</button>
        <input type="text" id="inp" placeholder="Message..." autocomplete="off" onkeypress="if(event.key==='Enter') send()">
        <button id="sendBtn" class="btn-icon btn-send" onclick="send()">↑</button>
    </div>
    
    <div id="modal">
        <div class="modal-content">
            <h3 style="color:white; margin:0;">MEMBER KEY</h3>
            <input type="text" id="key-val" placeholder="START-202X">
            <button class="btn-icon btn-send" style="width:100%; height:auto; padding:12px;" onclick="verifyAndSave()">UNLOCK</button>
            <p onclick="document.getElementById('modal').style.display='none'" style="margin-top:20px; color:#64748b; font-size:12px; cursor:pointer;">CANCEL</p>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat-box');
        const inp = document.getElementById('inp');
        let deviceId = localStorage.getItem('coach_uid');
        if (!deviceId) { deviceId = 'user_' + Math.random().toString(36).substr(2, 9); localStorage.setItem('coach_uid', deviceId); }

        function openModal() { document.getElementById('modal').style.display='flex'; }
        
        function verifyAndSave() {
            const val = document.getElementById('key-val').value.trim();
            fetch('/verify', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({access_key: val}) })
            .then(r => r.json()).then(d => {
                if (d.valid) { localStorage.setItem('coach_key', val); location.reload(); } else { alert("Invalid Key"); }
            });
        }

        function addMsg(text, type, imgUrl=null) {
            const d = document.createElement('div');
            d.className = 'message ' + type;
            if (imgUrl) {
                d.innerHTML = `<img src="${imgUrl}" style="max-height:150px; display:block; margin-bottom:8px;">` + (text || "Analyzing...");
            } else if (type === 'user') {
                d.innerText = text;
            } else {
                if(type.includes('sys-')) { d.className = 'sys-event'; d.innerText = text; } 
                else { 
                    let clean = text.replace(/\\n\\n\\n/g, "\\n\\n");
                    d.innerHTML = marked.parse(clean); 
                }
            }
            chat.appendChild(d); chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
        }

        function handleFile(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const img = new Image(); img.src = e.target.result;
                    img.onload = function() {
                        const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d');
                        const MAX_W = 800; let w=img.width; let h=img.height;
                        if(w>MAX_W){ h*=MAX_W/w; w=MAX_W; }
                        canvas.width=w; canvas.height=h; ctx.drawImage(img,0,0,w,h);
                        send(null, canvas.toDataURL('image/jpeg', 0.7));
                    }
                }; reader.readAsDataURL(input.files[0]);
            }
        }

        function send(force=null, imgData=null) {
            let val = force || inp.value.trim();
            if (!val && !imgData) return;
            if (!force) addMsg(val, 'user', imgData);
            inp.value = ''; 
            
            const payload = {
                message: val || "Analyze this photo.",
                image: imgData,
                access_key: localStorage.getItem('coach_key'), 
                device_id: deviceId
            };

            fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) })
            .then(r=>r.json()).then(d=>{
                if (d.is_premium) { document.getElementById('badge').innerText="PREMIUM"; document.getElementById('badge').classList.add("premium"); }
                addMsg(d.reply, d.type || 'bot');
            })
            .catch(() => addMsg("Connection Error", "sys-error"));
        }

        const hist = JSON.parse(localStorage.getItem('coach_history') || "[]");
        send("SYSTEM_INIT_TRIGGER");
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_PAGE)

@app.route('/verify', methods=['POST'])
def verify():
    key = request.json.get('access_key', '')
    if safe_str_eq(key, ACCESS_KEY): return jsonify({"valid": True})
    return jsonify({"valid": False})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get("message", "").strip()
    img_data = data.get("image")
    ukey = data.get("access_key", "")
    user_id = data.get("device_id")
    
    if not client: return jsonify({"reply": "AI OFFLINE", "type": "sys-error"})

    user = db.get_user(user_id)
    current_time = time.time()
    is_paid = safe_str_eq(ukey, ACCESS_KEY)

    if (current_time - user['last_reset']) > 86400:
        user['count'] = 0; user['last_reset'] = current_time

    # 🛑 "STRANGER" FILTER
    if not img_data and re.search(r"\b(friend|partner|brother|sister|wife|husband)\b", msg.lower()):
        return jsonify({"reply": "✋ I coach **YOU**. No plans for strangers.", "type": "bot"})

    # 📸 PHOTO ANALYSIS
    if img_data:
        if not is_paid: return jsonify({"reply": "📷 **Photo Analysis is Premium.**", "type": "sys-error"})
        if (current_time - user.get('joined_at', current_time)) / 86400 < PHOTO_UNLOCK_DAYS:
             return jsonify({"reply": f"✋ **Not yet.** Earn it. Discipline first.", "type": "bot"})

        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Analyze physique. Brutally honest. 2 sentences max."},
                    {"role": "user", "content": [{"type": "text", "text": "Analyze."}, {"type": "image_url", "image_url": {"url": img_data}}]}
                ],
                max_tokens=150, temperature=0.6
            )
            analysis = resp.choices[0].message.content
            user['coach_notes'].append(f"Visual {datetime.now().strftime('%m-%d')}: {analysis[:50]}...")
            user['last_photo_time'] = current_time
            db.save_user(user_id, user)
            return jsonify({"reply": analysis, "is_premium": True})
        except: return jsonify({"reply": "Image Error", "type": "sys-error"})

    # 🛤️ ONBOARDING
    if user.get('onboarding_step') != 'DONE':
        if msg == "SYSTEM_INIT_TRIGGER":
            if user['onboarding_step'] == 'HOOK': 
                return jsonify({"reply": "Alright. I’m your coach.\n\nTell me honestly:\n**what body do you want to see in the mirror in 6 months?**", "type": "bot"})
            return jsonify({"reply": "Session resumed.", "type": "sys-event"})

        if user['onboarding_step'] == 'HOOK':
            user['profile']['goal'] = msg 
            user['profile']['vibe'] = detect_vibe(msg)
            user['onboarding_step'] = 'BASELINE'
            db.save_user(user_id, user)
            time.sleep(1)
            return jsonify({"reply": "Got it. I can get you there.\n\nNeed facts:\n**Height (cm), Weight (kg), Age.**", "type": "bot"})
        
        if user['onboarding_step'] == 'BASELINE':
            stats = parse_baseline(msg)
            if not stats.get('height'): return jsonify({"reply": "Need numbers. Height & Weight.", "type": "bot"})
            user['profile']['stats'] = stats; user['onboarding_step'] = 'DONE'; db.save_user(user_id, user)
            time.sleep(1)
            return jsonify({"reply": "Profile locked. \n\nYou're not in a bad spot, but getting there takes discipline, not motivation.\n\n**Tell me exactly how you train right now.**", "type": "bot"})

    # CHAT
    limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE
    if user['count'] >= limit: return jsonify({"reply": "Enough for today. Rest."})
    
    user['count'] += 1
    sys_prompt = get_system_prompt(user['profile'])
    
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend([m for m in user['history'] if m.get('content') != "SYSTEM_INIT_TRIGGER"][-12:])
    messages.append({"role": "user", "content": msg})
    
    time.sleep(random.uniform(0.5, 2.5)) # 🧠 THINKING PAUSE

    try:
        resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.65) # 🔥 HIGH VARIANCE
        reply = resp.choices[0].message.content.strip()
        user['history'].append({"role": "user", "content": msg})
        user['history'].append({"role": "assistant", "content": reply})
        db.save_user(user_id, user)
        return jsonify({"reply": reply, "is_premium": is_paid})
    except: return jsonify({"reply": "Connection Error", "type": "sys-error"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
