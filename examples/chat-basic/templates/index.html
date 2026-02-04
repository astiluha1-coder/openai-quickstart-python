<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#ffffff">
<title>Coach</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root {
  --bg:#fff; --text:#111; --acc:#2563eb; --bub:#f3f4f6; --usr:#2563eb;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}

body {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100dvh;
  margin: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Учитываем безопасные зоны для всего экрана */
  padding-bottom: env(safe-area-inset-bottom);
}

/* HEADER - Исправлено наложение на статус-бар */
.head {
  position: fixed; top: 0; left: 0; width: 100%;
  padding: 10px 15px;
  /* Резервируем место под челку сверху */
  padding-top: calc(10px + env(safe-area-inset-top));
  height: auto;
  min-height: 60px;
  border-bottom: 1px solid #eee;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(10px);
  z-index: 100;
}
.logo { font-weight: 700; font-size: 14px; letter-spacing: 1px; color: #888; }
.badge { font-size: 10px; border: 1px solid #ddd; padding: 3px 8px; border-radius: 20px; color: #888; cursor: pointer; }
.badge.pro { background: var(--acc); color: white; border: none; }

/* MESSAGES BOX */
#box {
  flex: 1;
  overflow-y: auto;
  /* Отступ сверху равен высоте шапки, снизу — высоте инпута */
  padding: 80px 15px 100px; 
  display: flex; flex-direction: column; gap: 12px;
  -webkit-overflow-scrolling: touch;
}
.msg {
  max-width: 85%; padding: 10px 16px; border-radius: 18px; 
  font-size: 16px; line-height: 1.4; word-wrap: break-word; 
  animation: fadeUp 0.2s ease-out; position: relative;
}
@keyframes fadeUp { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.bot { background: var(--bub); align-self: flex-start; border-bottom-left-radius: 4px; color: #000; }
.usr { background: var(--usr); color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
.msg img { max-width: 100%; border-radius: 10px; margin-top: 5px; }
.msg-controls { font-size: 12px; margin-left: 8px; cursor: pointer; opacity: 0.6; }

/* INPUT PANEL - Исправлено для мобильных */
.inp {
  position: fixed; bottom: 0; left: 0; width: 100%;
  background: #fff;
  padding: 10px 15px;
  /* Учет safe-area внизу (для iPhone без кнопок) */
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid #eee;
  display: flex; gap: 10px; z-index: 99; align-items: flex-end;
}
.txt-div {
  flex: 1; padding: 10px 14px; border-radius: 22px;
  border: 1px solid #ddd; font-size: 16px; outline: none;
  max-height: 120px; overflow-y: auto; min-height: 44px; background: #fff;
  caret-color: var(--acc);
}
.txt-div:empty:before { content: attr(data-placeholder); color: #9ca3af; }
.txt-div:focus { border-color: var(--acc); }

.btn {
  width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; border: none; font-size: 24px; cursor: pointer;
  color: #555; flex-shrink: 0; background: #f3f4f6; transition: all 0.2s;
}
.send { background: var(--acc); color: white; }

/* PLUS MENU - Теперь открывается над инпутом */
#plusMenu {
  position: absolute; 
  bottom: calc(70px + env(safe-area-inset-bottom)); 
  left: 15px; 
  background: white; border: 1px solid #ddd;
  border-radius: 15px; display: none; flex-direction: column; gap: 2px; padding: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 101;
}
#plusMenu div { cursor: pointer; padding: 12px 18px; border-radius: 10px; transition: background 0.15s; font-size: 15px; }
#plusMenu div:hover { background: var(--bub); }

/* MODAL */
#mod { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(5px); }
.win { background: white; padding: 30px; border-radius: 20px; width: 85%; max-width: 320px; text-align: center; }
</style>
</head>
<body>

<div class="head">
    <div class="logo">COACH</div>
    <div id="sts" class="badge" onclick="showAuth()">ACCESS</div>
</div>

<div id="box" onclick="blurInput()"></div>

<div class="inp">
    <div class="btn" id="plus">+</div>
    <div class="txt-div" id="txt" contenteditable="true" data-placeholder="Message..."></div>
    <div class="btn send" onclick="send()">↑</div>
</div>

<div id="plusMenu">
    <div onclick="triggerFile()">📷 Upload Photo</div>
    <div onclick="addNote()">📝 Add Note</div>
</div>

<div id="mod">
    <div class="win">
        <h3>UNLOCK PRO</h3>
        <div id="auth-area"></div>
        <p onclick="closeAuth()" style="margin-top:20px;color:#888;font-size:12px;cursor:pointer;">Close</p>
    </div>
</div>

<script>
const b=document.getElementById('box'), t=document.getElementById('txt'), uid=localStorage.getItem('uid')||'u'+Date.now();
localStorage.setItem('uid',uid);

function blurInput(){ t.blur(); }

function add(msg,role,img,mid=null){
    let d=document.createElement('div');d.className='msg '+role;d.dataset.mid=mid||('m'+Date.now());
    if(img)d.innerHTML=`<img src="${img}"><br>`+(msg||'Analyzing...');
    else d.innerHTML=role=='usr'?msg.replace(/\n/g,'<br>'):marked.parse(msg);
    
    if(role=='usr'){ 
      let c=document.createElement('span');c.className='msg-controls';c.innerText='✎';
      c.onclick=(e)=>{e.stopPropagation();edit(d.dataset.mid,msg);};
      d.appendChild(c);
    }
    b.appendChild(d);
    // Плавный скролл вниз
    b.scrollTo({ top: b.scrollHeight, behavior: 'smooth' });
}

function edit(mid,txt){
    let n=prompt("Edit message:",txt);
    if(n!==null && n!==txt){ 
      let ep=n===""?'/delete':'/edit'; 
      let body=n===""?{uid,mid}:{uid,mid,new_text:n};
      fetch(ep,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      .then(r=>r.json()).then(d=>{if(d.ok)location.reload();});
    }
}

function post(txt,img){
    txt=txt||t.innerText.trim();
    if(!txt&&!img)return;
    if(!img){add(txt,'usr');t.innerText='';}else add("Analyzing...",'usr',img);
    
    fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:txt,img,uid,k:localStorage.getItem('key')})})
    .then(r=>r.json()).then(d=>{
      if(d.pro){document.getElementById('sts').innerText="PRO";document.getElementById('sts').className="badge pro";} 
      add(d.reply,'bot');
    })
    .catch(()=>add("Error connecting",'bot'));
}

function send(){post();}

// Обработка Enter (без Shift)
t.addEventListener('keydown',(e)=>{
  if(e.key==='Enter' && !e.shiftKey){
    e.preventDefault();
    send();
  }
});

t.addEventListener('paste',(e)=>{
  e.preventDefault();
  let text = (e.clipboardData || window.clipboardData).getData('text');
  document.execCommand('insertText', false, text);
});

function showAuth(){
    document.getElementById('mod').style.display='flex';
    document.getElementById('auth-area').innerHTML=`<input type="text" id="key" placeholder="ENTER KEY" style="width:100%;margin:15px 0;padding:12px;border:1px solid #ddd;border-radius:10px;text-align:center;font-size:16px;"><div class="btn send" style="width:100%;border-radius:15px;height:44px;" onclick="checkKey()">GO</div>`;
    document.getElementById('key').focus();
}

function closeAuth(){ document.getElementById('mod').style.display='none'; document.getElementById('auth-area').innerHTML=''; }

function checkKey(){ 
    let k=document.getElementById('key').value.trim(); 
    fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({k})})
    .then(r=>r.json()).then(d=>{
      if(d.ok){localStorage.setItem('key',k);location.reload();}
      else alert('Invalid key');
    }); 
}

