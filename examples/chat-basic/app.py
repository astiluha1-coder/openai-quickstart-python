import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# Настройки
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Главная страница (чтобы проверить, что сайт жив)
@app.route('/', methods=['GET'])
def index():
    return "AI Bot is listening for Tawk.to events!", 200

# Сюда приходят сообщения от Tawk.to
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("🔔 WEBHOOK RECEIVED:", data) # Пишем в лог, что пришло

    # Tawk.to может прислать событие начала чата или сообщение
    # Пока просто подтверждаем получение
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
