import os
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from openai import OpenAI
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)

# 👇👇👇 ВНИМАНИЕ! ВСТАВЬ СЮДА СВОЙ КЛЮЧ 👇👇👇
# Вместо sk-proj-.... вставь свой реальный ключ внутри кавычек!
client = OpenAI(api_key="") 

# --- НАСТРОЙКИ ---
MODEL = "gpt-4o-mini"
CURRENT_ACCESS_KEY = "START-2026"  # Ключ только на сервере
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- ЛИМИТЫ (Hard Limits) ---
HARD_LIMIT_FREE = 30 
HARD_LIMIT_PAID = 60

# --- СЕРВЕРНАЯ ПАМЯТЬ ---
user_limits = defaultdict(lambda: {'count': 0, 'last_reset': datetime.now()})

# --- РОУТЫ ДЛЯ PWA ---
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

# --- 1. ПРОДАВЕЦ (FREE) ---
SYSTEM_SALES = """You are the empathetic Assistant to a Premium Online Coach.
ROLE: Navigator & Desire Amplifier. You are NOT the coach yet.

STRICT RULES:
1. ❌ NO "I CANNOT": Use experience-based framing ("In my experience...").
2. 🧩 ABSOLUTION: "You’re not behind. You were just following generic advice."
3. 🛑 LIMIT PROTOCOL (CRITICAL): 
   - You have a soft focus limit of 20 messages.
   - IF message_count < 8: Focus 100% on the user. Validate them.
   - IF message_count >= 8 and message_count < 15: THE REALITY CHECK.
     Say: "I see where this conversation is going. We are circling around generalities. Based on what you told me, I already see patterns that keep people stuck. 
     I can keep guessing broadly, but frankly, **I don't work that way.**
     We have two options:
     1. I stay high-level (guessing).
     2. We switch to the full plan and fix this specifically for YOUR body.
     Which direction feels right?"
   - IF message_count >= 15 and < 20: Transparency: "Just to be transparent, I keep these free diagnostic sessions focused."
   - IF message_count >= 20: POLITELY CLOSE. Provide link.

RESPONSE STRUCTURE:
1. 🤝 HUMAN TOUCH: Validate their feeling.
2. 🛡️ RESPONSIBILITY: Explain why generic advice fails.
3. 💎 ADAPTIVE CTA: Ask one relevant question.
"""

# --- 2. ПЛАТНЫЙ ТРЕНЕР (PREMIUM) ---
SYSTEM_COACH = """You are an elite personal fitness architect.
GOAL: Deliver value but maintain professional boundaries.

FIRST MESSAGE PROTOCOL:
- If first message: Ask for Goal -> Experience -> Injuries -> Metrics.

LIMIT PROTOCOL:
- IF message_count >= 50: Say: "We’ve done a lot of great work today. Let's pause here. Review the plan, and we pick this up tomorrow with fresh focus."

BEHAVIOR:
1. 🪜 SCIENCE LADDER: Simple first, deep only if asked.
2. 🎯 FOCUS: Tie everything back to the plan.
"""

