import os
import time
import json
import random
import sys
import re
import threading
import hmac
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
from collections import defaultdict
from datetime import datetime

# Redis Setup (Optional)
try: 
    import redis
except ImportError: 
    redis = None

def safe_str_eq(a, b):
    if not a or not b: return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

app = Flask(__name__)

# --- CONFIG ---
DEFAULT_KEY = "START-2026"
ACCESS_KEY = os.environ.get("ACCESS_KEY", DEFAULT_KEY)
REDIS_URL = os.environ.get("REDIS_URL") 
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try: 
        client = OpenAI(api_key=OPENAI_API_KEY)
    except: 
        pass

# --- CONSTANTS ---
MODEL_FREE = "gpt-5-mini"
MODEL_PAID = "gpt-5-mini" 
HARD_LIMIT_FREE = 10 
HARD_LIMIT_PAID = 10 
BACKUP_FILE = "backup_db.json"
MAX_HISTORY = 50 
REDIS_TTL = 2592000

# ==========================================
# 🛠️ LOGIC
# ==========================================
def parse_baseline(text):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    stats = {'raw': text}
    if len(nums) >= 2: stats['height'], stats['weight'] = nums[0], nums[1]
    if len(nums) >= 3: stats['age'] = nums[2]
    return stats

def detect_vibe(text):
    t = text.lower()
    if any(w in t for w in ['david', 'laid', 'aesthetic']): return "AESTHETIC"
    if any(w in t for w in ['power', 'bench', 'squat']): return "POWER"
    return "MENTOR"

class DataManager:
    def __init__(self):
        self.r = None
        self.local = defaultdict(lambda: self._schema())
        self.lock = threading.Lock()
        if REDIS_URL and redis:
            try: 
                self.r = redis.from_url(REDIS_URL, decode_responses=True)
            except: 
                pass
        if not self.r: self._load()

    def _schema(self):
        return {'history': [], 'step': 'HOOK', 'profile': {'vibe': 'MENTOR'}, 'count': 0, 'count_free': 0, 'last': time.time()}

    def _load(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE) as f:
                    d = json.load(f)
                    for k, v in d.items(): self.local[k] = v
            except: pass

    def _save(self):
        def task():
            with self.lock:
                try: 
                    with open(BACKUP_FILE, 'w') as f: json.dump(self.local, f)
                except: pass
        threading.Thread(target=task).start()

    def get(self, uid):
        if self.r:
            try: 
                d = self.r.get(f"u:{uid}")
                if d: return json.loads(d)
            except: pass
        return self.local[uid]

    def set(self, uid, data):
        if len(data['history']) > MAX_HISTORY: data['history'] = data['history'][-MAX_HISTORY:]
        if self.r:
            try: self.r.set(f"u:{uid}", json.dumps(data), ex=REDIS_TTL)
            except: pass
        self.local[uid] = data
        if not self.r: self._save()

db = DataManager()

def get_sys(profile):
    vibe = profile.get('vibe', 'MENTOR')
    guide = "Be calm."
    if vibe == "AESTHETIC": guide = "Focus on symmetry, aesthetics, discipline. Cold tone."
    elif vibe == "POWER": guide = "Focus on strength, load, eating. Heavy tone."
    
    return f"""Role: Personal Coach. Vibe: {vibe}. Guide: {guide}. 
    Context: {profile.get('goal', 'New client')}. 
    Rules: Human tone. Short answers. No fluff."""

