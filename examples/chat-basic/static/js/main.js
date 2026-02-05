const app = document.getElementById('app');
const chatBubble = document.getElementById('chatBubble');
const closeBtn = document.getElementById('closeBtn');
const chatWindow = document.getElementById('chatWindow');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

let uid = localStorage.getItem("uid") || ("u" + Date.now());
localStorage.setItem("uid", uid);

// Флаг защиты от двойной отправки
let isSending = false;

// === 1. ОТКРЫТИЕ / ЗАКРЫТИЕ ===
chatBubble.addEventListener('click', () => {
    chatBubble.classList.add('hidden');
    requestAnimationFrame(() => app.classList.add('active'));
    setTimeout(() => userInput.focus(), 100);
});

closeBtn.addEventListener('click', () => {
    app.classList.remove('active');
    setTimeout(() => {
        chatBubble.classList.remove('hidden');
    }, 300);
});

// === 2. ВВОД ===
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);

// === 3. ЛОГИКА СООБЩЕНИЙ ===
async function sendMessage() {
    const text = userInput.value.trim();
    // Блокируем, если пусто или уже идет отправка
    if (!text || isSending) return;

    isSending = true; // Блокируем ввод
    
    addMessage(text, 'usr');
    userInput.value = '';
    scrollToBottom();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ msg: text, uid: uid, k: 'ACCESS_KEY' })
        });
        const data = await response.json();
        
        // Органическая задержка
        const delay = Math.max(600, (data.reply.length * 20));

        setTimeout(() => {
            addMessage(data.reply, 'bot');
            isSending = false; // Разблокируем после ответа
        }, delay);

    } catch (e) {
        setTimeout(() => {
            addMessage("Connection error. Try again.", 'bot');
            isSending = false; // Разблокируем при ошибке
        }, 600);
    }
}

function addMessage(text, type) {
    const div = document.createElement('div');
    div.classList.add('msg', type);
    div.textContent = text;
    chatWindow.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    // requestAnimationFrame гарантирует, что скролл сработает после рендера DOM
    requestAnimationFrame(() => {
        chatWindow.scrollTo({
            top: chatWindow.scrollHeight,
            behavior: 'smooth'
        });
    });
}
