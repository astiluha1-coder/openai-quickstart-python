import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI  # <--- Новый импорт для версий 1.0+

app = Flask(__name__)
CORS(app)

# Инициализация клиента (новый синтаксис)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# --- НАСТРОЙКИ ---
# Если у тебя есть доступ к gpt-5-mini, поменяй название внутри кавычек:
CURRENT_MODEL = "gpt-5-mini" 

@app.route("/", methods=["GET"])
def index():
    return "Personal Coach Server is Running! 🚀"

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_message = data.get("msg")
        
        if not user_message:
            return jsonify({"reply": "Error: Empty message"}), 400

        # СИСТЕМНЫЙ ПРОМПТ
        system_prompt = (
            "Ты — профессиональный фитнес-коуч. "
            "Твоя задача — мотивировать, составлять планы тренировок и давать советы по питанию. "
            "Отвечай кратко (до 50 слов), энергично и используй эмодзи. "
            "Веди себя как наставник."
        )

        # НОВЫЙ СИНТАКСИС ЗАПРОСА (v1.0+)
        response = client.chat.completions.create(
            model=CURRENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500
        )

        # Получаем ответ (новый синтаксис через точку, а не скобки)
        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"reply": "Произошла ошибка на сервере. Проверь логи Railway."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
