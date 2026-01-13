#!/usr/bin/env python3
"""
EMILIJA AI - Asmeninis balso asistentas Emilijai
Kalba: Lietuviu, Anglu, Rusu
AI vardas: Krikšto tėtis - protingas ir rupestingas AI draugas
"""
import os, json, asyncio, requests, edge_tts, base64, re
from flask import Flask, render_template_string, request, jsonify, Response
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

load_dotenv()
app = Flask(__name__)

# API Keys
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
PPLX_API_KEY = os.getenv("PPLX_API_KEY")
PPLX_API_URL = "https://api.perplexity.ai/chat/completions"

# Profile for Emilia
PROFILE = {
    "name": "Emilia",
    "display_name": "EMILIA AI",
    "age": 11,
    "ai_name": "Krikšto tėtis",
    "voice_lt": "lt-LT-LeonasNeural",      # Male Lithuanian voice
    "voice_en": "en-US-AndrewNeural",       # Clear American male voice (no accent)
    "voice_ru": "ru-RU-DmitryNeural"        # Male Russian voice
}

# Conversation storage
HISTORY_FILE = Path("history_emilia.json")
conversation = []

def load_conversation():
    try:
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            conv = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
            print(f"[MEMORY] Loaded {len(conv)} messages")
            return conv
    except Exception as e:
        print(f"[MEMORY ERR] {e}")
    return []

def save_message(role, content):
    try:
        history = []
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        })
        if len(history) > 500:
            history = history[-500:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[SAVE ERR] {e}")

def detect_language(text):
    text_lower = text.lower()
    words = text_lower.split()

    # Russian characters - check first (Cyrillic)
    ru_chars = ['а', 'б', 'в', 'г', 'д', 'е', 'ё', 'ж', 'з', 'и', 'й', 'к', 'л', 'м',
                'н', 'о', 'п', 'р', 'с', 'т', 'у', 'ф', 'х', 'ц', 'ч', 'ш', 'щ', 'ъ',
                'ы', 'ь', 'э', 'ю', 'я']
    if any(c in text_lower for c in ru_chars):
        return "ru"

    # Lithuanian special characters
    lt_chars = ['ą', 'č', 'ę', 'ė', 'į', 'š', 'ų', 'ū', 'ž']
    if any(c in text_lower for c in lt_chars):
        return "lt"

    # Common English words (check before Lithuanian)
    en_words = ['the', 'is', 'are', 'was', 'were', 'have', 'has', 'had', 'do', 'does',
                'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might',
                'hello', 'hi', 'hey', 'how', 'what', 'where', 'when', 'why', 'who',
                'yes', 'no', 'please', 'thank', 'thanks', 'sorry', 'okay', 'ok',
                'good', 'great', 'nice', 'well', 'very', 'much', 'more', 'less',
                'this', 'that', 'these', 'those', 'here', 'there', 'now', 'then',
                'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her',
                'and', 'but', 'or', 'if', 'because', 'so', 'just', 'only', 'also',
                'about', 'with', 'for', 'from', 'into', 'like', 'want', 'need',
                'know', 'think', 'feel', 'see', 'hear', 'say', 'tell', 'ask',
                'help', 'let', 'make', 'get', 'go', 'come', 'take', 'give', 'find']

    # Lithuanian words (without special chars)
    lt_words = ['labas', 'kaip', 'aciu', 'prasau', 'gerai', 'taip', 'kas', 'kur',
                'kodel', 'kada', 'man', 'tau', 'jis', 'ji', 'mes', 'jus', 'as', 'tu',
                'noriu', 'galiu', 'reikia', 'zinau', 'suprantu', 'klausyk', 'pasakyk',
                'kokios', 'kokia', 'koks', 'kokie', 'naujienos', 'dabar', 'siandien',
                'sveiki', 'sveikas', 'sveika', 'laba', 'labai', 'gera', 'geras', 'gali',
                'nori', 'turi', 'matau', 'zinai', 'sakyk', 'klausiu', 'atsakyk',
                'emilija', 'tavo', 'mano', 'musu', 'jusu']

    # Count matches
    en_count = sum(1 for w in words if w in en_words)
    lt_count = sum(1 for w in words if w in lt_words)

    # If more English words, it's English
    if en_count > lt_count:
        return "en"
    if lt_count > 0:
        return "lt"

    # Default to English for unknown
    return "en"

def get_voice(language):
    voices = {
        "lt": PROFILE["voice_lt"],
        "en": PROFILE["voice_en"],
        "ru": PROFILE["voice_ru"]
    }
    return voices.get(language, PROFILE["voice_en"])

def clean_tts(text):
    text = re.sub(r"[#*`\[\]]", "", text)
    text = re.sub(r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]", "", text)
    return text.strip()

def gen_tts(text, voice, lang="en"):
    async def _g():
        # Higher pitch for English to sound younger
        rate = "+10%" if lang == "en" else "+5%"
        pitch = "+5Hz" if lang == "en" else "+0Hz"
        c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume="+50%")
        d = b""
        async for ch in c.stream():
            if ch["type"] == "audio":
                d += ch["data"]
        return d
    return asyncio.run(_g())

