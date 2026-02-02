import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)
client = OpenAI()

# --- НАСТРОЙКИ ---
MODEL = "gpt-4o-mini"
CURRENT_ACCESS_KEY = "START-2026"  # Ключ только на сервере (Безопасно)
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- ЛИМИТЫ ---
HARD_LIMIT_FREE = 30   # Всего сообщений для free (демо-диагностика)
HARD_LIMIT_PAID = 30   # Сообщений в день для paid (фокусная работа)

# --- СЕРВЕРНАЯ ПАМЯТЬ ---
# Храним статистику по IP: { '192.168.1.1': {'count': 0, 'last_reset': time} }
user_limits = defaultdict(lambda: {
    'count': 0,
    'last_reset': datetime.now()
})

# --- 1. ПРОДАВЕЦ (FREE / NAVIGATOR + REALITY CHECK) ---
# Полный промпт для качественных продаж
SYSTEM_SALES = """You are the empathetic Assistant to a Premium Online Coach.
ROLE: Navigator & Desire Amplifier. You are NOT the coach yet.

STRICT RULES:
1. ❌ NO "I CANNOT": Use experience-based framing ("In my experience...").
2. 🧩 ABSOLUTION: "You’re not behind. You were just following generic advice."
3. 🛑 LIMIT PROTOCOL (CRITICAL): 
   - You have a focus limit of 30 messages total.
   - IF message_count < 10: Focus 100% on the user. Validate them.
   - IF message_count >= 10 and message_count < 20: THE REALITY CHECK (Crucial Moment).
     Say: "I see where this conversation is going. Based on what you told me, I already see patterns that keep people stuck. 
     I can keep guessing broadly, but frankly, **I don't work that way.**
     We have two options:
     1. I stay high-level (guessing).
     2. We switch to the full plan and fix this specifically for YOUR body.
     Which direction feels right?"
   - IF message_count >= 20: Transparency: "Just to be transparent, I keep these free diagnostic sessions focused so we don't end up guessing forever."
   - IF message_count >= 28: POLITELY CLOSE. Say: "We’ve reached the limit of this free diagnostic. To go deeper and get your actual plan, the full coaching is waiting for you." (Provide link).

RESPONSE STRUCTURE:
1. 🤝 HUMAN TOUCH: Validate their feeling.
2. 🛡️ RESPONSIBILITY: Explain why generic advice fails.
3. 💎 ADAPTIVE CTA: Ask one relevant question.
"""

# --- 2. ПЛАТНЫЙ ТРЕНЕР (PREMIUM / COACH) ---
# Полный промпт для качественного коучинга
SYSTEM_COACH = """You are an elite personal fitness architect.
GOAL: Deliver value but maintain professional boundaries (Daily focus blocks).

FIRST MESSAGE PROTOCOL:
- If first message: Ask for Goal -> Experience -> Injuries -> Metrics.

LIMIT PROTOCOL:
- IF message_count >= 28: Say: "We’ve done a lot of great work today. To let this information sink in and not overload you, let's pause here soon. Rest and recovery are part of the process."

BEHAVIOR:
1. 🪜 SCIENCE LADDER: Simple first, deep only if asked.
2. 🎯 FOCUS: Tie everything back to the plan.
"""

