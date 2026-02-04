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
DEFAULT_KEY = "START-2026"
ACCESS_KEY = os.environ.get("ACCESS_KEY", DEFAULT_KEY)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"OpenAI init error: {e}")

MODEL_FREE = "gpt-5-mini"
MODEL_PAID = "gpt-5-mini"
BACKUP_FILE = "backup_db.json"
MAX_HISTORY = 50

app = Flask(__name__, template_folder='templates')

# ==========================================
# 🛠️ DATA MANAGEMENT
# ==========================================
class DataManager:
    def __init__(self):
        self.local = defaultdict(lambda: self._schema())
        self.lock = threading.Lock()
        self._load()

    def _schema(self):
        return {'history': [], 'step': 'HOOK', 'profile': {'vibe': 'MENTOR'}, 'count_free': 0, 'count': 0, 'last': time.time()}

    def _load(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE) as f:
                    d = json.load(f)
                    for k, v in d.items():
                        self.local[k] = v
            except: pass

    def _save(self):
        def task():
            with self.lock:
                try:
                    with open(BACKUP_FILE, 'w') as f:
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
    if vibe=="AESTHETIC":
        guide = "Focus on symmetry, aesthetics, discipline. Cold tone."
    elif vibe=="POWER":
        guide = "Focus on strength, load, eating. Heavy tone."
    return f"""Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. 
Context: {profile.get('goal','New client')}. 
Rules: Human tone. Short answers. No fluff."""

def safe_str_eq(a, b):
    if not a or not b: return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

# ==========================================
# 🖥️ ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    return jsonify({"ok": safe_str_eq(request.json.get('k'), ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    data = request.json
    uid, mid, new_text = data.get('uid'), data.get('mid'), data.get('new_text')
    user = db.get(uid)
    for m in user['history']:
        if m.get('id') == mid or m.get('id')==str(mid):
            m['c'] = new_text
            break
    db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    data = request.json
    uid, mid = data.get('uid'), data.get('mid')
    user = db.get(uid)
    user['history'] = [m for m in user['history'] if m.get('id') != mid and m.get('id')!=str(mid)]
    db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/history', methods=['POST'])
def history():
    d = request.json
    uid,key = d.get('uid'), d.get('k')
    user = db.get(uid)
    # Ensure IDs exist
    for m in user['history']:
        if 'id' not in m:
            m['id'] = 'm'+str(int(time.time()*1000)+random.randint(0,999))
    is_paid = safe_str_eq(key, ACCESS_KEY)
    return jsonify({"history": user['history'], "pro": is_paid})

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    msg, img, uid, key = d.get('msg'), d.get('img'), d.get('uid'), d.get('k')
    paid = safe_str_eq(key, ACCESS_KEY)
    user = db.get(uid)

    # Free 10 messages limit
    if not paid and user['count_free'] >= 10:
        return jsonify({"reply":"Your 10 free messages limit reached.","pro":paid})

    reply="..."
    if not client:
        reply="AI Offline (Check API Key)"
    else:
        try:
            sys_p = get_sys(user['profile'])
            msgs=[{"role":"system","content":sys_p}]
            
            if img:
                msgs.append({"role":"user","content":[{"type":"text","text":"Analyze"},{"type":"image_url","image_url":{"url":img}}]})
                r = client.chat.completions.create(model=MODEL_FREE, messages=msgs)
                reply = r.choices[0].message.content
            else:
                # Onboarding
                if user['step']=='HOOK':
                    user['profile']['goal'] = msg
                    user['profile']['vibe'] = detect_vibe(msg)
                    user['step'] = 'BASE'
                    reply = "Got it. Height/Weight?"
                elif user['step']=='BASE':
                    user['profile']['stats'] = msg
                    user['step'] = 'DONE'
                    reply = "Locked. How do you train?"
                else:
                    # Last 6 messages context
                    context_msgs=[]
                    for m in user['history'][-6:]:
                        role='user' if m['r']=='usr' else 'assistant'
                        context_msgs.append({'role':role,'content':m['c']})
                    context_msgs.append({"role":"user","content":msg})
                    r = client.chat.completions.create(model=MODEL_FREE, messages=[{"role":"system","content":sys_p}]+context_msgs)
                    reply = r.choices[0].message.content
        except Exception as e:
            print(f"Error: {e}")
            reply = "Error generating response."

    # Save history with IDs
    new_mid_user = 'm'+str(int(time.time()*1000))
    new_mid_bot = 'm'+str(int(time.time()*1000)+1)
    user['history'].append({'r':'usr','c':msg or '[IMG]','id':new_mid_user})
    user['history'].append({'r':'bot','c':reply,'id':new_mid_bot})

    if not paid:
        user['count_free'] += 1
    db.set(uid,user)

    return jsonify({"reply":reply,"pro":paid})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