def search_perplexity(query):
    if not PPLX_API_KEY:
        return None
    try:
        print(f"[PPLX] Searching: {query[:50]}...")
        r = requests.post(PPLX_API_URL,
            headers={
                "Authorization": f"Bearer {PPLX_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": "Find current information. Be brief, facts only."},
                    {"role": "user", "content": query}
                ],
                "max_tokens": 500,
                "temperature": 0.2
            },
            timeout=30
        )
        if r.status_code == 200:
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"[PPLX ERROR] {e}")
    return None

def needs_search(text):
    keywords = [
        # English
        "news", "today", "current", "price", "weather", "latest", "now", "recent",
        "happening", "update", "score", "result", "live", "real", "actual",
        "how much", "how many", "what time", "when is", "where is", "who is",
        "search", "find", "look up", "google", "internet",
        # Lithuanian
        "naujienos", "šiandien", "siandien", "kaina", "oras", "dabar", "kas vyksta",
        "kiek", "kada", "kur yra", "kas yra", "rask", "surask", "ieškok", "ieskik",
        "internete", "Google", "žinios", "zinios", "rezultatas", "gyventoju", "gyventojų",
        # Russian
        "погода", "новости", "курс", "цена", "сейчас", "сегодня", "найди", "поищи",
        "сколько", "какой", "когда", "где", "кто", "интернет", "гугл"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)

def stream_grok(msgs):
    if not XAI_API_KEY:
        yield "[NO API KEY]"
        return
    try:
        r = requests.post(XAI_API_URL,
            headers={"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "grok-3-mini-fast",
                "messages": msgs,
                "max_tokens": 800,
                "temperature": 0.7,
                "reasoning_effort": "low",
                "stream": True
            },
            stream=True, timeout=60)
        if r.status_code != 200:
            print(f"[API ERROR] {r.status_code}: {r.text[:200]}")
            yield f"[Error {r.status_code}]"
            return
        for ln in r.iter_lines():
            if ln:
                ln = ln.decode("utf-8")
                if ln.startswith("data: "):
                    d = ln[6:]
                    if d == "[DONE]":
                        break
                    try:
                        cnt = json.loads(d).get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if cnt:
                            yield cnt
                    except:
                        pass
    except Exception as e:
        print(f"[ERROR] {e}")
        yield "[Connection error]"

