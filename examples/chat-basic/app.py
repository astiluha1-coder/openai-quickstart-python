import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Инициализация клиента
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# Используем gpt-4o-mini (самая свежая и быстрая модель на сегодня)
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "Ты профессиональный персональный фитнес-тренер. "
    "Отвечай уверенно, спокойно и по делу. "
    "Без лишней болтовни. Без воды."
)

@app.route("/", methods=["GET"])
def index():
    return "Coach Server Running! 🚀"

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_message = data.get("msg", "").strip()

        if not user_message:
            return jsonify({"reply": "Сообщение пустое"}), 400

        # === ПРАВИЛЬНАЯ КОМАНДА OPENAI ===
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
            temperature=0.7
        )

        # Правильный способ достать текст
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"SERVER ERROR: {e}")
        return jsonify({
            "reply": f"Ошибка сервера: {str(e)}"
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
