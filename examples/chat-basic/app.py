import os
import time
import json
import random
import threading
import hmac
from flask import Flask, request, jsonify, render_template
from collections import defaultdict
from openai import OpenAI

# --- CONFIG ---
# ACCESS_KEY используется для проверки PRO-статуса. По умолчанию: START-2026
ACCESS_KEY = os.environ.get("ACCESS_KEY", "START-2026")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_HISTORY = 50
FREE_MSG_LIMIT = 10

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("OpenAI init error:", e)

app = Flask(__name__, template_folder='templates')

# ==========================================
# 🛠️ DATA MANAGEMENT (Управление данными)
# ==========================================
class DataManager:
    def __init__(self):
        self.local = defaultdict(lambda: self._schema())
        self.lock = threading.Lock()
        self.backup_file = "backup_db.json"
        self._load()

    def _schema(self):
        return {'history': [], 'count_free': 0, 'count_paid': 0, 'profile': {'vibe':'MENTOR'}, 'step':'HOOK'}

    def _load(self):
        if os.path.exists(self.backup_file):
            try:
                with open(self.backup_file) as f:
                    d = json.load(f)
                    for k,v in d.items():
                        self.local[k] = v
            except: pass

    def _save(self):
        def task():
            with self.lock:
                try:
                    with open(self.backup_file,'w') as f:
                        json.dump(self.local, f)
                except: pass
        threading.Thread(target=task).start()

    def get(self, uid):
        return self.local[uid]

    def set(self, uid, data):
        if len(data['history']) > MAX_HISTORY:
            data['history'] = data['history'][-MAX_HISTORY:]
        self.local[uid] = data
        self._save()

db = DataManager()

def safe_eq(a, b):
    if not a or not b: return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

def detect_vibe(text):
    t = text.lower()
    if any(w in t for w in ['aesthetic','david','laid']):
        return "AESTHETIC"
    if any(w in t for w in ['power','squat','bench']):
        return "POWER"
    return "MENTOR"

def get_sys(profile):
    vibe = profile.get('vibe','MENTOR')
    guide = "Be calm."
    if vibe == "AESTHETIC":
        guide = "Focus on symmetry, aesthetics, discipline. Cold tone."
    elif vibe == "POWER":
        guide = "Focus on strength, load, eating. Heavy tone."
    return f"Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. Rules: Human tone. Short answers. No fluff."

# ==========================================
# 🖥️ ROUTES (Маршруты)
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    return jsonify({"ok": safe_eq(request.json.get('k'), ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    data = request.json
    uid, mid, new_text = data.get('uid'), data.get('mid'), data.get('new_text')
    user = db.get(uid)
    for m in user['history']:
        if m.get('id') == mid:
            m['c'] = new_text
            break
    db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    data = request.json
    uid, mid = data.get('uid'), data.get('mid')
    user = db.get(uid)
    user['history'] = [m for m in user['history'] if m.get('id') != mid]
    db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/history', methods=['POST'])
def history():
    d = request.json
    uid, key = d.get('uid'), d.get('k')
    user = db.get(uid)
    is_paid = safe_eq(key, ACCESS_KEY)
    # Генерация ID для старых сообщений, если их нет
    for m in user['history']:
        if 'id' not in m: 
            m['id'] = 'm' + str(int(time.time()*1000) + random.randint(0,999))
    return jsonify({"history": user['history'], "pro": is_paid})

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    msg, img, uid, key = d.get('msg'), d.get('img'), d.get('uid'), d.get('k')
    paid = safe_eq(key, ACCESS_KEY)
    user = db.get(uid)

    if msg == "SYSTEM_INIT_TRIGGER":
        return jsonify({"reply": "I'm your coach. What is your goal?", "pro": paid})

    if not paid and user['count_free'] >= FREE_MSG_LIMIT:
        return jsonify({"reply": "Free limit reached. Please unlock PRO.", "pro": paid})

    reply = "..."
    if not client:
        reply = "AI Offline (check API key)"
    else:
        try:
            sys_p = get_sys(user['profile'])
            msgs = [{"role": "system", "content": sys_p}]
            
            # Добавление контекста (последние 6 сообщений)
            for m in user['history'][-6:]:
                role = 'user' if m['r'] == 'usr' else 'assistant'
                msgs.append({'role': role, 'content': m['c']})

            if img:
                if not paid: 
                    reply = "Photos are Premium."
                else:
                    msgs.append({
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": "Analyze this image for my fitness goals."},
                            {"type": "image_url", "image_url": {"url": img}}
                        ]
                    })
                    r = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
                    reply = r.choices[0].message.content
            else:
                if user['step'] == 'HOOK':
                    user['profile']['goal'] = msg
                    user['profile']['vibe'] = detect_vibe(msg)
                    user['step'] = 'BASE'
                    reply = "Got it. Height/Weight?"
                elif user['step'] == 'BASE':
                    user['profile']['stats'] = msg
                    user['step'] = 'DONE'
                    reply = "Locked. How do you train?"
                else:
                    msgs.append({"role": "user", "content": msg})
                    # Используем доступную модель gpt-4o-mini
                    r = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
                    reply = r.choices[0].message.content
        except Exception as e:
            print("Error:", e)
            reply = "Error generating response."

    # Сохранение в историю с уникальными ID
    new_mid_user = 'm' + str(int(time.time()*1000))
    new_mid_bot = 'm' + str(int(time.time()*1000) + 1)
    user['history'].append({'r': 'usr', 'c': msg or '[IMG]', 'id': new_mid_user})
    user['history'].append({'r': 'bot', 'c': reply, 'id': new_mid_bot})

    if paid: 
        user['count_paid'] += 1
    else: 
        user['count_free'] += 1

    db.set(uid, user)
    return jsonify({"reply": reply, "pro": paid})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