function triggerFile(){ 
    let f=document.createElement('input');f.type='file';f.accept='image/*'; 
    f.onchange=e=>{
        let r=new FileReader();
        r.onload=ev=>{
            let i=new Image();i.src=ev.target.result;
            i.onload=()=>{
                let c=document.createElement('canvas');let x=c.getContext('2d');
                let w=i.width,h=i.height,m=800;if(w>m){h*=m/w;w=m;}
                c.width=w;c.height=h;x.drawImage(i,0,0,w,h);
                post(null,c.toDataURL('image/jpeg',0.8));
                document.getElementById('plusMenu').style.display='none';
            };
        };r.readAsDataURL(f.files[0]);
    };f.click();
}

function addNote(){ 
  let n=prompt("Note:");
  if(n) { post(n); document.getElementById('plusMenu').style.display='none'; }
}

const plus=document.getElementById('plus'); 
const plusMenu=document.getElementById('plusMenu');

plus.addEventListener('click',(e)=>{
    e.stopPropagation();
    plusMenu.style.display = plusMenu.style.display==='flex' ? 'none' : 'flex'; 
});

document.addEventListener('click',()=>{ plusMenu.style.display='none'; });

// Загрузка истории
fetch('/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:uid,k:localStorage.getItem('key')})})
.then(r=>r.json()).then(d=>{
    if(d.history&&d.history.length>0) d.history.forEach(m=>add(m.c,m.r,null,m.id));
    else post("SYSTEM_INIT_TRIGGER");
    if(d.pro){document.getElementById('sts').innerText="PRO";document.getElementById('sts').className="badge pro";}
});
</script>
</body>
</html>
