Import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# === МОДЕЛЬ ===
MODEL = "gpt-5-mini"

# === СИСТЕМНЫЙ ПРОМПТ (фиксированный, без креативного разброса) ===
SYSTEM_PROMPT = (
    "Ты профессиональный персональный фитнес-тренер. "
    "Отвечай четко, спокойно и уверенно. "
    "Давай практичные советы по тренировкам и восстановлению. "
    "Без воды, без лишних эмоций. "
    "Форматируй ответы краткими абзацами."
)

@app.route("/", methods=["GET"])
def index():
    return "Coach Server (GPT-5-mini) is running 🚀"

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_message = data.get("msg", "").strip()

        if not user_message:
            return jsonify({"reply": "Сообщение пустое"}), 400

        # === GPT-5-mini через Responses API ===
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
            max_output_tokens=400  # фиксируем длину, без хаоса
        )

        # === ДОСТАЕМ ТЕКСТ БЕЗОПАСНО ===
        reply = ""
        for item in response.output:
            if item["type"] == "message":
                for part in item["content"]:
                    if part["type"] == "output_text":
                        reply += part["text"]

        if not reply:
            reply = "Попробуй переформулировать вопрос."

        return jsonify({"reply": reply})

    except Exception as e:
        print("SERVER ERROR:", e)
        return jsonify({
            "reply": f"Ошибка сервера: {str(e)}"
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
