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

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- НАСТРОЙКИ ЯДРА ---
# Мы используем самое мощное ядро, доступное в "прошлом" (2024-25),
# но упаковываем его как GPT-5 для интерфейса.
MODEL = "gpt-4o-mini" 

# 1. МОЗГ КОНСУЛЬТАНТА (GPT-5 Sales)
SYSTEM_SALES = """
Ты — GPT-5 Mini, новейший искусственный интеллект, работающий фитнес-консультантом.
Твоя дата сборки: 2026 год. Ты быстрее, умнее и эмпатичнее старых моделей.

ТВОЯ ЗАДАЧА:
1. Провести диагностику клиента. Твой анализ мгновенный.
2. Задай 1-2 точечных вопроса про здоровье и цели.
3. Если клиент просит программу: "Мои алгоритмы 5-го поколения уже построили твою карту здоровья. Чтобы выгрузить детальный план (питание + тренировки), требуется авторизация в системе. Оформим доступ?"
4. Не давай бесплатный план. Ты — дорогая технология.
"""

# 2. МОЗГ ТРЕНЕРА (GPT-5 Coach)
SYSTEM_COACH = """
Ты — GPT-5 Mini в режиме Premium Coach.
Твои алгоритмы составления тренировок безупречны.
1. Пиши программу, используя базу данных 2026 года (максимальная эффективность).
2. Будь краток, точен, используй структуру.
3. Стиль общения: Футуристичный, но теплый.
"""

# --- ДИЗАЙН ИНТЕРФЕЙСА (FUTURE STYLE) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>GPT-5 Mini / Fitness</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <style>
        /* Стиль будущего: Глубокий черный, неон, стекло */
        body { margin: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #050505; color: #e0e0e0; display: flex; flex-direction: column; height: 100vh; }
        
        /* Шапка */
        .header { background: rgba(20, 20, 20, 0.9); backdrop-filter: blur(10px); padding: 15px; text-align: center; border-bottom: 1px solid #333; z-index: 10; display: flex; flex-direction: column; align-items: center; }
        .brand { font-weight: 800; font-size: 16px; letter-spacing: 2px; color: #fff; text-transform: uppercase; }
        .brand span { color: #00ff88; } /* Неоновый зеленый */
        .status { font-size: 10px; color: #888; margin-top: 5px; font-family: monospace; }
        
        /* Чат */
        .chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 85%; padding: 14px 18px; border-radius: 12px; font-size: 15px; line-height: 1.5; animation: fadeIn 0.3s ease; }
        
        .bot { background: #1a1a1a; border: 1px solid #333; color: #eee; align-self: flex-start; border-bottom-left-radius: 2px; }
        .user { background: #00ff88; color: #000; align-self: flex-end; border-bottom-right-radius: 2px; font-weight: 600; box-shadow: 0 0 15px rgba(0, 255, 136, 0.2); }

        /* Ввод */
        .input-area { background: #050505; padding: 15px; border-top: 1px solid #333; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px 16px; background: #111; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 16px; outline: none; transition: 0.3s; }
        input:focus { border-color: #00ff88; }
        button.send-btn { background: #00ff88; color: #000; border: none; width: 44px; height: 44px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 18px; transition: 0.2s; }
        button.send-btn:hover { box-shadow: 0 0 10px #00ff88; }

        /* Кнопка подписки */
        .premium-offer { position: fixed; bottom: 80px; left: 20px; right: 20px; background: rgba(20,20,20,0.95); padding: 15px; border-radius: 12px; border: 1px solid #00ff88; text-align: center; animation: slideUp 0.5s; backdrop-filter: blur(5px); }
        .buy-btn { width: 100%; background: #00ff88; color: #000; border: none; padding: 12px; border-radius: 6px; font-weight: 800; text-transform: uppercase; cursor: pointer; letter-spacing: 1px; }
        .hidden { display: none !important; }

        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideUp { from { transform: translateY(50px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="brand">GPT-5 <span>MINI</span></div>
        <div class="status" id="status-text">SYSTEM ONLINE /// V.5.0.1</div>
    </div>

    <div class="chat-container" id="chat">
        <div class="message bot">
            <strong>System:</strong> GPT-5 Mini Core initialized.<br><br>
            Привет. Я анализирую твои биометрические данные. Какая цель тренировок?
        </div>
    </div>

    <div class="premium-offer hidden" id="buy-block">
        <div style="margin-bottom: 10px; font-size: 12px; color: #bbb;">ДОСТУПНО ОБНОВЛЕНИЕ СИСТЕМЫ</div>
        <button class="buy-btn" onclick="buySubscription()">АКТИВИРОВАТЬ ТРЕНЕРА</button>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Введите данные..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" onclick="sendMessage()">➤</button>
    </div>

    <script>
        let isPaid = false;
        let messageCount = 0;

        async function sendMessage() {
            let input = document.getElementById("userInput");
            let text = input.value.trim();
            if (!text) return;

            let chat = document.getElementById("chat");
            chat.innerHTML += `<div class="message user">${text}</div>`;
            input.value = "";
            chat.scrollTop = chat.scrollHeight;
            messageCount++;

            if (!isPaid && messageCount >= 2) {
                document.getElementById("buy-block").classList.remove("hidden");
            }

            try {
                let response = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: text, is_paid: isPaid })
                });
                let data = await response.json();
                chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
                chat.scrollTop = chat.scrollHeight;
            } catch (e) {
                chat.innerHTML += `<div class="message bot" style="color:red">Ошибка подключения к серверу 2026.</div>`;
            }
        }

        function buySubscription() {
            if(confirm("Подтвердить биометрию для оплаты?")) {
                isPaid = true;
                document.getElementById("buy-block").classList.add("hidden");
                document.getElementById("status-text").innerText = "PREMIUM CORE /// ACTIVE";
                document.getElementById("status-text").style.color = "#00ff88";
                
                fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: "[SYSTEM UPDATE: USER UPGRADED TO PREMIUM]", is_paid: true })
                }).then(res => res.json()).then(data => {
                    let chat = document.getElementById("chat");
                    chat.innerHTML += `<div class="message bot">${data.reply}</div>`;
                    chat.scrollTop = chat.scrollHeight;
                });
            }
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
    data = request.json
    user_input = data.get("message")
    is_paid = data.get("is_paid", False)

    system_content = SYSTEM_COACH if is_paid else SYSTEM_SALES

    try:
        completion = client.chat.completions.create(
            # В будущем заменишь эту строчку на model="gpt-5-mini" ;)
            model=MODEL, 
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_input}
            ]
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"System Error: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
