import os, time, json, threading, hmac
from flask import Flask, request, jsonify, render_template
from collections import defaultdict
from openai import OpenAI

# --- CONFIG (Настройки) ---
ACCESS_KEY = os.environ.get("ACCESS_KEY", "START-2026")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__, template_folder='templates')
MAX_HISTORY = 50
FREE_MSG_LIMIT = 10
BACKUP_FILE = "backup_db.json"

# --- DATA STORAGE (Хранилище данных) ---
db = defaultdict(lambda: {
    "history": [],
    "step": "HOOK",
    "profile": {"vibe": "MENTOR"},
    "count_free": 0,
    "count": 0
})
lock = threading.Lock()

# Загрузка бэкапа при старте, если он существует
if os.path.exists(BACKUP_FILE):
    try:
        with open(BACKUP_FILE) as f:
            backup = json.load(f)
            for k, v in backup.items():
                db[k] = v
    except: pass

def save_db():
    """Синхронное сохранение базы данных в файл"""
    with lock:
        try:
            with open(BACKUP_FILE, 'w') as f:
                json.dump(db, f)
        except: pass

def safe_eq(a, b):
    """Безопасное сравнение строк для ключей доступа"""
    if not a or not b: return False
    return hmac.compare_digest(a.encode(), b.encode())

def detect_vibe(text):
    """Определение стиля общения коуча"""
    t=text.lower()
    if any(w in t for w in ["aesthetic","david","laid"]): return "AESTHETIC"
    if any(w in t for w in ["power","squat","bench"]): return "POWER"
    return "MENTOR"

def get_sys(profile):
    """Генерация системного промпта для ИИ"""
    vibe = profile.get("vibe","MENTOR")
    guide = "Be calm."
    if vibe=="AESTHETIC": guide="Focus on symmetry, aesthetics, discipline. Cold tone."
    if vibe=="POWER": guide="Focus on strength, load, eating. Heavy tone."
    return f"Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. Context: {profile.get('goal','New client')}. Rules: Human tone. Short answers."

# --- ROUTES (Маршруты) ---

@app.route('/')
def home(): return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    return jsonify({"ok": safe_eq(request.json.get("k"), ACCESS_KEY)})

@app.route('/history', methods=['POST'])
def history():
    uid = request.json.get("uid")
    user = db[uid]
    # Добавляем ID сообщениям, если их нет (для корректной работы редактирования)
    for m in user["history"]:
        if "id" not in m: m["id"] = "m"+str(int(time.time()*1000))
    return jsonify({"history": user["history"], "pro": safe_eq(request.json.get("k"), ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    d = request.json
    uid, mid, new_text = d.get("uid"), d.get("mid"), d.get("new_text")
    user = db[uid]
    for m in user["history"]:
        if m.get("id") == mid: m["c"] = new_text
    save_db()
    return jsonify({"ok": True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    d = request.json
    uid, mid = d.get("uid"), d.get("mid")
    user = db[uid]
    user["history"] = [m for m in user["history"] if m.get("id") != mid]
    save_db()
    return jsonify({"ok": True})

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    msg, uid, key, img = d.get("msg"), d.get("uid"), d.get("k"), d.get("img")
    paid = safe_eq(key, ACCESS_KEY)
    user = db[uid]

    # Лимит для бесплатных пользователей
    if not paid and user["count_free"] >= FREE_MSG_LIMIT:
        return jsonify({"reply":"Free 10 messages used. Please unlock access.","pro":paid})

    # Стартовый триггер системы
    if msg == "SYSTEM_INIT_TRIGGER":
        return jsonify({"reply":"I'm your coach. What is your goal?","pro":paid})

    # Пошаговый онбординг (HOOK -> BASE -> DONE)
    if user["step"] == "HOOK":
        user["profile"]["goal"] = msg
        user["profile"]["vibe"] = detect_vibe(msg)
        user["step"] = "BASE"
        reply = "Got it. Height/Weight?"
    elif user["step"] == "BASE":
        user["profile"]["stats"] = msg
        user["step"] = "DONE"
        reply = "Locked. How do you train?"
    else:
        # Основной чат с использованием контекста последних 6 сообщений
        context = [{"role":"user" if m["r"]=="usr" else "assistant","content":m["c"]} for m in user["history"][-6:]]
        msgs = [{"role":"system","content":get_sys(user["profile"])}] + context + [{"role":"user","content":msg}]
        try:
            if img:
                if not paid:
                    reply = "Photos are Premium."
                else:
                    msgs.append({"role":"user","content":[{"type":"text","text":"Analyze"},{"type":"image_url","image_url":{"url":img}}]})
                    r = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
                    reply = r.choices[0].message.content
            else:
                r = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
                reply = r.choices[0].message.content
        except:
            reply = "AI Offline"

    # Сохранение сообщений в историю
    new_mid_user = "m"+str(int(time.time()*1000))
    new_mid_bot = "m"+str(int(time.time()*1000)+1)
    user["history"].append({"r":"usr","c":msg,"id":new_mid_user})
    user["history"].append({"r":"bot","c":reply,"id":new_mid_bot})
    
    # Счётчик сообщений
    if not paid:
        user["count_free"] += 1
    else:
        user["count"] += 1
        
    # Удаление старых сообщений из истории
    if len(user["history"]) > MAX_HISTORY:
        user["history"] = user["history"][-MAX_HISTORY:]

    save_db()
    return jsonify({"reply": reply, "pro": paid})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
