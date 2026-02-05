Import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Инициализация клиента OpenAI
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

MODEL = "gpt-5-mini"

SYSTEM_PROMPT = (
    "Ты персональный фитнес-тренер премиум-класса. "
    "Отвечай уверенно, спокойно и по делу. "
    "Без воды. Без лишних эмодзи. "
    "Твоя цель — помочь человеку тренироваться безопасно и эффективно."
)

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("msg", "").strip()

        if not user_message:
            return jsonify({"reply": "Сообщение пустое"}), 400

        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_output_tokens=300
        )

        # Универсальный и безопасный способ получить текст
        reply = response.output_text

        return jsonify({"reply": reply})

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({
            "reply": "Ошибка сервера. Попробуй ещё раз."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