# Beautiful HTML with pink theme for Emilija
HTML = """<!DOCTYPE html>
<html lang="lt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#ff69b4">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Emilija AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
background:linear-gradient(135deg,#ff9a9e 0%,#fecfef 50%,#fecfef 100%);
color:#333;min-height:100vh;min-height:100dvh;display:flex;flex-direction:column}

.birthday-banner{
    background:linear-gradient(45deg,#ff6b9d,#c44da1,#ff6b9d);
    padding:20px;text-align:center;
    animation:shimmer 3s infinite;
    box-shadow:0 4px 15px rgba(255,107,157,0.4);
}
@keyframes shimmer{
    0%,100%{background-position:0% 50%}
    50%{background-position:100% 50%}
}
.birthday-banner h1{
    color:#fff;font-size:1.8em;text-shadow:2px 2px 4px rgba(0,0,0,0.2);
    margin-bottom:5px;
}
.birthday-banner .age{
    font-size:3em;color:#fff;font-weight:bold;
    text-shadow:3px 3px 6px rgba(0,0,0,0.3);
    animation:bounce 1s infinite;
}
@keyframes bounce{
    0%,100%{transform:translateY(0)}
    50%{transform:translateY(-10px)}
}
.birthday-banner .subtitle{
    color:#fff;font-size:1.1em;margin-top:5px;
    opacity:0.9;
}

.confetti{position:fixed;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:1000}
.confetti-piece{position:absolute;width:10px;height:10px;animation:fall linear infinite}
@keyframes fall{
    0%{transform:translateY(-100px) rotate(0deg);opacity:1}
    100%{transform:translateY(100vh) rotate(720deg);opacity:0}
}

.header{padding:15px;text-align:center;background:rgba(255,255,255,0.9);border-bottom:3px solid #ff69b4}
h2{font-size:1.3em;color:#c44da1}
.status{padding:10px;text-align:center}
#st{display:inline-block;padding:10px 25px;border-radius:25px;background:rgba(255,105,180,.2);font-size:1em;
border:2px solid #ff69b4;color:#c44da1}
#st.listen{background:rgba(255,105,180,.3);color:#ff1493;border-color:#ff1493;animation:pulse 1s infinite}
#st.think{background:rgba(147,112,219,.3);color:#9370db;border-color:#9370db}
#st.speak{background:rgba(255,182,193,.4);color:#ff69b4;border-color:#ff69b4}
#st.err{background:rgba(255,0,0,.2);color:#f00}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,105,180,.4)}50%{box-shadow:0 0 0 15px rgba(255,105,180,0)}}

.chat{flex:1;overflow-y:auto;padding:15px;-webkit-overflow-scrolling:touch;background:rgba(255,255,255,0.7)}
.msg{margin:10px;padding:15px;border-radius:20px;max-width:85%;word-wrap:break-word;
box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.msg.user{background:linear-gradient(135deg,#ff9a9e,#fecfef);margin-left:auto;text-align:right;color:#333}
.msg.ai{background:linear-gradient(135deg,#a8edea,#fed6e3);color:#333}
.msg small{display:block;font-size:.75em;color:#666;margin-bottom:5px}

.controls{padding:20px;background:rgba(255,255,255,0.95);display:flex;flex-direction:column;align-items:center;gap:12px;
border-top:3px solid #ff69b4}
.mic-row{display:flex;align-items:center;gap:20px}
#mic{width:80px;height:80px;border-radius:50%;border:4px solid #ff69b4;
background:linear-gradient(135deg,#ff9a9e,#fecfef);
color:#c44da1;font-size:2.2em;cursor:pointer;-webkit-tap-highlight-color:transparent;
box-shadow:0 4px 15px rgba(255,105,180,0.4);transition:all 0.3s}
#mic:hover{transform:scale(1.05)}
#mic.on{background:linear-gradient(135deg,#ff6b9d,#ff1493);color:#fff;animation:pulse 1s infinite}
#mic.off{border-color:#ccc;color:#ccc;background:#f0f0f0}

.text-input{display:flex;width:100%;max-width:400px;gap:10px}
.text-input input{flex:1;padding:14px;border-radius:30px;border:2px solid #ff69b4;
background:#fff;color:#333;font-size:1em}
.text-input input::placeholder{color:#ffb6c1}
.text-input button{padding:14px 25px;border-radius:30px;border:none;
background:linear-gradient(135deg,#ff6b9d,#c44da1);color:#fff;font-weight:bold;cursor:pointer;
box-shadow:0 3px 10px rgba(196,77,161,0.3)}
#playBtn{display:none;padding:12px 30px;border-radius:25px;border:none;
background:linear-gradient(135deg,#9370db,#c44da1);color:#fff;font-weight:bold;cursor:pointer;margin-top:10px}
.lang-indicator{font-size:.7em;padding:3px 10px;border-radius:12px;background:rgba(255,105,180,0.2);margin-left:5px}
</style>
</head>
<body>

<div class="confetti" id="confetti"></div>

<div class="birthday-banner">
    <h1>Labas, Emilija!</h1>
    <div class="age">Emilija</div>
    <div class="subtitle">Tavo AI draugas - Krikšto tėtis</div>
</div>

<div class="header">
    <h2>Krikšto tėtis - Tavo AI Draugas</h2>
</div>
<div class="status"><span id="st">Paspausk mikrofona</span></div>
<div class="chat" id="chat"></div>
<div class="controls">
<div class="mic-row">
<button id="mic" onclick="toggleMic()">🎤</button>
</div>
<div class="text-input">
<input type="text" id="txtInput" placeholder="Rasyk cia..." onkeypress="if(event.key==='Enter')sendText()">
<button onclick="sendText()">Siusti</button>
</div>
<button id="playBtn" onclick="playAudio()">Paleisti</button>
</div>
<audio id="au" playsinline></audio>

<script>
// Confetti animation
function createConfetti(){
    const colors=['#ff69b4','#ff1493','#c44da1','#ffd700','#ff6b9d','#9370db','#00ff7f'];
    const confetti=document.getElementById('confetti');
    for(let i=0;i<50;i++){
        const piece=document.createElement('div');
        piece.className='confetti-piece';
        piece.style.left=Math.random()*100+'%';
        piece.style.background=colors[Math.floor(Math.random()*colors.length)];
        piece.style.animationDuration=(Math.random()*3+2)+'s';
        piece.style.animationDelay=Math.random()*5+'s';
        piece.style.borderRadius=Math.random()>0.5?'50%':'0';
        confetti.appendChild(piece);
    }
}
createConfetti();

const st=document.getElementById('st');
const chat=document.getElementById('chat');
const au=document.getElementById('au');
const mic=document.getElementById('mic');
const txtInput=document.getElementById('txtInput');
const playBtn=document.getElementById('playBtn');

let isProcessing=false;
let audioQueue=[];
let isPlaying=false;
let audioUnlocked=false;
let rec=null;
let listening=false;

async function unlockAudio(){
    if(audioUnlocked) return;
    try{
        au.src='data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYNAAAAAAAAAAAAAAAAAAAA';
        au.volume=0.01;
        await au.play();
        au.pause();
        au.volume=1;
        audioUnlocked=true;
    }catch(e){}
}

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let silenceTimer=null;

if(SR){
    rec=new SR();
    rec.lang='lt-LT';
    rec.continuous=false;
    rec.interimResults=true;

    rec.onstart=()=>{
        listening=true;
        mic.classList.add('on');
        mic.classList.remove('off');
        st.textContent='Klausau...';
        st.className='listen';
    };

    rec.onresult=(e)=>{
        const result=e.results[e.results.length-1];
        const text=result[0].transcript;
        st.textContent=text||'Klausau...';
        if(result.isFinal){
            if(silenceTimer) clearTimeout(silenceTimer);
            silenceTimer=setTimeout(()=>{
                if(!isProcessing){
                    sendMessage(text);
                }
            }, 800);
        }
    };

    rec.onend=()=>{
        listening=false;
        mic.classList.remove('on');
        if(!isProcessing){
            st.textContent='Pasiruosusi';
            st.className='';
        }
    };

    rec.onerror=(e)=>{
        listening=false;
        mic.classList.remove('on');
        if(silenceTimer) clearTimeout(silenceTimer);
        if(e.error==='not-allowed'){
            st.textContent='Nera prieigos prie mikrofono';
            st.className='err';
            mic.classList.add('off');
        }else if(e.error==='no-speech'){
            st.textContent='Pasiruosusi';
            st.className='';
        }
    };
}else{
    mic.classList.add('off');
}

async function toggleMic(){
    await unlockAudio();
    if(!rec){ st.textContent='Naudok teksto ivesti'; return; }
    if(listening){ rec.stop(); return; }
    if(isProcessing||isPlaying){
        au.pause();
        audioQueue=[];
        isPlaying=false;
        isProcessing=false;
    }
    try{ rec.start(); }catch(e){ st.textContent='Mikrofono klaida'; st.className='err'; }
}

function sendText(){
    const text=txtInput.value.trim();
    if(text){
        unlockAudio();
        txtInput.value='';
        sendMessage(text);
    }
}

function detectLang(text){
    const ltChars=/[ąčęėįšųūž]/i;
    const ruChars=/[а-яё]/i;
    if(ruChars.test(text)) return 'ru';
    if(ltChars.test(text)) return 'lt';
    return 'en';
}

function addMsg(role,text){
    const d=document.createElement('div');
    d.className='msg '+(role==='user'?'user':'ai');
    const lang=detectLang(text);
    const langLabel={lt:'LT',en:'EN',ru:'RU'}[lang]||'';
    d.innerHTML='<small>'+(role==='user'?'Emilija':'Krikšto tėtis')+' <span class="lang-indicator">'+langLabel+'</span></small><span class="txt">'+text+'</span>';
    chat.appendChild(d);
    chat.scrollTop=chat.scrollHeight;
    return d;
}

async function sendMessage(text){
    if(!text||isProcessing) return;

    isProcessing=true;
    audioQueue=[];
    isPlaying=false;
    au.pause();
    playBtn.style.display='none';

    addMsg('user',text);
    const gm=addMsg('ai','...');

    st.textContent='Galvoju...';
    st.className='think';

    try{
        const response=await fetch('/chat-stream',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({message:text})
        });

        if(!response.ok) throw new Error('HTTP '+response.status);

        const reader=response.body.getReader();
        const decoder=new TextDecoder();
        let fullText='';
        let buffer='';

        while(true){
            const{done,value}=await reader.read();
            if(done) break;

            buffer+=decoder.decode(value,{stream:true});
            const lines=buffer.split('\\n');
            buffer=lines.pop()||'';

            for(const line of lines){
                if(line.startsWith('data: ')){
                    const data=line.slice(6).trim();
                    if(data==='[DONE]'||!data) continue;
                    try{
                        const p=JSON.parse(data);
                        if(p.type==='text'&&p.content){
                            fullText+=p.content;
                            gm.querySelector('.txt').textContent=fullText;
                            chat.scrollTop=chat.scrollHeight;
                        }
                        if(p.type==='audio'&&p.audio){
                            audioQueue.push(p.audio);
                        }
                    }catch(e){}
                }
            }
        }

        if(audioQueue.length>0){
            st.textContent='Kalbu...';
            st.className='speak';
            playNext();
        }else{
            st.textContent='Pasiruosusi';
            st.className='';
            isProcessing=false;
        }

    }catch(e){
        st.textContent='Klaida';
        st.className='err';
        gm.querySelector('.txt').textContent='Rysio klaida';
        isProcessing=false;
    }
}

function playNext(){
    if(audioQueue.length===0){
        isPlaying=false;
        isProcessing=false;
        st.textContent='Pasiruosusi';
        st.className='';
        return;
    }

    isPlaying=true;
    const audioData=audioQueue.shift();

    au.src='data:audio/mp3;base64,'+audioData;
    au.volume=1.0;
    au.onended=playNext;
    au.onerror=(e)=>{ playNext(); };

    au.play().then(()=>{
    }).catch((e)=>{
        playBtn.style.display='block';
        st.textContent='Paspausk paleisti';
        st.className='speak';
    });
}

function playAudio(){
    playBtn.style.display='none';
    au.play().catch((e)=>{ playNext(); });
}
</script>
</body>
</html>
"""

