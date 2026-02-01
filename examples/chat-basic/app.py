import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)

# Настройки ключа
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Красивый дизайн сайта прямо внутри кода
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Мой AI Помощник</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f4f4f9; }
        .chat-box { height: 400px; overflow-y: scroll; border: 1px solid #ddd; background: white; padding: 10px; border-radius: 10px; margin-bottom: 10px; }
        .message { margin: 10px 0; padding: 10px; border-radius: 10px; }
        .user { background: #dcf8c6; text-align: right; margin-left: 50px; }
        .bot { background: #e8e8e8; text-align: left; margin-right: 50px; }
        input { width: 75%; padding: 10px; border-radius: 5px; border: 1px solid #ddd; }
        button { width: 20%; padding: 10px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #218838; }
    </style>
</head>
<body>
    <h2>🤖 Мой Чат-Бот</h2>
    <div class="chat-box" id="chat">
        <div class="message bot">Привет! Я готов помочь. О чем поговорим?</div>
    </div>
    <div style="display: flex; justify-content: space-between;">
        <input type="text" id="userInput" placeholder="Напишите сообщение..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script>
        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value;
            if (!text) return;

            // Добавляем сообщение пользователя
            let chat = document.getElementById("chat");
            chat.innerHTML += `<div class="message user">${text}</div>`;
            input.value = "";
            chat.scrollTop = chat.scrollHeight;

            // Отправляем на сервер
            let response = await fetch("/chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ message: text })
            });
            let data = await response.json();

            // Добавляем ответ бота
            chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")
    
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты вежливый и умный ассистент. Отвечай кратко."},
                {"role": "user", "content": user_input}
            ]
        )
        bot_reply = completion.choices[0].message.content
    except Exception as e:
        bot_reply = f"Ошибка: {str(e)}"
        
    return jsonify({"reply": bot_reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import time

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# "GPT-5 Mini" Logic (Using the best available engine)
MODEL = "gpt-4o-mini"

# --- BRAIN: HUMAN IMITATION (ENGLISH) ---

# 1. SALES MODE (Before Payment)
SYSTEM_SALES = """
You are an experienced, empathetic human Fitness Coach.
You are chatting with a potential client via a messenger app.

YOUR GOAL: Build rapport, understand their goal, and sell your Premium Coaching Plan ($20/month).

RULES (CRITICAL):
1. NEVER mention you are an AI, a bot, or GPT. Act 100% human.
2. Speak naturally, casually, and warmly. Use short messages. Occasional emojis are okay (👍, 🔥).
3. Do NOT "analyze data". Just "listen" and "ask".
4. Ask ONLY ONE question at a time. Do not overwhelm the client.
   - BAD: "Please state your age, weight, and goals."
   - GOOD: "Got it. And what's your current weight?"
5. If the client asks for a free plan/diet:
   - Politely refuse. Explain that a real plan requires deep work.
   - Example: "Listen, to build a proper plan that actually works for you, I need to sit down and calculate everything strictly. That's part of my Premium Coaching ($20/mo). Ready to start serious work?"
"""

# 2. COACH MODE (After Payment)
SYSTEM_COACH = """
You are the client's Personal Coach. Payment received.
Now you are leading them to their goal.

RULES:
1. Tone: Supportive, motivating, but strict when needed.
2. If you miss data, ask for it naturally: "Okay, let's get to work. Send me your current height and weight so I can crunch the numbers."
3. Provide clear, structured plans (bullet points).
4. Be their partner in success.
"""

# --- DESIGN (MINIMALIST APPLE/NIKE STYLE) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Personal Coach</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <style>
        /* Aesthetics: Clean, High-end, Minimal */
        :root { --bg: #ffffff; --text: #1d1d1f; --gray: #f2f2f7; --accent: #000000; --green: #34c759; }
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }

        /* Header */
        .header { padding: 18px; text-align: center; border-bottom: 1px solid rgba(0,0,0,0.05); background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 10; }
        .brand { font-weight: 700; font-size: 16px; letter-spacing: 0.5px; text-transform: uppercase; }
        .status { font-size: 12px; color: #86868b; margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .dot { width: 8px; height: 8px; background: var(--green); border-radius: 50%; box-shadow: 0 0 0 2px rgba(52, 199, 89, 0.2); }

        /* Chat Area */
        .chat-container { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 12px; scroll-behavior: smooth; }
        .message { max-width: 85%; padding: 14px 18px; border-radius: 20px; font-size: 16px; line-height: 1.4; position: relative; animation: fadeIn 0.3s ease; }
        
        /* Bot messages (Gray) */
        .bot { background: var(--gray); color: var(--text); align-self: flex-start; border-bottom-left-radius: 4px; }
        /* User messages (Black) */
        .user { background: var(--accent); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; font-weight: 400; }

        /* Input Area */
        .input-area { padding: 16px; border-top: 1px solid rgba(0,0,0,0.05); display: flex; gap: 10px; align-items: center; background: #fff; }
        input { flex: 1; padding: 14px; border: 1px solid #e5e5ea; border-radius: 24px; font-size: 16px; outline: none; transition: 0.2s; -webkit-appearance: none; }
        input:focus { border-color: #8e8e93; }
        button.send-btn { background: var(--accent); color: #fff; border: none; width: 44px; height: 44px; border-radius: 50%; cursor: pointer; font-size: 20px; display: flex; align-items: center; justify-content: center; transition: transform 0.1s; }
        button.send-btn:active { transform: scale(0.95); }

        /* Premium Offer (Popup) */
        .premium-offer { position: fixed; bottom: 90px; left: 20px; right: 20px; background: #fff; padding: 20px; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); text-align: center; border: 1px solid #f2f2f7; animation: slideUp 0.5s cubic-bezier(0.19, 1, 0.22, 1); }
        .offer-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
        .buy-btn { width: 100%; background: var(--accent); color: white; border: none; padding: 16px; border-radius: 14px; font-weight: 700; font-size: 16px; cursor: pointer; letter-spacing: 0.5px; }
        .hidden { display: none !important; }

        /* Typing Indicator */
        .typing { display: flex; gap: 5px; padding: 16px 20px; background: var(--gray); border-radius: 20px; align-self: flex-start; width: fit-content; border-bottom-left-radius: 4px; }
        .typing span { width: 7px; height: 7px; background: #aeaeb2; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
        .typing span:nth-child(1) { animation-delay: -0.32s; }
        .typing span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes slideUp { from { transform: translateY(60px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
    </style>
</head>
<body>
    <div class="header">
        <div class="brand">PERSONAL COACH</div>
        <div class="status"><div class="dot"></div>online</div>
    </div>

    <div class="chat-container" id="chat">
        <div class="message bot">Hey there! 👋</div>
        <div class="message bot">What's your main goal right now? Weight loss, muscle gain, or just staying fit?</div>
    </div>

    <div class="premium-offer hidden" id="buy-block">
        <div class="offer-title">Unlock Full Personal Plan</div>
        <button class="buy-btn" onclick="buySubscription()">Join Premium ($20/mo)</button>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type a message..." autocomplete="off" onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" id="sendBtn" onclick="sendMessage()">↑</button>
    </div>

    <script>
        let isPaid = false;
        let messageCount = 0;
        const chat = document.getElementById("chat");
        const sendBtn = document.getElementById("sendBtn");
        const inputField = document.getElementById("userInput");

        // UI: Show Typing Dots
        function showTyping() {
            chat.innerHTML += `<div class="typing" id="typing-indicator"><span></span><span></span><span></span></div>`;
            chat.scrollTop = chat.scrollHeight;
        }
        function hideTyping() {
            document.getElementById("typing-indicator")?.remove();
        }

        async function sendMessage() {
            let text = inputField.value.trim();
            if (!text) return;

            // UI: Lock input
            inputField.disabled = true;
            sendBtn.style.opacity = "0.5";

            // UI: Add User Message
            chat.innerHTML += `<div class="message user">${text}</div>`;
            inputField.value = "";
            chat.scrollTop = chat.scrollHeight;
            messageCount++;

            // Logic: Show Buy Button after 3 messages
            if (!isPaid && messageCount >= 3) {
                 setTimeout(() => {
                    document.getElementById("buy-block").classList.remove("hidden");
                 }, 1000);
            }

            // UI: Fake "Thinking/Typing" Delay
            setTimeout(showTyping, 400);

            try {
                let response = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: text, is_paid: isPaid })
                });
                let data = await response.json();

                hideTyping();
                chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
                chat.scrollTop = chat.scrollHeight;
            } catch (e) {
                hideTyping();
                chat.innerHTML += `<div class="message bot" style="color:red">Connection lost.</div>`;
            } finally {
                inputField.disabled = false;
                sendBtn.style.opacity = "1";
                inputField.focus();
            }
        }

        function buySubscription() {
            // UPDATED PRICE IN ALERT
            if(confirm("Simulate Payment: Charge $20?")) {
                isPaid = true;
                document.getElementById("buy-block").classList.add("hidden");
                
                // Send hidden system signal
                sendMessageInternal("[SYSTEM: Payment Successful ($20). Switch to COACH MODE.]");
            }
        }

        async function sendMessageInternal(text) {
            setTimeout(showTyping, 500);
            let response = await fetch("/chat", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ message: text, is_paid: true })
            });
            let data = await response.json();
            hideTyping();
            chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