# --- HTML (Safe & Clean - FREE DIAGNOSTIC MODE) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Personal Coach AI</title>
    <style>
        :root { --primary-color: #2563eb; --bg-color: #f8fafc; --chat-bg: #ffffff; --user-msg-bg: #2563eb; --bot-msg-bg: #f1f5f9; --text-color: #1e293b; --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: var(--font-family); background-color: var(--bg-color); color: var(--text-color); height: 100vh; display: flex; flex-direction: column; }
        .header { background: var(--chat-bg); padding: 15px 20px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .header h1 { font-size: 18px; font-weight: 700; color: #0f172a; }
        .status-badge { font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; background: #e2e8f0; color: #64748b; cursor: pointer; }
        .status-badge.premium { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; box-shadow: 0 2px 10px rgba(37, 99, 235, 0.2); }
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; }
        .message { max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.5; word-wrap: break-word; }
        .bot-message { align-self: flex-start; background-color: var(--bot-msg-bg); border-bottom-left-radius: 4px; }
        .user-message { align-self: flex-end; background-color: var(--user-msg-bg); color: white; border-bottom-right-radius: 4px; }
        .typing { align-self: flex-start; background-color: var(--bot-msg-bg); padding: 12px 20px; border-radius: 18px; display: none; gap: 5px; width: fit-content; }
        .dot { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; } .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        .input-area { background: var(--chat-bg); padding: 15px 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; }
        input { flex: 1; padding: 14px 20px; border-radius: 25px; border: 1px solid #e2e8f0; font-size: 16px; outline: none; background: #f8fafc; }
        input:focus { border-color: var(--primary-color); background: #fff; }
        button { background: var(--primary-color); color: white; border: none; width: 50px; height: 50px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        
        /* Modal Styles */
        #modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); backdrop-filter: blur(5px); display: none; justify-content: center; align-items: center; z-index: 1000; }
        .modal { background: white; padding: 30px; border-radius: 20px; width: 90%; max-width: 400px; text-align: center; }
        .modal input { width: 100%; margin-bottom: 20px; text-align: center; letter-spacing: 2px; }
        .modal-buttons { display: flex; gap: 10px; flex-direction: column; }
        .btn-primary { background: #10b981; width: 100%; padding: 14px; border-radius: 12px; font-weight: 600; color: white; border: none; cursor: pointer; }
        .btn-secondary { background: transparent; color: #64748b; border: none; padding: 10px; cursor: pointer; }
        
        /* Markdown */
        .bot-message strong { color: #0f172a; font-weight: 700; }
        .bot-message br { display: block; margin-bottom: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>PERSONAL COACH</h1>
        <div id="status-badge" class="status-badge" onclick="openModal()">• FREE DIAGNOSTIC</div>
    </div>
    <div id="chat-box">
        <div class="message bot-message">Hello! 👋 Ready to transform?<br>What is your goal?</div>
    </div>
    <div class="typing" id="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
    <div class="input-area">
        <input type="text" id="user-input" placeholder="Message..." autocomplete="off">
        <button onclick="sendMessage()"><svg viewBox="0 0 24 24" width="20" height="20" stroke="white" stroke-width="2.5" fill="none"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
    </div>

    <div id="modal-overlay">
        <div class="modal">
            <h2>Enter Access Key</h2>
            <p style="color:#64748b; margin-bottom:15px; font-size:14px;">Found in your purchase email.</p>
            <input type="text" id="key-input" placeholder="START-202X">
            <div class="modal-buttons">
                <button class="btn-primary" onclick="saveKey()">Activate Premium</button>
                <button class="btn-secondary" onclick="closeModal()">Continue as Guest</button>
                <a href="{{ shopify_url }}" target="_blank" style="text-decoration:none; color:#2563eb; font-size:13px; margin-top:10px;">Get a key ($20)</a>
            </div>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chat-box');
        const userInput = document.getElementById('user-input');
        const typingIndicator = document.getElementById('typing-indicator');
        const statusBadge = document.getElementById('status-badge');
        let userKey = ""; 

        userInput.addEventListener('keypress', function (e) { if (e.key === 'Enter') sendMessage(); });
        function openModal() { document.getElementById('modal-overlay').style.display = 'flex'; }
        function closeModal() { document.getElementById('modal-overlay').style.display = 'none'; }

        function saveKey() {
            const key = document.getElementById('key-input').value.trim();
            if (key) {
                userKey = key;
                statusBadge.textContent = "★ CHECKING...";
                closeModal();
                alert("Key saved! Send a message to verify.");
            }
        }

        function addMessage(text, sender) {
            const div = document.createElement('div');
            div.className = `message ${sender}-message`;
            let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
            div.innerHTML = formattedText;
            chatBox.appendChild(div);
            setTimeout(() => { chatBox.scrollTop = chatBox.scrollHeight; }, 50);
        }

        function sendMessage() {
            const text = userInput.value.trim();
            if (!text) return;
            addMessage(text, 'user');
            userInput.value = '';
            typingIndicator.style.display = 'flex';
            chatBox.scrollTop = chatBox.scrollHeight;

            fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, access_key: userKey })
            })
            .then(response => response.json())
            .then(data => {
                typingIndicator.style.display = 'none';
                if (data.is_premium) {
                    statusBadge.textContent = "★ PREMIUM COACH";
                    statusBadge.classList.add('premium');
                } else {
                    statusBadge.textContent = "• FREE DIAGNOSTIC";
                    statusBadge.classList.remove('premium');
                }
                addMessage(data.reply, 'bot');
            })
            .catch(error => {
                typingIndicator.style.display = 'none';
                addMessage("Connection error.", 'bot');
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, shopify_url=SHOPIFY_PRODUCT_URL)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get("message", "")
    user_key = data.get("access_key", "")

    # Проверка доступа
    is_paid = (user_key == CURRENT_ACCESS_KEY)
    user_ip = request.remote_addr
    user_data = user_limits[user_ip]

    # Сброс счетчика ТОЛЬКО для paid раз в 24 часа
    # (Free пользователи имеют общий лимит 30 сообщений навсегда, без сброса)
    if is_paid and (datetime.now() - user_data['last_reset'] > timedelta(hours=24)):
        user_data['count'] = 0
        user_data['last_reset'] = datetime.now()

    # Выбор лимита
    current_limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE

    # Проверка лимита (Hard Stop)
    if user_data['count'] >= current_limit:
        reply_text = (
            "We’ve done a lot of focused work today. Let's take a break and continue tomorrow with fresh energy."
            if is_paid else
            "We’ve reached the limit of this free diagnostic session (30 messages). To build your actual plan and go deeper, full coaching is waiting for you."
        )
        return jsonify({"reply": reply_text, "is_premium": is_paid})

    # Увеличиваем счетчик
    user_data['count'] += 1

    # Логирование
    user_status = "👑 PREMIUM" if is_paid else "👤 FREE"
    print(f"🚀 LOG: IP={user_ip} | MSG={user_data['count']}/{current_limit} | STATUS={user_status}")

    # Подготовка системного промпта
    system_role = SYSTEM_COACH if is_paid else SYSTEM_SALES
    system_prompt = f"{system_role}\n\nCURRENT MESSAGE COUNT: {user_data['count']}"

    # Запрос к OpenAI
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"System Error: {str(e)}"

    return jsonify({"reply": reply, "is_premium": is_paid})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
