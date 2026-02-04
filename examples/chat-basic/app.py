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

# 👇 Redis Check
try:
    import redis
except ImportError:
    redis = None

def safe_str_eq(a, b):
    if not a or not b: return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

app = Flask(__name__)

# --- CONFIG ---
DEFAULT_KEY = "START-2026"
ACCESS_KEY = os.environ.get("ACCESS_KEY", DEFAULT_KEY)
if ACCESS_KEY == DEFAULT_KEY:
    print(f"⚠️  WARNING: Using default ACCESS_KEY. Set env var for production.")

REDIS_URL = os.environ.get("REDIS_URL") 
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except:
        print("❌ OpenAI Client Failed to Init")

# --- ECONOMY & MODELS ---
MODEL_FREE = "gpt-4o-mini"
MODEL_PAID = "gpt-4o" 

HARD_LIMIT_FREE_TOTAL = 10 
HARD_LIMIT_PAID_DAILY = 10 

# --- SYSTEM SETTINGS ---
PHOTO_UNLOCK_DAYS = 7 
PHOTO_INTERVAL_DAYS = 7
BACKUP_FILE = "backup_db.json"
MAX_HISTORY_LEN = 20 
REDIS_TTL = 2592000 # 30 Days

# ==========================================
# 🛠️ HELPERS
# ==========================================
def parse_baseline(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    stats = {
        'raw': text,
        'updated': datetime.now().strftime("%Y-%m-%d")
    }
    if len(nums) >= 2:
        stats['height'] = nums[0]
        stats['weight'] = nums[1]
    if len(nums) >= 3:
        stats['age'] = nums[2]
    return stats

def detect_vibe(text):
    t = text.lower()
    if any(w in t for w in ['david', 'laid', 'zyzz', 'aesthetic', 'shredded', 'veins', 'looksmax']): 
        return "AESTHETIC_WARRIOR"
    if any(w in t for w in ['strong', 'power', 'bench', 'deadlift', 'squat', 'heavy']): 
        return "POWERHOUSE"
    if any(w in t for w in ['health', 'longevity', 'balance', 'pain', 'injury', 'yoga']):
        return "MENTOR"
    return None

# ==========================================
# 💾 DATA MANAGER
# ==========================================
class DataManager:
    def __init__(self):
        self.r = None
        self.local_cache = defaultdict(lambda: self._default_schema())
        self.lock = threading.Lock()
        if REDIS_URL and redis:
            try:
                self.r = redis.from_url(REDIS_URL, decode_responses=True)
            except:
                print("❌ Redis connection failed, using memory.")
        if not self.r:
            self._load_from_disk()

    def _default_schema(self):
        return {
            'joined_at': time.time(), 
            'count': 0,       
            'count_free': 0,  
            'last_reset': time.time(),
            'history': [], 
            'onboarding_step': 'HOOK', 
            'profile': {'goal': None, 'stats': {}, 'vibe': 'MENTOR'}, 
            'coach_notes': [], 
            'last_photo_time': 0
        }

    def _load_from_disk(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self.local_cache[k] = v
            except:
                pass

    def _async_save(self):
        def save():
            with self.lock:
                try:
                    with open(BACKUP_FILE, 'w') as f:
                        json.dump(self.local_cache, f)
                except:
                    pass
        threading.Thread(target=save).start()

    def get_user(self, uid):
        if self.r:
            try:
                data = self.r.get(f"user:{uid}")
                if data:
                    return json.loads(data)
            except:
                pass
        return self.local_cache[uid]

    def save_user(self, uid, data):
        if len(data['history']) > MAX_HISTORY_LEN:
            data['history'] = data['history'][-MAX_HISTORY_LEN:]
        if len(data.get('coach_notes', [])) > 5:
            data['coach_notes'] = data['coach_notes'][-5:] 

        if self.r:
            try:
                self.r.set(f"user:{uid}", json.dumps(data), ex=REDIS_TTL)
            except:
                pass
        self.local_cache[uid] = data
        if not self.r:
            self._async_save()

    def reset_user(self, uid):
        self.local_cache[uid] = self._default_schema()
        self.save_user(uid, self.local_cache[uid])

db = DataManager()

# ==========================================
# 🧠 SYSTEM PROMPT
# ==========================================
def get_system_prompt(profile, last_msg=""):
    stats = profile.get('stats', {})
    goal = profile.get('goal', '—')
    vibe = profile.get('vibe', 'MENTOR')
    
    voice_guide = ""
    if vibe == "AESTHETIC_WARRIOR":
        voice_guide = """
        - VOICE: Cold, Visual, Demanding.
        - LEXICON: "Symmetry", "Taper", "Suffering", "Discipline".
        - RULE: Do not overuse keywords. Sound natural.
        """
    elif vibe == "POWERHOUSE":
        voice_guide = """
        - VOICE: Heavy, Grounded, Simple.
        - LEXICON: "Load", "Volume", "Eat", "Sleep", "Grind".
        - RULE: Do not overuse keywords. Sound natural.
        """
    else: # MENTOR
        voice_guide = """
        - VOICE: Calm, Stoic, Experienced.
        - LEXICON: "Consistency", "Patience", "Routine".
        - RULE: Do not overuse keywords. Sound natural.
        """

    states_list = [
        "NORMAL: Direct, helpful but brief.",
        "RUSHED: Extremely short answers. 1-5 words. No explanations.",
        "STERN: No tolerance for weakness. Push back.",
        "LISTENING: Just acknowledge. Say 'Ok', 'Got it', 'Mmhm', or 'Go on'."
    ]
    
    weights = [0.6, 0.2, 0.15, 0.05] 
    if "?" in last_msg:
        weights = [0.8, 0.1, 0.1, 0.0]
    elif len(last_msg.split()) < 4:
        weights = [0.2, 0.1, 0.1, 0.6] 

    current_state = random.choices(states_list, weights=weights, k=1)[0]

    notes = profile.get("coach_notes", [])
    memory = f"[OBSERVATION: {random.choice(notes)}]" if notes else ""

    return f"""
    You are a personal coach. 1-on-1 text chat.
    
    CLIENT CONTEXT:
    - Goal: {goal}
    - Stats: {stats.get('raw', 'N/A')}
    - Vibe: {vibe}
    {memory}
    
    YOUR VOICE SETTINGS:
    {voice_guide}
    
    CURRENT MOOD: {current_state}
    
    CORE RULES:
    1. Text like a human (WhatsApp). Fragments ok. Lowercase ok.
    2. No corporate fluff. No "I hope this helps".
    3. If they ask for a plan too early -> "No plan yet. I don’t guess. Give me data."
    4. If stats contradict -> "Wait. You said X before."
    5. If progress/consistency is visible -> Acknowledge briefly. No hype.
    
    Be real. Not perfect.
    """

# ==========================================
# 🎨 UI (VERSION 66 - GHOST BUSTER)
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content">
    <title>Coach</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="https://img.icons8.com/fluency/192/dumbbell.png">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <meta name="theme-color" content="#ffffff">
    <style>
        :root { --bg: #ffffff; --chat-bg: #f7f7f8; --border: #e5e7eb; --user-msg: #2563eb; --bot-msg: #f3f4f6; --text-main: #111827; --text-muted: #6b7280; --accent: #2563eb; }
        * { box-sizing: border-box; }
        
        /* 🔥 FIXED VIEWPORT FIX */
        html { height: 100%; overflow: hidden; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: var(--bg); color: var(--text-main); 
            height: 100dvh; width: 100%; 
            margin: 0; position: relative; overflow: hidden; 
        }

        .header { position: fixed; top: 0; left: 0; width: 100%; height: 52px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; padding-top: max(10px, env(safe-area-inset-top)); background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 100; }
        .title { font-size: 13px; font-weight: 600; letter-spacing: 0.04em; color: var(--text-muted); }
        .badge { font-size: 11px; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border); cursor: pointer; color: var(--text-muted); }
        .badge.premium { background: var(--accent); color: white; border: none; }
        
        /* 🔥 CHAT AREA PINNED */
        #chat-box { 
            position: fixed; top: 52px; bottom: 70px; left: 0; width: 100%;
            overflow-y: auto; padding: 24px 16px; display: flex; flex-direction: column; gap: 20px; 
            -webkit-overflow-scrolling: touch; background: var(--bg);
        }
        
        .message { max-width: 85%; padding: 14px 16px; border-radius: 12px; font-size: 15px; line-height: 1.5; animation: fadeIn 0.2s forwards; }
        .bot { background: var(--bot-msg); color: var(--text-main); align-self: flex-start; border-bottom-left-radius: 4px; }
        .user { background: var(--user-msg); color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        .message img { max-width: 100%; border-radius: 10px; margin-top: 8px; }
        .sys-event { align-self: center; text-align: center; font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 10px 0; }
        
        /* 🔥 INPUT AREA PINNED */
        .input-area { 
            position: fixed; bottom: 0; left: 0; width: 100%;
            border-top: 1px solid var(--border); padding: 12px; 
            display: flex; gap: 10px; background: var(--bg); 
            padding-bottom: max(15px, env(safe-area-inset-bottom)); 
            z-index: 100;
        }
        
        input[type="text"] { 
            flex: 1; padding: 12px 14px; font-size: 16px; 
            border-radius: 10px; border: 1px solid var(--border); outline: none; 
            background: var(--chat-bg); color: var(--text-main); 
        }
        input[type="text"]:focus { border-color: var(--border); background: #fff; }
        
        .btn-icon { width: 46px; height: 46px; border-radius: 10px; border: 1px solid var(--border); background: white; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; }
        .btn-send { background: var(--accent); color: white; border: none; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        #modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: none; align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(2px); }
        .modal-content { background: white; padding: 24px; border-radius: 16px; width: 90%; max-width: 320px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        .modal-content input { width: 100%; margin: 16px 0; padding: 12px; font-size: 18px; text-align: center; letter-spacing: 2px; border: 1px solid var(--border); border-radius: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">COACH V66</div>
        <div id="badge" class="badge" onclick="openModal()">ACCESS</div>
    </div>
    
    <div id="chat-box"></div>
    
    <div class="input-area">
        <input type="file" id="fileInp" accept="image/*" style="display:none" tabindex="-1" aria-hidden="true" onchange="handleFile(this)">
        <button class="btn-icon" style="color: #6b7280;" onclick="document.getElementById('fileInp').click()">📷</button>
        
        <input type="text" id="inp" placeholder="Message..." 
               autocomplete="off" autocorrect="off" autocapitalize="sentences" spellcheck="false"
               enterkeyhint="send" onkeypress="if(event.key==='Enter') send()">
        
        <button id="sendBtn" class="btn-icon btn-send" onclick="send()">↑</button>
    </div>
    
    <div id="modal">
        <div class="modal-content">
            <h3 style="color:#111827; margin:0; font-size:16px;">MEMBER ACCESS</h3>
            <input type="hidden" id="key-val" placeholder="ENTER KEY">
            <button class="btn-icon btn-send" style="width:100%; height:auto; padding:12px; font-size:14px; font-weight:600;" onclick="verifyAndSave()">UNLOCK</button>
            <p onclick="closeModal()" style="margin-top:20px; color:#6b7280; font-size:12px; cursor:pointer;">Close</p>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat-box');
        const inp = document.getElementById('inp');
        const keyInp = document.getElementById('key-val');
        
        let deviceId = localStorage.getItem('coach_uid');
        if (!deviceId) { deviceId = 'user_' + Math.random().toString(36).substr(2, 9); localStorage.setItem('coach_uid', deviceId); }

        function openModal() { 
            document.getElementById('modal').style.display='flex';
            // 🔥 Switch to text ONLY when visible
            keyInp.type = 'text';
            keyInp.focus();
        }
        
        function closeModal() {
            document.getElementById('modal').style.display='none';
            // 🔥 Switch back to hidden to kill arrows
            keyInp.type = 'hidden';
            keyInp.blur();
        }
        
        function verifyAndSave() {
            const val = keyInp.value.trim();
            fetch('/verify', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({access_key: val}) })
            .then(r => r.json()).then(d => { 
                if (d.valid) { localStorage.setItem('coach_key', val); location.reload(); } 
                else { alert("Invalid Key"); } 
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
        if (hist.length > 0) {
            hist.forEach(m => addMsg(m.content, m.role === 'user' ? 'user' : 'bot'));
        } else {
            send("SYSTEM_INIT_TRIGGER");
        }
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
    
    is_paid = safe_str_eq(ukey, ACCESS_KEY)

    if msg == "SYSTEM_INIT_TRIGGER":
        return jsonify({
            "reply": "I’m your coach.\n\n**What is your goal?**",
            "type": "bot",
            "is_premium": is_paid
        })

    if not client: return jsonify({"reply": "AI OFFLINE", "type": "sys-error"})

    user = db.get_user(user_id)
    current_time = time.time()

    if not is_paid:
        user_free_count = user.get('count_free', 0)
        if user_free_count >= HARD_LIMIT_FREE_TOTAL:
            return jsonify({"reply": "💬 Бесплатный осмотр окончен. Чтобы тренироваться дальше, нужен доступ.", "type": "sys-event"}) 
    else:
        if (current_time - user.get('last_reset', 0)) > 86400:
            user['count'] = 0
            user['last_reset'] = current_time
        if user['count'] >= HARD_LIMIT_PAID_DAILY:
            return jsonify({"reply": "💤 На сегодня всё (10/10). Дисциплина — это и отдых тоже. До завтра.", "type": "sys-event"})

    if not img_data:
        stranger_keywords = r"\b(friend|partner|brother|sister|wife|husband|mom|dad)\b"
        self_keywords = r"\b(i|me|myself)\b"
        if re.search(stranger_keywords, msg.lower()) and not re.search(self_keywords, msg.lower()):
            return jsonify({"reply": "✋ I coach **YOU**. I don't build plans for strangers.", "type": "bot"})

    if img_data:
        if not is_paid: return jsonify({"reply": "📷 **Photo Analysis is Premium.**", "type": "sys-error"})
        if (current_time - user.get('joined_at', current_time)) / 86400 < PHOTO_UNLOCK_DAYS:
             return jsonify({"reply": f"✋ **Not yet.**\nWe just started. I need to see your discipline first.", "type": "bot"})

        try:
            resp = client.chat.completions.create(
                model=MODEL_PAID, 
                messages=[
                    {"role": "system", "content": "Analyze physique. Brutally honest. 2 sentences max."},
                    {"role": "user", "content": [{"type": "text", "text": "Analyze."}, {"type": "image_url", "image_url": {"url": img_data}}]}
                ],
                max_tokens=150, temperature=0.6
            )
            analysis = resp.choices[0].message.content
            user['coach_notes'].append(f"[OBSERVATION: Visual {datetime.now().strftime('%m-%d')}: {analysis[:50]}...]")
            user['last_photo_time'] = current_time
            db.save_user(user_id, user)
            return jsonify({"reply": analysis, "is_premium": True})
        except: return jsonify({"reply": "Image Error", "type": "sys-error"})

    if user.get('onboarding_step') != 'DONE':
        if user['onboarding_step'] == 'HOOK':
            user['profile']['goal'] = msg 
            user['profile']['vibe'] = detect_vibe(msg) or "MENTOR"
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

    if user.get('onboarding_step') == 'DONE' and len(msg.split()) > 5:
        new_vibe = detect_vibe(msg)
        current_vibe = user['profile'].get('vibe')
        if new_vibe and new_vibe != current_vibe:
            user['profile']['vibe'] = new_vibe
            user['coach_notes'].append(f"[SHIFT: Focus moved to {new_vibe}]")
            db.save_user(user_id, user)

    user['count'] += 1 
    
    sys_prompt = get_system_prompt(user['profile'], msg)
    messages = [{"role": "system", "content": sys_prompt}]
    clean_history = [m for m in user['history'] if m.get('content') != "SYSTEM_INIT_TRIGGER"][-12:]
    messages.extend(clean_history)
    messages.append({"role": "user", "content": msg})
    
    time.sleep(random.uniform(0.5, 2.5))

    try:
        model_to_use = MODEL_PAID if is_paid else MODEL_FREE
        resp = client.chat.completions.create(model=model_to_use, messages=messages, temperature=0.65)
        reply = resp.choices[0].message.content.strip()
        if not reply: reply = "..."
        
        user['history'].append({"role": "user", "content": msg})
        user['history'].append({"role": "assistant", "content": reply})
        
        if not is_paid:
            user['count_free'] = user.get('count_free', 0) + 1
        
        db.save_user(user_id, user)
        return jsonify({"reply": reply, "is_premium": is_paid})
    except: return jsonify({"reply": "Connection Error", "type": "sys-error"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
