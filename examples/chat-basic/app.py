import os
import openai
from flask import Flask, redirect, render_template, request, url_for, jsonify
from flask_cors import CORS  # <--- ЭТО ВАЖНО ДЛЯ РАБОТЫ С SHOPIFY

app = Flask(__name__)
# Разрешаем запросы с любых сайтов (чтобы Shopify не ругался)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def index():
    return "Personal Coach Server is Running! 🚀"

@app.route("/chat", methods=["POST"])
def chat():
    try:
        # Получаем данные от Shopify
        data = request.json
        user_message = data.get("msg")
        
        # Если сообщения нет, возвращаем ошибку
        if not user_message:
            return jsonify({"reply": "Error: Empty message"}), 400

        # НАСТРОЙКА МОЗГА (СИСТЕМНЫЙ ПРОМПТ)
        # Здесь ты задаешь характер тренера
        system_prompt = (
            "Ты — опытный, энергичный и поддерживающий фитнес-тренер. "
            "Твоя цель — помогать пользователю с тренировками, питанием и мотивацией. "
            "Отвечай кратко (не более 3-4 предложений), четко и с энтузиазмом. "
            "Используй эмодзи, чтобы ответы выглядели живыми. "
            "Если спрашивают не про фитнес, вежливо верни тему к тренировкам."
        )

        # Отправляем запрос в OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-5-mini", # Или gpt-5-mini, если у тебя есть доступ
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
        )

        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"reply": "Извини, я сейчас немного устал. Попробуй еще раз через минуту!"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