# --- HTML (PWA READY + ANIMATIONS) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Personal Coach AI</title>
    
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#2563eb">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="apple-touch-icon" href="/static/icons/icon-192.png">

    <style>
        :root { --primary-color: #2563eb; --bg-color: #f8fafc; --chat-bg: #ffffff; --user-msg-bg: #2563eb; --bot-msg-bg: #f1f5f9; --text-color: #1e293b; --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { font-family: var(--font-family); background-color: var(--bg-color); color: var(--text-color); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        
        /* Header */
        .header { background: var(--chat-bg); padding: 15px 20px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05); z-index: 10; padding-top: max(15px, env(safe-area-inset-top)); }
        .header h1 { font-size: 18px; font-weight: 700; color: #0f172a; letter-spacing: -0.5px; }
        .status-badge { font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; background: #e2e8f0; color: #64748b; cursor: pointer; transition: all 0.2s; }
        .status-badge:active { transform: scale(0.95); }
        .status-badge.premium { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; box-shadow: 0 2px 10px rgba(37, 99, 235, 0.2); }
        
        /* Chat Area */
        #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; padding-bottom: 30px; }
        
        /* ANIMATIONS */
        .message { 
            max-width: 85%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.5; word-wrap: break-word; 
            opacity: 0; 
            transform: translateY(10px); 
            animation: fadeInUp 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        @keyframes fadeInUp { to { opacity: 1; transform: translateY(0); } }

        .bot-message { align-self: flex-start; background-color: var(--bot-msg-bg); border-bottom-left-radius: 4px; color: #334155; }
        .user-message { align-self: flex-end; background-color: var(--user-msg-bg); color: white; border-bottom-right-radius: 4px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15); }
        
        /* Typing Indicator */
        .typing { align-self: flex-start; background-color: var(--bot-msg-bg); padding: 12px 20px; border-radius: 18px; display: none; gap: 5px; width: fit-content; border-bottom-left-radius: 4px; animation: fadeInUp 0.3s forwards; }
        .dot { width: 6px; height: 6px; background: #94a3b8; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; } .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        
        /* Input Area */
        .input-area { background: var(--chat-bg); padding: 15px 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; padding-bottom: max(15px, env(safe-area-inset-bottom)); }
        input { flex: 1; padding: 14px 20px; border-radius: 25px; border: 1px solid #e2e8f0; font-size: 16px; outline: none; background: #f8fafc; transition: all 0.2s; }
        input:focus { border-color: var(--primary-color); background: #fff; box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1); }
        
        /* BUTTON ANIMATION */
        button { background: var(--primary-color); color: white; border: none; width: 50px; height: 50px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1); box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }
        button:active { transform: scale(0.90); box-shadow: 0 2px 5px rgba(37, 99, 235, 0.2); }
        button svg { transition: transform 0.2s; }
        
        /* Modal */
        #modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); backdrop-filter: blur(5px); display: none; justify-content: center; align-items: center; z-index: 1000; animation: fadeIn 0.3s ease; }
        .modal { background: white; padding: 30px; border-radius: 24px; width: 90%; max-width: 400px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04); transform: translateY(10px); animation: slideUp 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; }
        @keyframes slideUp { to { transform: translateY(0); opacity: 1; } }
        .modal input { width: 100%; margin-bottom: 20px; text-align: center; letter-spacing: 2px; font-weight: 600; }
        .btn-primary { background: #10b981; width: 100%; padding: 14px; border-radius: 16px; font-weight: 600; color: white; border: none; cursor: pointer; transition: transform 0.1s; }
        .btn-primary:active { transform: scale(0.98); }
        
        .bot-message strong { color: #0f172a; font-weight: 700; }
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
            <p style="color:#64748b; margin-bottom:15px; font-size:14px;">Check your email for the key.</p>
            <input type="text" id="key-input" placeholder="START-202X">
            <div style="display:flex; flex-direction:column; gap:10px;">
                <button class="btn-primary" onclick="saveKey()">Activate Premium</button>
                <button style="background:none; border:none; color:#64748b; padding:10px;" onclick="closeModal()">Continue as Guest</button>
                <a href="{{ shopify_url }}" target="_blank" style="text-decoration:none; color:#2563eb; font-size:13px; font-weight:500;">Get a key ($20)</a>
            </div>
        </div>
    </div>

    <script>
        // PWA REGISTRATION
        if ('serviceWorker' in navigator) {
           window.addEventListener('load', () => {
             navigator.serviceWorker.register('/service-worker.js')
               .then(reg => console.log('SW registered'))
               .catch(err => console.log('SW failed', err));
           });
        }

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
    
    # 1. ПРОВЕРКА КЛЮЧА
    is_paid = (user_key == CURRENT_ACCESS_KEY)
    
    # 2. ЛОГИКА СЧЕТЧИКА
    user_ip = request.remote_addr
    
    if datetime.now() - user_limits[user_ip]['last_reset'] > timedelta(hours=24):
         user_limits[user_ip]['count'] = 0
         user_limits[user_ip]['last_reset'] = datetime.now()
    
    current_limit = HARD_LIMIT_PAID if is_paid else HARD_LIMIT_FREE
    
    # HARD STOP
    if user_limits[user_ip]['count'] >= current_limit:
         return jsonify({
            "reply": "We’ve covered a lot today. To keep this useful and not rushed, let’s pause here. Come back tomorrow with fresh focus — or unlock full coaching if you want to go deeper now.",
            "is_premium": is_paid
        })

    user_limits[user_ip]['count'] += 1
    current_count = user_limits[user_ip]['count']

    # ЛОГ
    user_status = "👑 PREMIUM" if is_paid else "👤 FREE"
    print(f"🚀 LOG: IP={user_ip} | MSG={current_count}/{current_limit} | STATUS={user_status}")

    # 3. AI
    if is_paid:
        system_role = SYSTEM_COACH
    else:
        system_role = SYSTEM_SALES

    system_prompt = f"{system_role}\n\nCURRENT MESSAGE COUNT: {current_count}"

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
