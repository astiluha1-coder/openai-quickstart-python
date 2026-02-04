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
REDIS_URL = os.environ.get("REDIS_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except:
        pass

MODEL_FREE = "gpt-4o-mini"
MODEL_PAID = "gpt-4o"
HARD_LIMIT_FREE = 10
HARD_LIMIT_PAID = 10
BACKUP_FILE = "backup_db.json"
MAX_HISTORY = 50
REDIS_TTL = 2592000

try:
    import redis
except ImportError:
    redis = None

def safe_str_eq(a, b):
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

app = Flask(__name__, template_folder='templates')

# ==========================================
# 🛠️ DATA MANAGEMENT
# ==========================================
class DataManager:
    def __init__(self):
        self.r = None
        self.local = defaultdict(lambda: self._schema())
        self.lock = threading.Lock()
        if REDIS_URL and redis:
            try:
                self.r = redis.from_url(REDIS_URL, decode_responses=True)
            except: pass
        if not self.r:
            self._load()

    def _schema(self):
        return {'history': [], 'step': 'HOOK', 'profile': {'vibe': 'MENTOR'}, 'count': 0, 'count_free': 0, 'last': time.time()}

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
        if self.r:
            try:
                d = self.r.get(f"u:{uid}")
                if d:
                    return json.loads(d)
            except: pass
        return self.local[uid]

    def set(self, uid, data):
        if len(data['history']) > MAX_HISTORY:
            data['history'] = data['history'][-MAX_HISTORY:]
        if self.r:
            try:
                self.r.set(f"u:{uid}", json.dumps(data), ex=REDIS_TTL)
            except: pass
        self.local[uid] = data
        if not self.r:
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
    found = False
    for m in user['history']:
        if m.get('id') == mid or m.get('id')==str(mid):
            m['c'] = new_text
            found = True
            break
    if found:
        db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    data = request.json
    uid, mid = data.get('uid'), data.get('mid')
    user = db.get(uid)
    original_len = len(user['history'])
    user['history'] = [m for m in user['history'] if m.get('id') != mid and m.get('id')!=str(mid)]
    if len(user['history']) != original_len:
        db.set(uid, user)
    return jsonify({"ok": True})

@app.route('/history', methods=['POST'])
def history():
    d = request.json
    uid,key = d.get('uid'), d.get('k')
    user = db.get(uid)
    is_paid = safe_str_eq(key, ACCESS_KEY)
    # Ensure IDs exist for legacy messages
    for m in user['history']:
        if 'id' not in m:
            m['id'] = 'm'+str(int(time.time()*1000)+random.randint(0,999))
    return jsonify({"history": user['history'], "pro": is_paid})

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    msg, img, uid, key = d.get('msg'), d.get('img'), d.get('uid'), d.get('k')
    paid = safe_str_eq(key, ACCESS_KEY)
    
    if msg=="SYSTEM_INIT_TRIGGER":
        return jsonify({"reply":"I'm your coach. What is your goal?","pro":paid})
        
    user = db.get(uid)
    
    if not paid and user['count_free'] >= HARD_LIMIT_FREE:
        return jsonify({"reply":"Free limit reached. Access required."})
    if paid and user['count'] >= HARD_LIMIT_PAID:
        return jsonify({"reply":"Daily limit reached."})
        
    reply="..."
    if not client:
        reply="AI Offline (Check API Key)"
    else:
        try:
            model = MODEL_PAID if paid else MODEL_FREE
            sys_p = get_sys(user['profile'])
            msgs=[{"role":"system","content":sys_p}]
            
            if img:
                if not paid: reply="Photos are Premium."
                else:
                    msgs.append({"role":"user","content":[{"type":"text","text":"Analyze"},{"type":"image_url","image_url":{"url":img}}]})
                    r=client.chat.completions.create(model=model,messages=msgs)
                    reply=r.choices[0].message.content
            else:
                # Simple state machine for onboarding
                if user['step']=='HOOK':
                    user['profile']['goal']=msg
                    user['profile']['vibe']=detect_vibe(msg)
                    user['step']='BASE'
                    reply="Got it. Height/Weight?"
                elif user['step']=='BASE':
                    user['profile']['stats']=msg
                    user['step']='DONE'
                    reply="Locked. How do you train?"
                else:
                    # Build context
                    context_msgs=[]
                    for m in user['history'][-6:]:
                        role='user' if m['r']=='usr' else 'assistant'
                        context_msgs.append({'role':role,'content':m['c']})
                    msgs.extend(context_msgs)
                    msgs.append({"role":"user","content":msg})
                    
                    r=client.chat.completions.create(model=model,messages=msgs)
                    reply=r.choices[0].message.content
        except Exception as e:
            print(f"Error: {e}")
            reply="Error generating response."
            
    # Save to history with IDs
    new_mid_user='m'+str(int(time.time()*1000))
    new_mid_bot='m'+str(int(time.time()*1000)+1)
    
    user['history'].append({'r':'usr','c':msg or '[IMG]','id':new_mid_user})
    user['history'].append({'r':'bot','c':reply,'id':new_mid_bot})
    
    if not paid:
        user['count_free'] +=1
    else:
        user['count'] +=1
    db.set(uid,user)
    
    return jsonify({"reply":reply,"pro":paid})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
