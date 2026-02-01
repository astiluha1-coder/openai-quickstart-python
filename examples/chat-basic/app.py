import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# НАСТРОЙКИ
MODEL = "gpt-4o-mini"
# СЕКРЕТНЫЙ КЛЮЧ (Совет: меняйте его раз в месяц, например "MARCH-2026", чтобы старые ссылки сгорали)
ACCESS_CODE = "START-2026" 
# ССЫЛКА НА ВАШ ТОВАР (Куда отправлять, если подписка истекла)
SHOPIFY_PRODUCT_URL = "https://your-shopify-store.com/products/monthly-coaching-plan"

# --- МОЗГИ (ENGLISH) ---
SYSTEM_SALES = "You are a Human Fitness Sales Consultant. Be friendly. Sell the plan ($20/mo)."
SYSTEM_COACH = "You are the Personal Coach. Be motivating, strict, professional. Give plans."

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>Personal Coach</title>
    <style>
        :root { --bg: #fff; --text: #1d1d1f; --gray: #f5f5f7; --accent: #000; --green: #34c759; --red: #ff3b30; }
        body { margin: 0; font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
        
        .header { padding: 18px; text-align: center; border-bottom: 1px solid #eee; font-weight: 700; }
        .status { font-size: 11px; color: #888; display: flex; align-items: center; justify-content: center; gap: 5px; margin-top: 4px; }
        .dot { width: 8px; height: 8px; background: #ccc; border-radius: 50%; }
        .dot.active { background: var(--green); }
        .dot.expired { background: var(--red); }

        .chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 80%; padding: 12px 16px; border-radius: 20px; font-size: 16px; line-height: 1.4; }
        .bot { background: var(--gray); align-self: flex-start; border-bottom-left-radius: 2px; }
        .user { background: var(--accent); color: #fff; align-self: flex-end; border-bottom-right-radius: 2px; }

        .input-area { padding: 15px; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { flex: 1; padding: 14px; border: 1px solid #ddd; border-radius: 25px; font-size: 16px; outline: none; }
        button { background: var(--accent); color: #fff; border: none; width: 45px; height: 45px; border-radius: 50%; cursor: pointer; }

        /* Paywall Overlay */
        .paywall { position: fixed; bottom: 80px; left: 20px; right: 20px; background: #fff; padding: 25px; border-radius: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); text-align: center; border: 1px solid #eee; z-index: 100; }
        .btn-buy { width: 100%; padding: 15px; background: #000; color: #fff; border: none; border-radius: 15px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        COACH AI
        <div class="status" id="status-text"><div class="dot" id="status-dot"></div>Free Preview</div>
    </div>

    <div class="chat-container" id="chat">
        <div class="message bot">Hey! 👋 I'm ready. What's your fitness goal?</div>
    </div>

    <div id="pay-wall" class="paywall hidden">
        <h3 id="pw-title">Unlock Premium</h3>
        <p id="pw-desc" style="color:#666; font-size:14px;">Get your personal plan for $20/mo.</p>
        <button class="btn-buy" onclick="window.open('{{ shopify_url }}', '_blank')">Subscribe ($20/mo)</button>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Message..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">↑</button>
    </div>

    <script>
        const ONE_MONTH = 30 * 24 * 60 * 60 * 1000; // 30 дней
        let isPremium = false;
        let msgCount = 0;

        // 1. ПРОВЕРКА ССЫЛКИ (Если перешли из Shopify)
        const urlParams = new URLSearchParams(window.location.search);
        const secretKey = urlParams.get('key');
        const correctCode = "{{ access_code }}";

        if (secretKey === correctCode) {
            activatePremium();
            window.history.replaceState({}, document.title, "/"); // Прячем код из строки браузера
        } 
        
        // 2. ПРОВЕРКА ТАЙМЕРА ПРИ ЗАГРУЗКЕ
        checkSubscription();

        function checkSubscription() {
            const expiry = localStorage.getItem("subExpiry");
            if (expiry) {
                const now = new Date().getTime();
                if (parseInt(expiry) > now) {
                    // Подписка активна
                    isPremium = true;
                    const daysLeft = Math.ceil((parseInt(expiry) - now) / (1000 * 60 * 60 * 24));
                    setPremiumUI(daysLeft);
                } else {
                    // Подписка ИСТЕКЛА
                    isPremium = false;
                    showExpiredUI();
                }
            }
        }

        function activatePremium() {
            const expiry = new Date().getTime() + ONE_MONTH;
            localStorage.setItem("subExpiry", expiry);
            isPremium = true;
            setPremiumUI(30);
            
            setTimeout(() => {
                let chat = document.getElementById("chat");
                chat.innerHTML += `<div class="message bot">✅ Subscription Activated for 30 Days! Let's work. What is your current weight?</div>`;
                chat.scrollTop = chat.scrollHeight;
            }, 800);
        }

        function setPremiumUI(days) {
            document.getElementById("status-dot").className = "dot active";
            document.getElementById("status-text").innerHTML = `<div class="dot active"></div>Premium (${days} days left)`;
            document.getElementById("pay-wall").classList.add("hidden");
        }

        function showExpiredUI() {
            document.getElementById("status-dot").className = "dot expired";
            document.getElementById("status-text").innerHTML = `<div class="dot expired"></div>Expired`;
            
            const pw = document.getElementById("pay-wall");
            pw.classList.remove("hidden");
            document.getElementById("pw-title").innerText = "Subscription Expired";
            document.getElementById("pw-desc").innerText = "Your 30-day pass has ended. Please renew to continue.";
        }

        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value.trim();
            if (!text) return;

            // Блокировка, если истекла подписка (и не премиум)
            // Но даем отправить 2 тестовых сообщения, если это новый пользователь
            if (!isPremium && msgCount >= 2) {
                document.getElementById("pay-wall").classList.remove("hidden");
                return; // Не отправляем сообщение боту
            }

            let chat = document.getElementById("chat");
            chat.innerHTML += `<div class="message user">${text}</div>`;
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
                chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
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
    return render_template_string(HTML_PAGE, shopify_url=SHOPIFY_PRODUCT_URL, access_code=ACCESS_CODE)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get("message", "")
    is_paid = data.get("is_paid", False)

    system_content = SYSTEM_COACH if is_paid else SYSTEM_SALES
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_input}
            ]
        )
        reply = completion.choices[0].message.content
    except:
        reply = "Please add OpenAI Key."

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
