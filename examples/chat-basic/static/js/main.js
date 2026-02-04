const chatWindow = document.querySelector('.chat-window');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const app = document.getElementById('app');
const closeBtn = document.getElementById('closeBtn');
const chatBubble = document.getElementById('chatBubble');

let uid = localStorage.getItem("uid") || ("u" + Date.now());
localStorage.setItem("uid", uid);

// --- ЛОГИКА ОТКРЫТИЯ/ЗАКРЫТИЯ ---
chatBubble.addEventListener('click', () => {
    app.classList.remove('hidden');     // Показать чат
    chatBubble.classList.add('hidden'); // Скрыть кнопку
});

closeBtn.addEventListener('click', () => {
    app.classList.add('hidden');        // Скрыть чат
    chatBubble.classList.remove('hidden'); // Вернуть кнопку
});

// --- ОТПРАВКА СООБЩЕНИЙ ---
sendBtn.addEventListener('click', sendUserMessage);
userInput.addEventListener('keypress', (e) => { if(e.key==='Enter') sendUserMessage(); });

async function sendUserMessage() {
    const text = userInput.value.trim(); 
    if(!text) return;
    
    addUserMessage(text); 
    userInput.value='';

    try {
        const res = await fetch('/chat', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ msg:text, uid:uid, k:'ACCESS_KEY' })
        });
        const data = await res.json();
        addBotMessage(data.reply);
    } catch (e) {
        addBotMessage("AI Offline");
    }
}

function addBotMessage(text) {
    const msg = document.createElement('div');
    msg.classList.add('bot');
    msg.textContent = text;
    chatWindow.appendChild(msg); // ИСПРАВЛЕНО (было пусто)
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addUserMessage(text) {
    const msg = document.createElement('div');
    msg.classList.add('usr');
    msg.textContent = text;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}
