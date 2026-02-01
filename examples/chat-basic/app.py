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
