import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- НАСТРОЙКИ ---
MODEL = "gpt-4o-mini"
# СЕКРЕТНЫЙ КЛЮЧ
CURRENT_ACCESS_KEY = "START-2026" 
# ССЫЛКА НА SHOPIFY
SHOPIFY_PRODUCT_URL = "https://your-shopify-store.com/products/monthly-coaching-plan"

# --- МОЗГИ (НАСТРОЕНЫ НА ЦЕННОСТЬ) ---

# Sales: Краткий, цель - продать за $1.
SYSTEM_SALES = "You are a Fitness Sales Consultant. Be concise. Your goal is to get them to try the $1 trial. Do not give free detailed plans."

# Coach: ПОДРОБНЫЙ, ДЛИННЫЕ ОТВЕТЫ (Окупаем $1 качеством)
SYSTEM_COACH = """
You are an Elite Personal Coach. The user has paid for Premium.
YOUR GOAL: Over-deliver value in every message.

RULES:
1. NEVER give short answers. If asked for a workout, give a full table with sets, reps, and rest times.
2. If asked about diet, give macros, specific meals, and cooking tips.
3. Explain the "WHY". Don't just say "eat protein". Say "Protein is crucial because..."
4. Structure your text: Use Bold, Bullet points, and Emojis.
5. Act like a $500/hour coach. Comprehensive, deep, educational.
"""

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>AI Coach</title>
    <style>
        :root { --bg: #fff; --text: #000; --accent: #000; --green: #28a745; --red: #dc3545; }
        body { margin: 0; font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
        
        .header { padding: 15px; text-align: center; border-bottom: 1px solid #eee; font-weight: 800; letter-spacing: 1px; display: flex; justify-content: space-between; align-items: center; }
        .status { font-size: 10px; color: #666; text-transform: uppercase; display: flex; align-items: center; gap: 5px; }
        .dot { width: 8px; height: 8px; background: #ccc; border-radius: 50%; }
        .dot.active { background: var(--green); }
        .msg-counter { font-size: 10px; color: #aaa; font-weight: 600; }

        .chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg { max-width: 85%; padding: 14px 18px; border-radius: 18px; font-size: 15px; line-height: 1.5; }
        .bot { background: #f2f2f7; align-self: flex-start; }
        .user { background: #000; color: #fff; align-self: flex-end; }

        .input-area { padding: 15px; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 20px; font-size: 16px; outline: none; }
        button { background: #000; color: #fff; border: none; width: 45px; border-radius: 50%; cursor: pointer; }

        /* Lock Screen (Paywall) */
        .lock-screen { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.98); z-index: 999; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 20px; }
        .lock-title { font-size: 24px; font-weight: 900; margin-bottom: 10px; }
        .lock-btn { background: #000; color: #fff; padding: 15px 30px; border-radius: 30px; text-decoration: none; font-weight: bold; margin-top: 20px; display: block; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        COACH AI
        <div style="text-align:right;">
            <div class="status" id="status-text"><span class="dot" id="dot"></span>Guest</div>
            <div class="msg-counter" id="limit-display"></div>
        </div>
    </div>

    <div class="chat-box" id="chat">
        <div class="msg bot">Hey! 👋 I'm ready to build your plan. Do you have an access key?</div>
    </div>

    <div id="paywall" class="lock-screen hidden">
        <div class="lock-title" id="lock-title">🔒 DEMO ENDED</div>
        <p id="lock-msg">You've reached the free limit.<br>Start your transformation now.</p>
        
        <a href="{{ shopify_url }}" target="_blank" class="lock-btn">Try 1st Month for $1</a>
        
        <p style="margin-top:20px; font-size:12px; color:#888;">Already paid? Use the link from your email.</p>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type here..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">↑</button>
    </div>

    <script>
        // --- ЛИМИТЫ (СТРОГИЕ) ---
        const FREE_LIMIT = 5;       // 5 сообщений для гостей
        const PAID_LIMIT = 20;      // 20 сообщений в день для платных
        const ONE_MONTH = 30 * 24 * 60 * 60 * 1000;

        let isPremium = false;
        
        // СБРОС ЛИМИТА РАЗ В СУТКИ
        let today = new Date().toDateString();
        let storedDate = localStorage.getItem("msgDate");
        let msgCount = 0;

        if (storedDate === today) {
            msgCount = parseInt(localStorage.getItem("msgCount") || "0");
        } else {
            msgCount = 0;
            localStorage.setItem("msgDate", today);
        }

        // 1. АКТИВАЦИЯ ПО ССЫЛКЕ
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('key') === "{{ access_key }}") {
            activatePremium();
            window.history.replaceState({}, document.title, "/");
        }

        // 2. ПРОВЕРКА ПОДПИСКИ
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
                document.getElementById("chat").innerHTML += `<div class="msg bot">✅ VIP ACCESS GRANTED. I am now configured to provide detailed plans. What is your goal?</div>`;
            }, 500);
        }

        function updateUI(premium) {
            const dot = document.getElementById("dot");
            const status = document.getElementById("status-text");
            const limitDisplay = document.getElementById("limit-display");
            
            const currentLimit = premium ? PAID_LIMIT : FREE_LIMIT;
            const left = Math.max(0, currentLimit - msgCount);

            limitDisplay.innerText = `${left} left`;

            if (premium) {
                dot.className = "dot active";
                status.innerHTML = `<span class="dot active"></span>Premium`;
                document.getElementById("paywall").classList.add("hidden");
            } else {
                dot.className = "dot";
                status.innerHTML = `<span class="dot"></span>Guest`;
            }
        }

        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value.trim();
            if (!text) return;

            const limit = isPremium ? PAID_LIMIT : FREE_LIMIT;
            
            if (msgCount >= limit) {
                document.getElementById("paywall").classList.remove("hidden");
                if(isPremium) {
                    document.getElementById("lock-title").innerText = "DAILY LIMIT REACHED";
                    document.getElementById("lock-msg").innerText = "You reached the limit (20/20).\nSee you tomorrow.";
                } else {
                    document.getElementById("lock-title").innerText = "DEMO ENDED";
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
    except:
        reply = "System Error."

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
