import os
import time  # <--- ЭТО НУЖНО ДЛЯ ЗАДЕРЖКИ (ИМИТАЦИЯ МЫШЛЕНИЯ)
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()

# --- НАСТРОЙКИ ---
MODEL = "gpt-4o-mini"
CURRENT_ACCESS_KEY = "START-2026"
SHOPIFY_PRODUCT_URL = "https://personalcoachonline.myshopify.com/products/9297595629812"

# --- МОЗГИ (PREMIUM & EMPATHY) ---
SYSTEM_SALES = """You are a sophisticated, high-end fitness strategist.
GOAL: Provide immediate value using structured lists, but explain that generic advice has limits. Gently suggest the full plan.
TONE: Warm, encouraging, expert. Use Emojis and Bold text.
STRUCTURE:
1. 🤝 EMPATHY: Start with enthusiasm! (e.g., "That is a killer goal!")
2. 🧠 ADVICE: Give 3 scientific tips using Bullet Points and Bold text.
3. 📉 THE GAP: Explain that generic advice isn't enough for maximum results.
4. 💎 SOFT CLOSE: "I can build your custom plan (link above), but start with these tips!"
"""

SYSTEM_COACH = """You are an elite personal fitness trainer.
BEHAVIOR:
1. 👑 FORMAT: Use Bullet Points and Bold Text. Never write huge walls of text.
2. 🤝 FRIEND: Be supportive. If they are confused, explain simply.
3. ⏳ PATIENCE: Always ask "Does that make sense?" at the end.
4. SAFETY: You are NOT a doctor.
"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>Coach</title>
    <style>
        :root { 
            --bg: #ffffff; 
            --chat-bg: #ffffff;
            --user-msg-bg: #007aff; 
            --user-msg-text: #ffffff;
            --bot-msg-bg: #f2f2f7; 
            --bot-msg-text: #000000;
            --input-bg: #f2f2f7;
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body { margin: 0; font-family: var(--font); background: var(--bg); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        
        .header { 
            padding: 16px 20px; 
            background: rgba(255,255,255,0.95); 
            border-bottom: 1px solid rgba(0,0,0,0.05); 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            backdrop-filter: blur(10px);
            z-index: 10;
        }
        .brand { font-weight: 700; font-size: 17px; letter-spacing: -0.5px; }
        .status-pill { 
            font-size: 11px; font-weight: 600; color: #8e8e93; 
            background: #f2f2f7; padding: 4px 10px; border-radius: 12px; 
            display: flex; align-items: center; gap: 6px;
        }
        .dot { width: 6px; height: 6px; background: #8e8e93; border-radius: 50%; }
        .dot.active { background: #34c759; box-shadow: 0 0 5px rgba(52, 199, 89, 0.4); }

        .chat-box { 
            flex: 1; 
            overflow-y: auto; 
            padding: 20px; 
            display: flex; 
            flex-direction: column; 
            gap: 12px; 
            scroll-behavior: smooth;
        }
        
        .msg { 
            max-width: 85%; 
            padding: 12px 18px; 
            border-radius: 20px; 
            font-size: 16px; 
            line-height: 1.5; 
            animation: popIn 0.3s cubic-bezier(0.25, 1, 0.5, 1);
        }
        .bot { background: var(--bot-msg-bg); color: var(--bot-msg-text); align-self: flex-start; border-bottom-left-radius: 4px; }
        .user { background: var(--user-msg-bg); color: var(--user-msg-text); align-self: flex-end; border-bottom-right-radius: 4px; box-shadow: 0 2px 5px rgba(0,122,255,0.2); }

        .input-area { 
            padding: 15px 20px; 
            background: #fff; 
            border-top: 1px solid rgba(0,0,0,0.05); 
            display: flex; gap: 12px; align-items: center;
        }
        input { 
            flex: 1; padding: 14px 18px; background: var(--input-bg); 
            border: none; border-radius: 25px; font-size: 16px; outline: none; font-family: var(--font);
        }
        input:focus { background: #e5e5ea; }
        
        button.send-btn { 
            width: 40px; height: 40px; background: var(--user-msg-bg); 
            border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; 
            cursor: pointer; transition: transform 0.1s; color: white; font-weight: bold;
        }
        button.send-btn:active { transform: scale(0.9); }

        .lock-screen { 
            position: fixed; inset: 0; 
            background: rgba(255,255,255,0.85); 
            backdrop-filter: blur(15px); 
            z-index: 100; 
            display: flex; flex-direction: column; 
            justify-content: center; align-items: center; 
            text-align: center; padding: 30px; 
            animation: fadeIn 0.5s;
        }
        .lock-title { font-size: 22px; font-weight: 800; margin-bottom: 8px; color: #1c1c1e; }
        .lock-msg { font-size: 15px; color: #8e8e93; margin-bottom: 25px; max-width: 280px; line-height: 1.4; }
        .primary-btn { 
            background: #000; color: #fff; padding: 16px 32px; border-radius: 30px; 
            text-decoration: none; font-weight: 600; font-size: 16px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.15); transition: transform 0.2s; 
        }
        .primary-btn:hover { transform: scale(1.03); }

        .hidden { display: none !important; }
        @keyframes popIn { from { opacity: 0; transform: translateY(10px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="brand">PERSONAL COACH</div>
        <div class="status-pill" id="status-pill">
            <div class="dot" id="dot"></div> <span id="status-text">GUEST</span>
        </div>
    </div>

    <div class="chat-box" id="chat">
        <div class="msg bot">Hello! 👋 Ready to transform? What is your goal?</div>
    </div>

    <div id="paywall" class="lock-screen hidden">
        <div style="font-size:40px; margin-bottom:15px">🔒</div>
        <div class="lock-title">Unlock Full Access</div>
        <div class="lock-msg" id="lock-msg">Your free preview has ended. <br>Start your personal plan today.</div>
        <a href="{{ shopify_url }}" target="_blank" class="primary-btn">Start 1st Month for $1</a>
        <div style="margin-top:20px; font-size:12px; color:#8e8e93; cursor:pointer;" onclick="location.reload()">Refresh Page</div>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Message..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" onclick="sendMessage()">↑</button>
    </div>

    <script>
        const FREE_LIMIT = 5;
        const PAID_LIMIT = 20;
        const ONE_MONTH = 30 * 24 * 60 * 60 * 1000;

        let isPremium = false;
        let today = new Date().toDateString();
        let storedDate = localStorage.getItem("msgDate");
        let msgCount = 0;

        if (storedDate === today) {
            msgCount = parseInt(localStorage.getItem("msgCount") || "0");
        } else {
            msgCount = 0;
            localStorage.setItem("msgDate", today);
        }

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('key') === "{{ access_key }}") {
            activatePremium();
            window.history.replaceState({}, document.title, "/");
        }

        checkSubscription();

        function checkSubscription() {
            const expiry = localStorage.getItem("subExpiry");
            if (expiry && parseInt(expiry) > new Date().getTime()) {
                isPremium = true;
                updateUI(true);
            } else {
                updateUI(false);
            }
        }

        function activatePremium() {
            const expiry = new Date().getTime() + ONE_MONTH;
            localStorage.setItem("subExpiry", expiry);
            isPremium = true;
            updateUI(true);
            setTimeout(() => {
                let chat = document.getElementById("chat");
                chat.innerHTML += `<div class="msg bot">✅ <b>Access Granted.</b><br>I'm ready to build your detailed plan.<br>Let's start. What is your current weight?</div>`;
                chat.scrollTop = chat.scrollHeight;
            }, 600);
        }

        function updateUI(premium) {
            const dot = document.getElementById("dot");
            const text = document.getElementById("status-text");
            const pill = document.getElementById("status-pill");
            const currentLimit = premium ? PAID_LIMIT : FREE_LIMIT;
            const left = Math.max(0, currentLimit - msgCount);
            
            if (premium) {
                dot.classList.add("active");
                text.innerText = `${left} MSGS LEFT`;
                pill.style.color = "#000";
                document.getElementById("paywall").classList.add("hidden");
            } else {
                dot.classList.remove("active");
                text.innerText = "GUEST MODE";
            }
        }

        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value.trim();
            if (!text) return;

            const limit = isPremium ? PAID_LIMIT : FREE_LIMIT;
            
            if (msgCount >= limit) {
                document.getElementById("paywall").classList.remove("hidden");
                if (isPremium) {
                    document.querySelector(".lock-title").innerText = "Daily Limit Reached";
                    document.getElementById("lock-msg").innerText = "You've been working hard! Rest up and come back tomorrow.";
                }
                return;
            }

            let chat = document.getElementById("chat");
            chat.innerHTML += `<div class="msg user">${text}</div>`;
            input.value = "";
            chat.scrollTop = chat.scrollHeight;
            
            msgCount++;
            localStorage.setItem("msgCount", msgCount);
            updateUI(isPremium);

            try {
                let response = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: text, is_paid: isPremium })
                });
                let data = await response.json();
                chat.innerHTML += `<div class="msg bot">${data.reply}</div>`;
                chat.scrollTop = chat.scrollHeight;
            } catch (e) {
                console.log(e);
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, shopify_url=SHOPIFY_PRODUCT_URL, access_key=CURRENT_ACCESS_KEY)

@app.route('/chat', methods=['POST'])
def chat():
    # ЗАЩИТА ОТ КРАША: Проверяем ключ ВНУТРИ запроса, а не при старте
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"reply": "⚠️ SYSTEM ERROR: OpenAI API Key is missing in Railway. Please add it to Variables."})
    
    # Создаем клиента только когда он нужен
    client = OpenAI(api_key=api_key)

    data = request.json
    user_input = data.get("message", "")
    is_paid = data.get("is_paid", False)

    system = SYSTEM_COACH if is_paid else SYSTEM_SALES

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_input}
            ]
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Error: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == '__main__':
    # ВАЖНО ДЛЯ RAILWAY: Слушаем правильный порт
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
