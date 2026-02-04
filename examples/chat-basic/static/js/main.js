const plusBtn = document.getElementById('plusBtn');
const plusMenu = document.getElementById('plusMenu');
const exerciseMenu = document.getElementById('exerciseMenu');
const chatWindow = document.querySelector('.chat-window');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const app = document.getElementById('app');
const closeBtn = document.getElementById('closeBtn');

// Plus Menu toggle
plusBtn.addEventListener('click', (e) => { e.stopPropagation(); plusMenu.classList.toggle('hidden'); });
document.addEventListener('click', () => plusMenu.classList.add('hidden'));

// Fullscreen chat toggle
plusBtn.addEventListener('dblclick', () => { app.classList.add('fullscreen'); closeBtn.classList.remove('hidden'); });
closeBtn.addEventListener('click', () => { app.classList.remove('fullscreen'); closeBtn.classList.add('hidden'); });

// Exercise buttons
exerciseMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button'); if (!btn) return;
    const text = btn.dataset.text;
    addBotMessage(text);
});

// Send message
sendBtn.addEventListener('click', sendUserMessage);
userInput.addEventListener('keypress', (e) => { if(e.key==='Enter') sendUserMessage(); });

function sendUserMessage() {
    const text = userInput.value.trim(); if(!text) return;
    addUserMessage(text); userInput.value='';
    // AI request
    fetch('/chat', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ msg:text, uid:'shopify-user', k:'ACCESS_KEY' })
    })
    .then(res=>res.json())
    .then(data=>addBotMessage(data.reply))
    .catch(()=>addBotMessage("AI Offline"));
}

function addBotMessage(text) {
    const msg = document.createElement('div');
    msg.classList.add('chat-message','bot');
    msg.innerHTML = `<p>${text}</p>`;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addUserMessage(text) {
    const msg = document.createElement('div');
    msg.classList.add('chat-message','usr');
    msg.innerHTML = `<p>${text}</p>`;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}
