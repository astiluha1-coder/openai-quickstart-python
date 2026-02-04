import os, time, json, random, threading, hmac
from flask import Flask, request, jsonify, render_template
from collections import defaultdict
from openai import OpenAI

# --- CONFIG ---
ACCESS_KEY = os.environ.get("ACCESS_KEY","START-2026")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__, template_folder='templates')
MAX_HISTORY = 50
BACKUP_FILE = "backup_db.json"

# --- DATA ---
db_lock = threading.Lock()
# Используем defaultdict для автоматической инициализации новых пользователей
db = defaultdict(lambda: {"history":[],"step":"HOOK","profile":{"vibe":"MENTOR"},"count":0})

# --- LOAD BACKUP ---
if os.path.exists(BACKUP_FILE):
    try:
        with open(BACKUP_FILE) as f:
            data = json.load(f)
            for k,v in data.items():
                db[k] = v
    except: pass

def save_db():
    """Функция фонового сохранения данных в JSON файл"""
    def task():
        with db_lock:
            try:
                with open(BACKUP_FILE, 'w') as f:
                    json.dump(db, f)
            except: pass
    threading.Thread(target=task).start()

# --- HELPERS ---
def safe_eq(a,b):
    """Безопасное сравнение ключей через hmac"""
    if not a or not b: return False
    return hmac.compare_digest(a.encode(),b.encode())

def detect_vibe(text):
    """Определение стиля коучинга по ключевым словам"""
    t=text.lower()
    if any(w in t for w in ["aesthetic","david","laid"]): return "AESTHETIC"
    if any(w in t for w in ["power","squat","bench"]): return "POWER"
    return "MENTOR"

def get_sys(profile):
    """Формирование системного промпта для OpenAI"""
    vibe=profile.get("vibe","MENTOR")
    guide="Be calm."
    if vibe=="AESTHETIC": guide="Focus on symmetry, aesthetics, discipline. Cold tone."
    if vibe=="POWER": guide="Focus on strength, load, eating. Heavy tone."
    return f"Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. Context: {profile.get('goal','New client')}. Rules: Human tone. Short answers."

# ==========================================
# ROUTES
# ==========================================
@app.route('/')
def home(): 
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify(): 
    return jsonify({"ok": safe_eq(request.json.get("k"),ACCESS_KEY)})

@app.route('/history', methods=['POST'])
def history():
    uid=request.json.get("uid")
    user=db[uid]
    # Присваиваем ID старым сообщениям, если их нет
    for m in user["history"]:
        if "id" not in m:
            m["id"]="m"+str(int(time.time()*1000)+random.randint(0,999))
    return jsonify({"history":user["history"],"pro":safe_eq(request.json.get("k"),ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    d=request.json; uid,mid,new_text=d.get("uid"),d.get("mid"),d.get("new_text")
    user=db[uid]
    for m in user["history"]:
        if m.get("id")==mid: m["c"]=new_text
    save_db()
    return jsonify({"ok":True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    d=request.json; uid,mid=d.get("uid"),d.get("mid")
    user=db[uid]
    user["history"]=[m for m in user["history"] if m.get("id")!=mid]
    save_db()
    return jsonify({"ok":True})

@app.route('/chat', methods=['POST'])
def chat():
    d=request.json
    msg, uid = d.get("msg"), d.get("uid")
    paid = safe_eq(d.get("k"),ACCESS_KEY)
    user=db[uid]

    # Ограничение бесплатных сообщений: 10 навсегда
    if not paid and user["count"]>=10:
        return jsonify({"reply":"Free limit reached. Access required."})

    if msg=="SYSTEM_INIT_TRIGGER":
        return jsonify({"reply":"I'm your coach. What is your goal?"})

    # Скрипт первого знакомства (Onboarding)
    if user["step"]=="HOOK":
        user["profile"]["goal"]=msg
        user["profile"]["vibe"]=detect_vibe(msg)
        user["step"]="BASE"
        reply="Got it. Height/Weight?"
    elif user["step"]=="BASE":
        user["profile"]["stats"]=msg
        user["step"]="DONE"
        reply="Locked. How do you train?"
    else:
        # Обычный чат: берем контекст из последних 6 сообщений
        context=[{"role":"user" if m["r"]=="usr" else "assistant","content":m["c"]} for m in user["history"][-6:]]
        msgs=[{"role":"system","content":get_sys(user["profile"])}]+context+[{"role":"user","content":msg}]
        try:
            # Используем модель gpt-4o-mini (так как gpt-5 еще не вышла)
            r=client.chat.completions.create(model="gpt-4o-mini",messages=msgs)
            reply=r.choices[0].message.content
        except:
            reply="AI Offline"

    # Сохранение в историю с ID для возможности редактирования
    user["history"].append({"r":"usr","c":msg,"id":"m"+str(int(time.time()*1000))})
    user["history"].append({"r":"bot","c":reply,"id":"m"+str(int(time.time()*1000)+1)})
    
    # Считаем сообщения для лимита только если не оплачено
    if not paid:
        user["count"]+=1
        
    if len(user["history"])>MAX_HISTORY: 
        user["history"]=user["history"][-MAX_HISTORY:]

    save_db()
    return jsonify({"reply":reply})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
