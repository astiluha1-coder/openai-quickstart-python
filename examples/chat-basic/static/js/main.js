// === ЭЛЕМЕНТЫ DOM ===
const chatWindow = document.querySelector(".chat-window");
const msgInput = document.getElementById("msgInput");
const sendBtn = document.getElementById("sendBtn");
const plusBtn = document.getElementById("plusBtn");
const plusMenu = document.getElementById("plusMenu");
const uploadPhotoBtn = document.getElementById("uploadPhoto");
const addNoteBtn = document.getElementById("addNote");

let uid = localStorage.getItem("uid") || ("u" + Date.now());
localStorage.setItem("uid", uid);

// === PLUS MENU ===
plusBtn.onclick = (e) => {
    e.stopPropagation();
    plusMenu.classList.toggle("hidden");
};

document.addEventListener('click', (e) => {
    if (!plusMenu.contains(e.target) && e.target !== plusBtn) {
        plusMenu.classList.add("hidden");
    }
});

// === ДОБАВЛЕНИЕ СООБЩЕНИЯ ===
function addMessage(text, role = "bot", skeleton = false) {
    const msgDiv = document.createElement("div");
    msgDiv.className = role;
    if (skeleton) {
        msgDiv.classList.add("skeleton");
        msgDiv.textContent = "";
    } else {
        msgDiv.textContent = text;
    }
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return msgDiv;
}

// === ОТПРАВКА СООБЩЕНИЯ ===
async function sendMessage() {
    const msg = msgInput.value.trim();
    if (!msg) return;
    
    // Закрываем меню если открыто
    plusMenu.classList.add("hidden");
    
    addMessage(msg, "usr");
    msgInput.value = "";
    const skeletonDiv = addMessage("", "bot", true);

    try {
        const resp = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uid, msg })
        });
        const data = await resp.json();
        const text = data.reply || "No response";

        // --- TYPING EFFECT ---
        let reply = "";
        skeletonDiv.classList.remove("skeleton");
        
        for (let i = 0; i < text.length; i++) {
            reply += text[i];
            skeletonDiv.textContent = reply;
            chatWindow.scrollTop = chatWindow.scrollHeight; // Автопрокрутка
            await new Promise(r => setTimeout(r, 15 + Math.random() * 20));
        }

    } catch (e) {
        skeletonDiv.textContent = "Error sending message";
        skeletonDiv.classList.remove("skeleton");
        console.error(e);
    }
}

sendBtn.onclick = sendMessage;
msgInput.addEventListener("keypress", e => {
    if (e.key === "Enter") sendMessage();
});

// === КНОПКИ ПЛЮС МЕНЮ ===
uploadPhotoBtn.onclick = () => {
    alert("Photo upload feature coming soon!");
    plusMenu.classList.add("hidden");
};
addNoteBtn.onclick = () => {
    let note = prompt("Enter note:");
    if(note) {
        msgInput.value = "[NOTE]: " + note;
        sendMessage();
    }
    plusMenu.classList.add("hidden");
};

// === LOTTIE АНИМАЦИИ (Пример использования) ===
function playExerciseLottie(container, file) {
    lottie.loadAnimation({
        container,
        renderer: "svg",
        loop: true,
        autoplay: true,
        path: `/static/lottie/${file}.json`
    });
}