conversation = load_conversation()

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/chat-stream", methods=["POST"])
def chat_endpoint():
    global conversation

    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"error": "empty"})

    print(f"[EMILIA] {msg}")

    # Detect language
    lang = detect_language(msg)
    print(f"[LANG] {lang}")

    # Save message
    save_message("user", msg)
    conversation.append({"role": "user", "content": msg})
    if len(conversation) > 20:
        conversation = conversation[-20:]

    # Search if needed
    search_context = ""
    if needs_search(msg):
        print(f"[SEARCH] Query needs current info...")
        result = search_perplexity(msg)
        if result:
            search_context = f"\n\n=== SVARBU: INFORMACIJA IŠ INTERNETO (naudok šią informaciją atsakymui!) ===\n{result}\n=== PABAIGA ===\n"
            print(f"[SEARCH RESULT] Found: {result[:100]}...")
        else:
            print(f"[SEARCH] No results returned")

    # Build system prompt
    today = datetime.now(ZoneInfo("Europe/Vilnius")).strftime("%Y-%m-%d %H:%M")

    system_prompt = f"""Tu esi Krikšto tėtis - protingas ir rupestingas AI draugas. Tu kalbi su Emilija (jai 11 metu).

SVARBU - KREIPIMASIS:
- VISADA kreipkis i ja "Emilija"
- Tu esi jos krikšto tetis - mylintis ir ismintas
- Pavyzdziai: "Labas, Emilija!", "Kaip sekasi, Emilija?", "Zinoma, Emilija!"

TAISYKLES:
- Bendraukis kaip kriksto tetis - rupestingai ir draugiskai, naudok "tu"
- Jei kalba lietuviškai - atsakyk lietuviškai
- Jei kalba angliškai - atsakyk angliškai ir SVELNIAI pataisyk klaidas (pasakyk teisinga varianta)
- Jei kalba rusiškai - atsakyk rusiškai
- Buk protingas, kantrus ir palaikantis
- Atsakymai trumpi - 1-3 sakiniai
- JOKIU emoji! Tai balso isvestis
- Padek mokytis anglu kalbos - pagirti ir svelniai pataisyti klaidas
- Emilijai yra 11 metu, ji mokosi 5 klaseje
{search_context}
INTERNETO PAIEŠKA:
- Jei žemiau yra "INFORMACIJA IŠ INTERNETO" - BŪTINAI naudok tą informaciją atsakymui!
- Tai yra TIKRI, AKTUALŪS duomenys iš interneto paieškos
- Atsakyk remiantis šia informacija, ne savo žiniomis

Dabartinis laikas: {today}
Aptikta kalba: {lang}

SVARBU:
- JOKIU emoji! Tai balso isvestis
- Atsakymai TRUMPI (1-3 sakiniai)
- Atitik vartotojo kalba
- Jei yra interneto informacija - NAUDOK ją!"""

    msgs = [{"role": "system", "content": system_prompt}] + conversation

    # Get voice for detected language
    voice = get_voice(lang)
    print(f"[VOICE] {voice}")

    def gen():
        full, buf = "", ""
        for tok in stream_grok(msgs):
            full += tok
            buf += tok
            yield f'data: {json.dumps({"type": "text", "content": tok})}\n\n'

            if re.search(r"[.!?]\s*$", buf) and len(buf) > 15:
                s = clean_tts(buf)
                if s:
                    try:
                        # Detect language of response text for correct voice
                        resp_lang = detect_language(s)
                        resp_voice = get_voice(resp_lang)
                        ad = gen_tts(s, resp_voice, resp_lang)
                        yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                    except Exception as e:
                        print(f"[TTS ERROR] {e}")
                buf = ""

        if buf:
            s = clean_tts(buf)
            if s:
                try:
                    resp_lang = detect_language(s)
                    resp_voice = get_voice(resp_lang)
                    ad = gen_tts(s, resp_voice, resp_lang)
                    yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                except Exception as e:
                    print(f"[TTS ERROR] {e}")

        save_message("assistant", full)
        conversation.append({"role": "assistant", "content": full})
        yield "data: [DONE]\n\n"

    return Response(gen(), mimetype="text/event-stream")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5565))
    print("=" * 50)
    print("EMILIA AI - Krikšto tėtis")
    print(f"http://localhost:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, threaded=True)
