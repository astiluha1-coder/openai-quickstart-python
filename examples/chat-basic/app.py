import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# НАСТРОЙКИ
MODEL = "gpt-4o-mini"

# --- ВАШ СЕКРЕТНЫЙ КЛЮЧ (МЕНЯЙТЕ ЕГО РАЗ В МЕСЯЦ!) ---
# Например: FEB-PRO, MAR-PRO, APR-PRO
CURRENT_ACCESS_KEY = "START-2026" 

SHOPIFY_PRODUCT_URL = "https://your-shopify-store.com/products/monthly-coaching-plan"

# --- ЛИЧНОСТИ БОТА ---
SYSTEM_SALES = "You are a friendly Fitness Consultant. Goal: Sell the plan ($20/mo). Be concise."
SYSTEM_COACH = "You are a Professional Personal Coach. Be strict, motivating, and data-driven."

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
        
        .header { padding: 15px; text-align: center; border-bottom: 1px solid #eee; font-weight: 800; letter-spacing: 1px; }
        .status { font-size: 10px; margin-top: 5px; color: #666; text-transform: uppercase; }
        .dot { display: inline-block; width: 8px; height: 8px; background: #ccc; border-radius: 50%; margin-right: 5px; }
        .dot.active { background: var(--green); }
        .dot.locked { background: var(--red); }

        .chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .msg { max-width: 80%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.4; }
        .bot { background: #f2f2f7; align-self: flex-start; }
        .user { background: #000; color: #fff; align-self: flex-end; }

        .input-area { padding: 15px; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 20px; font-size: 16px; outline: none; }
        button { background: #000; color: #fff; border: none; width: 45px; border-radius: 50%; cursor: pointer; }

        /* ЭКРАН БЛОКИРОВКИ */
        .lock-screen { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.98); z-index: 999; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 20px; }
        .lock-title { font-size: 24px; font-weight: 900; margin-bottom: 10px; }
        .lock-btn { background: #000; color: #fff; padding: 15px 30px; border-radius: 30px; text-decoration: none; font-weight: bold; margin-top: 20px; display: block; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        COACH AI
        <div class="status" id="status-text"><span class="dot" id="dot"></span>Guest Mode</div>
    </div>

    <div class="chat-box" id="chat">
        <div class="msg bot">Hey! 👋 I'm ready to train you. Do you have a subscription?</div>
    </div>

    <div id="paywall" class="lock-screen hidden">
        <div class="lock-title">🔒 MEMBERS ONLY</div>
        <p>This is a private coaching line.<br>Please subscribe to get access.</p>
        <a href="{{ shopify_url }}" target="_blank" class="lock-btn">Get Access ($20)</a>
        <p style="margin-top:20px; font-size:12px; color:#888;">Already paid? Check your email for the activation link.</p>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type here..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">↑</button>
    </div>

    <script>
        const ONE_MONTH = 30 * 24 * 60 * 60 * 1000;
        let isPremium = false;
        let msgCount = 0;

        // --- 1. ЗАЩИТА ССЫЛКИ ---
        // Проверяем, есть ли ключ в адресной строке
        const urlParams = new URLSearchParams(window.location.search);
        const secretKey = urlParams.get('key');
        const validKey = "{{ access_key }}";

        if (secretKey === validKey) {
            // Если ключ верный - активируем и ЧИСТИМ ССЫЛКУ (чтобы нельзя было скопировать)
            activatePremium();
            window.history.replaceState({}, document.title, "/");
        }

        // --- 2. ПРОВЕРКА СОХРАНЕННОЙ ПОДПИСКИ ---
        checkSubscription();

        function checkSubscription() {
            const expiry = localStorage.getItem("subExpiry");
            if (expiry && parseInt(expiry) > new Date().getTime()) {
                isPremium = true;
                updateUI(true);
            } else {
                // Если подписки нет - не блокируем сразу, даем сказать "Привет"
                updateUI(false);
            }
        }

        function activatePremium() {
            const expiry = new Date().getTime() + ONE_MONTH;
            localStorage.setItem("subExpiry", expiry);
            isPremium = true;
            updateUI(true);
            setTimeout(() => {
                document.getElementById("chat").innerHTML += `<div class="msg bot">✅ Access Granted! Welcome to the Team. Let's start. Weight & Height?</div>`;
            }, 500);
        }

        function updateUI(premium) {
            const dot = document.getElementById("dot");
            const status = document.getElementById("status-text");
            if (premium) {
                dot.className = "dot active";
                status.innerHTML = `<span class="dot active"></span>Premium Member`;
                document.getElementById("paywall").classList.add("hidden");
            } else {
                dot.className = "dot";
                status.innerHTML = `<span class="dot"></span>Guest Mode`;
            }
        }

        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value.trim();
            if (!text) return;

            // БЛОКИРОВКА ХАЛЯВЩИКОВ:
            // Если нет премиума и написали больше 2 сообщений -> БЛОК НА ВЕСЬ ЭКРАН
            if (!isPremium && msgCount >= 2) {
                document.getElementById("paywall").classList.remove("hidden");
                return; 
            }

            // UI
            let chat = document.getElementById("chat");
            chat.innerHTML += `<div class="msg user">${text}</div>`;
            input.value = "";
            chat.scrollTop = chat.scrollHeight;
            msgCount++;

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
        reply = "System Error. Check API Key."

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
