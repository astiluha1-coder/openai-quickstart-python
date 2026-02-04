import os, time, json, random, threading, hmac
from flask import Flask, request, jsonify, render_template
from collections import defaultdict
from openai import OpenAI
import redis

# --- CONFIG (Настройки) ---
ACCESS_KEY = os.environ.get("ACCESS_KEY","START-2026")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Подключение к Redis для стабильного хранения данных
rdb = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
MAX_HISTORY = 50

app = Flask(__name__, template_folder='templates')

# ---------------------
# DATA MANAGER (Управление данными)
# ---------------------
def safe_eq(a,b): 
    """Безопасное сравнение ключей доступа"""
    return hmac.compare_digest(a.encode(), b.encode()) if a and b else False

def load_user(uid):
    """Загрузка данных пользователя из Redis"""
    if rdb:
        data = rdb.get(f"u:{uid}")
        if data: return json.loads(data)
    # Возвращаем схему по умолчанию, если пользователь новый
    return {"history":[], "step":"HOOK", "profile":{"vibe":"MENTOR"}, "mode":"support", "count":0, "count_free":0}

def save_user(uid, user):
    """Сохранение данных пользователя в Redis"""
    if len(user["history"]) > MAX_HISTORY: 
        user["history"] = user["history"][-MAX_HISTORY:]
    if rdb: 
        rdb.set(f"u:{uid}", json.dumps(user))
    
def detect_vibe(text):
    """Определение стиля коучинга по ключевым словам"""
    t=text.lower()
    if any(w in t for w in ["aesthetic", "david", "laid"]): return "AESTHETIC"
    if any(w in t for w in ["power", "squat", "bench"]): return "POWER"
    return "MENTOR"

def get_sys(profile):
    """Генерация системного промпта для ИИ"""
    vibe=profile.get("vibe", "MENTOR")
    guide="Be calm."
    if vibe=="AESTHETIC": guide="Focus on symmetry, aesthetics, discipline. Cold tone."
    if vibe=="POWER": guide="Focus on strength, load, eating. Heavy tone."
    return f"Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. Context: {profile.get('goal','New client')}. Rules: Human tone. Short answers."

# ---------------------
# ROUTES (Маршруты приложения)
# ---------------------
@app.route('/')
def home(): 
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify(): 
    return jsonify({"ok": safe_eq(request.json.get("k"), ACCESS_KEY)})

@app.route('/history', methods=['POST'])
def history():
    uid = request.json.get("uid")
    user = load_user(uid)
    # Присваиваем ID сообщениям, если их нет (для корректной работы редактирования)
    for m in user["history"]:
        if "id" not in m: 
            m["id"] = "m" + str(int(time.time()*1000) + random.randint(0,999))
    save_user(uid, user)
    return jsonify({"history": user["history"], "pro": safe_eq(request.json.get("k"), ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    d=request.json; uid, mid, new_text = d.get("uid"), d.get("mid"), d.get("new_text")
    user = load_user(uid)
    for m in user["history"]:
        if m.get("id") == mid: 
            m["c"] = new_text
    save_user(uid, user)
    return jsonify({"ok": True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    d=request.json; uid, mid = d.get("uid"), d.get("mid")
    user = load_user(uid)
    user["history"] = [m for m in user["history"] if m.get("id") != mid]
    save_user(uid, user)
    return jsonify({"ok": True})

@app.route('/chat', methods=['POST'])
def chat():
    d=request.json
    msg, uid, key, img = d.get("msg"), d.get("uid"), d.get("k"), d.get("img")
    paid = safe_eq(key, ACCESS_KEY)
    user = load_user(uid)

    if msg=="SYSTEM_INIT_TRIGGER":
        return jsonify({"reply":"I'm your coach. What is your goal?", "pro":paid})

    # Логика поддержки (режим по умолчанию)
    if user["mode"]=="support":
        reply="Первый месяц $1, потом $20/мес. Я могу рассказать, что входит в подписку."
        user["history"].append({"r":"usr", "c":msg, "id":"m"+str(int(time.time()*1000))})
        user["history"].append({"r":"bot", "c":reply, "id":"m"+str(int(time.time()*1000)+1)})
        save_user(uid, user)
        return jsonify({"reply":reply, "pro":paid})

    # Логика Коуча (если режим изменен)
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
        # Чат с использованием модели ИИ
        context=[{"role":"user" if m["r"]=="usr" else "assistant", "content":m["c"]} for m in user["history"][-6:]]
        msgs=[{"role":"system", "content":get_sys(user["profile"])}] + context + [{"role":"user", "content":msg}]
        try:
            # Используем актуальную модель gpt-4o-mini
            r=client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
            reply=r.choices[0].message.content
        except:
            reply="AI Offline"

    # Сохранение диалога в историю
    user["history"].append({"r":"usr", "c":msg, "id":"m"+str(int(time.time()*1000))})
    user["history"].append({"r":"bot", "c":reply, "id":"m"+str(int(time.time()*1000)+1)})
    save_user(uid, user)
    return jsonify({"reply":reply, "pro":paid})

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
