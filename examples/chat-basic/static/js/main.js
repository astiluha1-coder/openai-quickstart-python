const chatWindow=document.querySelector(".chat-window");
const msgInput=document.getElementById("msgInput");
const sendBtn=document.getElementById("sendBtn");
const plusBtn=document.getElementById("plusBtn");
const plusMenu=document.getElementById("plusMenu");
let uid=localStorage.getItem("uid")||("u"+Date.now());
localStorage.setItem("uid",uid);

plusBtn.onclick=()=>{ plusMenu.classList.toggle("hidden"); };

function addMessage(text, role="bot", skeleton=false){
    const msgDiv=document.createElement("div");
    msgDiv.className=role;
    if(skeleton){
        msgDiv.classList.add("skeleton");
        msgDiv.textContent="...";
    } else {
        msgDiv.textContent=text;
    }
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop=chatWindow.scrollHeight;
    return msgDiv;
}

async function sendMessage(){
    const msg=msgInput.value.trim();
    if(!msg) return;
    addMessage(msg,"usr");
    msgInput.value="";
    const skeletonDiv=addMessage("", "bot", true);

    try {
        const resp=await fetch("/chat",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({uid,msg})
        });
        const data=await resp.json();

        // typing effect
        let reply="";
        const text=data.reply || "No reply";
        skeletonDiv.classList.remove("skeleton");
        skeletonDiv.textContent="";
        
        for(let i=0;i<text.length;i++){
            reply+=text[i];
            skeletonDiv.textContent=reply;
            chatWindow.scrollTop=chatWindow.scrollHeight; // Auto-scroll while typing
            await new Promise(r=>setTimeout(r,15+Math.random()*20));
        }
    } catch(e) {
        skeletonDiv.classList.remove("skeleton");
        skeletonDiv.textContent="Error connecting to server.";
    }
}

sendBtn.onclick=sendMessage;
msgInput.addEventListener("keypress",e=>{if(e.key==="Enter")sendMessage();});

// Example Lottie animation usage (вызывай при необходимости)
function playExerciseLottie(container, file){
    lottie.loadAnimation({container,renderer:"svg",loop:true,autoplay:true,path:`/static/lottie/${file}.json`});
}

// Загрузка истории при старте (опционально)
(async ()=>{
    try {
        const r=await fetch("/history",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({uid})
        });
        const d=await r.json();
        if(d.history) d.history.forEach(m=>addMessage(m.c, m.r));
    } catch(e){}
})();