# ==========================================
# 🖥️ FRONTEND
# ==========================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#ffffff">
<title>Coach</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
body{font-family:-apple-system,sans-serif;margin:0;height:100dvh;display:flex;flex-direction:column;overflow:hidden;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom);overscroll-behavior:none;}
.head{position:fixed;top:0;left:0;width:100%;height:50px;background:rgba(255,255,255,0.95);display:flex;align-items:center;justify-content:space-between;padding:0 15px;padding-top:max(10px,env(safe-area-inset-top));border-bottom:1px solid #eee;z-index:99;}
.logo{font-weight:700;color:#888;font-size:14px;letter-spacing:1px;}
.badge{font-size:10px;border:1px solid #ddd;padding:3px 8px;border-radius:20px;color:#888;cursor:pointer;}
.badge.pro{background:#2563eb;color:#fff;border:none;}
.msg-controls{font-size:14px;margin-left:8px;cursor:pointer;opacity:0.6;}
#box{flex:1;overflow-y:auto;padding:60px 15px 80px;display:flex;flex-direction:column;gap:12px;}
.msg{max-width:85%;padding:10px 16px;border-radius:18px;font-size:16px;line-height:1.4;word-wrap:break-word;position:relative;animation:fadeUp 0.2s ease-out;}
@keyframes fadeUp{from{opacity:0;transform:translateY(5px);}to{opacity:1;transform:translateY(0);}}
.bot{background:#f3f4f6;align-self:flex-start;color:#000;border-bottom-left-radius:4px;}
.usr{background:#2563eb;color:white;align-self:flex-end;border-bottom-right-radius:4px;}
.msg img{max-width:100%;border-radius:10px;margin-top:5px;}
.inp{position:fixed;bottom:0;left:0;width:100%;background:#fff;padding:10px 15px;padding-bottom:max(10px,env(safe-area-inset-bottom));border-top:1px solid #eee;display:flex;gap:10px;align-items:flex-end;z-index:99;}
.txt-div{flex:1;padding:10px 14px;border-radius:20px;border:1px solid #ddd;font-size:16px;outline:none;max-height:120px;overflow-y:auto;min-height:42px;background:#fff;caret-color:#2563eb;}
.txt-div:empty:before{content:attr(data-placeholder);color:#9ca3af;}
.txt-div:focus{border-color:#999;}
.btn{width:42px;height:42px;display:flex;align-items:center;justify-content:center;border-radius:50%;border:1px solid #ddd;font-size:20px;cursor:pointer;color:#555;flex-shrink:0;}
.send{background:#2563eb;color:white;border:none;}
#mod{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(3px);}
.win{background:#fff;padding:30px;border-radius:20px;width:80%;max-width:300px;text-align:center;}
</style>
</head>
<body>
<div class="head">
    <div class="logo">COACH V74</div>
    <div id="sts" class="badge" onclick="showAuth()">ACCESS</div>
</div>

<div id="box" onclick="blurInput()"></div>

<div class="inp">
    <div class="btn" onclick="trigFile()">📷</div>
    <div class="txt-div" id="txt" contenteditable="true" data-placeholder="Message..."></div>
    <div class="btn send" onclick="send()">↑</div>
</div>

<div id="mod">
    <div class="win">
        <h3>UNLOCK</h3>
        <div id="auth-area"></div>
        <p onclick="closeAuth()" style="margin-top:20px;color:#888;font-size:12px;">Close</p>
    </div>
</div>

<script>
const b=document.getElementById('box'), t=document.getElementById('txt'), uid=localStorage.getItem('uid')||'u'+Date.now();
localStorage.setItem('uid',uid);

function blurInput(){ t.blur(); }

function add(msg,role,img,mid=null){
    let d=document.createElement('div');d.className='msg '+role;d.dataset.mid=mid||('m'+Date.now());
    if(img)d.innerHTML=`<img src="${img}"><br>`+(msg||'Analyzing...');
    else d.innerHTML=role=='usr'?msg.replace(/\\n/g,'<br>'):marked.parse(msg);
    
    if(role=='usr'){
        let ctrls=document.createElement('span');ctrls.className='msg-controls';ctrls.innerText='✎';
        ctrls.onclick=(e)=>{e.stopPropagation();showEditDelete(d.dataset.mid,msg);};
        d.appendChild(ctrls);
    }
    b.appendChild(d);b.scrollTop=b.scrollHeight;
}

function showEditDelete(mid,currentText){
    let newText=prompt("Edit message:",currentText);
    if(newText!==null && newText!==currentText){
        if(newText===""){
            if(confirm("Delete message?")){
                fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:uid,mid:mid})})
                .then(r=>r.json()).then(d=>{if(d.ok)location.reload();});
            }
        } else {
            fetch('/edit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:uid,mid:mid,new_text:newText})})
            .then(r=>r.json()).then(d=>{if(d.ok)location.reload();});
        }
    }
}

function post(txt,img){
    txt=txt||t.innerText.trim();if(!txt && !img)return;
    if(!img){add(txt,'usr');t.innerText='';}else add("Analyzing...",'usr',img);
    
    fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:txt,img,uid,k:localStorage.getItem('key')})})
    .then(r=>r.json()).then(d=>{
        if(d.pro){document.getElementById('sts').innerText="PRO";document.getElementById('sts').className="badge pro";}
        add(d.reply,'bot');
    }).catch(()=>add("Error connecting",'bot'));
}

function send(){post();}

t.addEventListener('keydown',(e)=>{if(e.key==='Enter'){if(e.shiftKey)return;e.preventDefault();send();}});
t.addEventListener('paste',(e)=>{e.preventDefault();let text=(e.originalEvent||e).clipboardData.getData('text/plain');document.execCommand('insertText',false,text);});

function showAuth(){
    document.getElementById('mod').style.display='flex';
    document.getElementById('auth-area').innerHTML='<input type="text" id="key" placeholder="ENTER KEY" style="width:100%;margin:15px 0;text-align:center;font-size:16px;padding:10px;border:1px solid #ddd;border-radius:10px;"><div class="btn send" style="width:100%;border-radius:15px;" onclick="checkKey()">GO</div>';
    document.getElementById('key').focus();
}
function closeAuth(){document.getElementById('mod').style.display='none';document.getElementById('auth-area').innerHTML='';}

function checkKey(){
    let k=document.getElementById('key').value.trim();
    fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({k})})
    .then(r=>r.json()).then(d=>{if(d.ok){localStorage.setItem('key',k);location.reload();}else alert('Invalid');});
}

function trigFile(){
    let f=document.createElement('input');f.type='file';f.accept='image/*';
    f.onchange=e=>{
        let r=new FileReader();
        r.onload=ev=>{
            let i=new Image();i.src=ev.target.result;
            i.onload=()=>{
                let c=document.createElement('canvas');let x=c.getContext('2d');
                let w=i.width,h=i.height,m=800;if(w>m){h*=m/w;w=m;}c.width=w;c.height=h;
                x.drawImage(i,0,0,w,h);
                post(null,c.toDataURL('image/jpeg',0.8));
            }
        };r.readAsDataURL(f.files[0]);
    };f.click();
}

// Load history
fetch('/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:uid,k:localStorage.getItem('key')})})
.then(r=>r.json()).then(d=>{
    if(d.history&&d.history.length>0){
        d.history.forEach(m=>{add(m.c,m.r,null,m.id);});
    } else post("SYSTEM_INIT_TRIGGER");
    if(d.pro){document.getElementById('sts').innerText="PRO";document.getElementById('sts').className="badge pro";}
});
</script>
</body>
</html>
"""

# ==========================================
# 🛠️ SERVER ROUTES
# ==========================================
@app.route('/')
def home(): return render_template_string(HTML_PAGE)

@app.route('/verify', methods=['POST'])
def verify(): return jsonify({"ok": safe_str_eq(request.json.get('k'), ACCESS_KEY)})

@app.route('/edit', methods=['POST'])
def edit_msg():
    data=request.json
    uid,mid,new_text=data.get('uid'),data.get('mid'),data.get('new_text')
    user=db.get(uid)
    for m in user['history']:
        if m.get('id')==mid or m.get('id')==str(mid):
            m['c']=new_text;break
    db.set(uid,user)
    return jsonify({"ok":True})

@app.route('/delete', methods=['POST'])
def delete_msg():
    data=request.json
    uid,mid=data.get('uid'),data.get('mid')
    user=db.get(uid)
    user['history']=[m for m in user['history'] if m.get('id')!=mid and m.get('id')!=str(mid)]
    db.set(uid,user)
    return jsonify({"ok":True})

@app.route('/history', methods=['POST'])
def history():
    d=request.json
    uid,key=d.get('uid'),d.get('k')
    user=db.get(uid)
    is_paid=safe_str_eq(key,ACCESS_KEY)
    # Generate IDs if missing (for legacy messages)
    for m in user['history']:
        if 'id' not in m: m['id']='m'+str(int(time.time()*1000)+random.randint(0,999))
    return jsonify({"history":user['history'],"pro":is_paid})

@app.route('/chat', methods=['POST'])
def chat():
    d=request.json
    msg,img,uid,key=d.get('msg'),d.get('img'),d.get('uid'),d.get('k')
    paid=safe_str_eq(key,ACCESS_KEY)
    
    if msg=="SYSTEM_INIT_TRIGGER": return jsonify({"reply":"I'm your coach. What is your goal?","pro":paid})
    
    user=db.get(uid)
    if not paid and user['count_free']>=HARD_LIMIT_FREE: return jsonify({"reply":"Free limit reached. Access required."})
    if paid and user['count']>=HARD_LIMIT_PAID: return jsonify({"reply":"Daily limit reached."})
    
    reply="..."
    if not client: 
        reply="AI Offline"
    else:
        try:
            model=MODEL_PAID if paid else MODEL_FREE
            sys_p=get_sys(user['profile'])
            msgs=[{"role":"system","content":sys_p}]
            
            if img:
                if not paid: reply="Photos are Premium."
                else:
                    msgs.append({"role":"user","content":[{"type":"text","text":"Analyze"},{"type":"image_url","image_url":{"url":img}}]})
                    r=client.chat.completions.create(model=model,messages=msgs)
                    reply=r.choices[0].message.content
            else:
                if user['step']=='HOOK':
                    user['profile']['goal']=msg;user['profile']['vibe']=detect_vibe(msg);user['step']='BASE';reply="Got it. Height/Weight?"
                elif user['step']=='BASE':
                    user['profile']['stats']=msg;user['step']='DONE';reply="Locked. How do you train?"
                else:
                    context_msgs=[]
                    for m in user['history'][-6:]:
                        role='user' if m['r']=='usr' else 'assistant'
                        context_msgs.append({'role':role,'content':m['c']})
                    msgs.extend(context_msgs)
                    msgs.append({"role":"user","content":msg})
                    r=client.chat.completions.create(model=model,messages=msgs)
                    reply=r.choices[0].message.content
        except Exception as e:
            print(f"Error: {e}")
            reply="Error generating response."
            
    # Save with unique IDs for editing
    new_mid_user='m'+str(int(time.time()*1000))
    new_mid_bot='m'+str(int(time.time()*1000)+1)
    
    user['history'].append({'r':'usr','c':msg or '[IMG]','id':new_mid_user})
    user['history'].append({'r':'bot','c':reply,'id':new_mid_bot})
    
    if not paid: user['count_free']+=1
    else: user['count']+=1
    db.set(uid,user)
    
    return jsonify({"reply":reply,"pro":paid})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get("PORT",5000)))
