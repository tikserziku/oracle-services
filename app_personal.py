#!/usr/bin/env python3
"""
Personal AI Assistant - Multi-user architecture
Each user gets their own URL, voice, personality, and conversation history
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

# Load profiles
PROFILES_FILE = Path("profiles.json")
PROFILES = {}
if PROFILES_FILE.exists():
    PROFILES = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    print(f"[PROFILES] Loaded {len(PROFILES)} profiles")

# Conversation storage per user
CONVERSATIONS = {}

def get_history_file(user_id):
    return Path(f"history_{user_id}.json")

def load_conversation(user_id):
    """Load conversation history for specific user"""
    try:
        history_file = get_history_file(user_id)
        if history_file.exists():
            history = json.loads(history_file.read_text(encoding="utf-8"))
            conv = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
            print(f"[{user_id}] Loaded {len(conv)} messages")
            return conv
    except Exception as e:
        print(f"[{user_id}] Memory error: {e}")
    return []

def save_message(user_id, role, content):
    """Save message to user's history"""
    try:
        history_file = get_history_file(user_id)
        history = []
        if history_file.exists():
            history = json.loads(history_file.read_text(encoding="utf-8"))
        history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        })
        if len(history) > 500:
            history = history[-500:]
        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[{user_id}] Save error: {e}")

def detect_language(text):
    """Detect if text is Lithuanian, English, or Russian"""
    text_lower = text.lower()

    # Lithuanian specific characters and words
    lt_chars = ['ą', 'č', 'ę', 'ė', 'į', 'š', 'ų', 'ū', 'ž']
    lt_words = ['labas', 'kaip', 'ačiū', 'prašau', 'gerai', 'taip', 'ne', 'kas', 'kur',
                'kodėl', 'kada', 'man', 'tau', 'jis', 'ji', 'mes', 'jūs', 'aš', 'tu',
                'noriu', 'galiu', 'reikia', 'žinau', 'suprantu', 'klausyk', 'pasakyk',
                # Common words without diacritics
                'kokios', 'kokia', 'koks', 'kokie', 'naujienos', 'dabar', 'siandien',
                'vakar', 'rytoj', 'yra', 'esi', 'esu', 'esame', 'ar', 'bet', 'ir', 'tai',
                'tik', 'cia', 'ten', 'kiek', 'del', 'nuo', 'iki', 'apie', 'prie', 'po',
                'sveiki', 'sveikas', 'sveika', 'laba', 'labai', 'gera', 'geras', 'gali',
                'nori', 'turi', 'matau', 'zinai', 'sakyk', 'klausiu', 'atsakyk']

    # Russian specific
    ru_chars = ['а', 'б', 'в', 'г', 'д', 'е', 'ё', 'ж', 'з', 'и', 'й', 'к', 'л', 'м',
                'н', 'о', 'п', 'р', 'с', 'т', 'у', 'ф', 'х', 'ц', 'ч', 'ш', 'щ', 'ъ',
                'ы', 'ь', 'э', 'ю', 'я']

    # Check for Cyrillic (Russian)
    if any(c in text_lower for c in ru_chars):
        return "ru"

    # Check for Lithuanian
    if any(c in text_lower for c in lt_chars):
        return "lt"
    if any(word in text_lower.split() for word in lt_words):
        return "lt"

    # Default to English
    return "en"

def get_voice(profile, language):
    """Get appropriate voice for language"""
    voice_key = f"voice_{language}"
    return profile.get(voice_key, profile.get("voice_en", "en-US-JennyNeural"))

def clean_tts(text):
    """Clean text for TTS"""
    text = re.sub(r"[#*`\[\]]", "", text)
    text = re.sub(r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]", "", text)
    return text.strip()

def gen_tts(text, voice):
    """Generate TTS audio with specified voice"""
    async def _g():
        c = edge_tts.Communicate(text, voice, rate="+5%", volume="+50%")
        d = b""
        async for ch in c.stream():
            if ch["type"] == "audio":
                d += ch["data"]
        return d
    return asyncio.run(_g())

def search_perplexity(query):
    """Search current info via Perplexity"""
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
    """Check if query needs internet search"""
    keywords = [
        # English
        "news", "today", "current", "price", "weather", "latest", "now", "recent",
        "what time", "what date", "who is", "what is happening",
        # Lithuanian
        "naujienos", "šiandien", "kaina", "oras", "dabar", "kas vyksta", "kiek",
        "kas yra", "koks laikas", "kokia data",
        # Russian
        "погода", "новости", "курс", "цена", "сейчас", "сегодня", "который час"
    ]
    return any(kw in text.lower() for kw in keywords)

def stream_grok(msgs):
    """Stream response from Grok"""
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

# HTML Template with user customization
def get_html(profile, user_id):
    name = profile.get("name", "User")
    display_name = profile.get("display_name", "AI Assistant")
    chat_url = f"/{user_id}/chat-stream"

    return f"""<!DOCTYPE html>
<html lang="lt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#1a1a2e">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>{display_name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,system-ui,sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:#fff;
min-height:100vh;min-height:100dvh;display:flex;flex-direction:column}}
.header{{padding:15px;text-align:center;background:rgba(0,0,0,.3)}}
h1{{font-size:1.4em;color:#f0a}}
.subtitle{{font-size:0.9em;color:#aaa;margin-top:5px}}
.status{{padding:10px;text-align:center}}
#st{{display:inline-block;padding:8px 20px;border-radius:20px;background:rgba(100,100,100,.3);font-size:.9em}}
#st.listen{{background:rgba(255,0,170,.2);color:#f0a;border:2px solid #f0a}}
#st.think{{background:rgba(0,212,255,.2);color:#0df;border:2px solid #0df}}
#st.speak{{background:rgba(168,85,247,.2);color:#a8f;border:2px solid #a8f}}
#st.err{{background:rgba(255,68,68,.2);color:#f44}}
.chat{{flex:1;overflow-y:auto;padding:10px;-webkit-overflow-scrolling:touch}}
.msg{{margin:8px;padding:12px;border-radius:15px;max-width:85%;word-wrap:break-word}}
.msg.user{{background:rgba(255,0,170,.2);margin-left:auto;text-align:right}}
.msg.ai{{background:rgba(100,100,255,.15)}}
.msg small{{display:block;font-size:.7em;color:#888;margin-bottom:4px}}
.correction{{background:rgba(255,200,0,.1);border-left:3px solid #fc0;padding:5px;margin-top:5px;font-size:0.85em}}
.controls{{padding:15px;background:rgba(0,0,0,.4);display:flex;flex-direction:column;align-items:center;gap:10px}}
.mic-row{{display:flex;align-items:center;gap:15px}}
#mic{{width:70px;height:70px;border-radius:50%;border:3px solid #f0a;background:rgba(255,0,170,.1);
color:#f0a;font-size:2em;cursor:pointer;-webkit-tap-highlight-color:transparent}}
#mic.on{{background:rgba(255,0,170,.3);animation:pulse 1s infinite}}
#mic.off{{border-color:#666;color:#666;background:rgba(100,100,100,.2)}}
@keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(255,0,170,.4)}}50%{{box-shadow:0 0 0 15px rgba(255,0,170,0)}}}}
.text-input{{display:flex;width:100%;max-width:400px;gap:8px}}
.text-input input{{flex:1;padding:12px;border-radius:25px;border:none;background:rgba(255,255,255,.1);color:#fff;font-size:1em}}
.text-input input::placeholder{{color:#888}}
.text-input button{{padding:12px 20px;border-radius:25px;border:none;background:#f0a;color:#000;font-weight:bold;cursor:pointer}}
#playBtn{{display:none;padding:10px 25px;border-radius:20px;border:none;background:#a8f;color:#000;font-weight:bold;cursor:pointer;margin-top:10px}}
.lang-indicator{{font-size:0.7em;padding:2px 8px;border-radius:10px;background:rgba(255,255,255,.1);margin-left:5px}}
</style>
</head>
<body>
<div class="header">
<h1>{display_name}</h1>
<div class="subtitle">Labas, {name}!</div>
</div>
<div class="status"><span id="st">Paspausk mikrofoną</span></div>
<div class="chat" id="chat"></div>
<div class="controls">
<div class="mic-row">
<button id="mic" onclick="toggleMic()">🎤</button>
</div>
<div class="text-input">
<input type="text" id="txtInput" placeholder="Arba rašyk čia..." onkeypress="if(event.key==='Enter')sendText()">
<button onclick="sendText()">OK</button>
</div>
<button id="playBtn" onclick="playAudio()">▶ Paleisti</button>
</div>
<audio id="au" playsinline></audio>

<script>
const userName = "{name}";
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

async function unlockAudio(){{
    if(audioUnlocked) return;
    try{{
        au.src='data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYYNAAAAAAAAAAAAAAAAAAAA';
        au.volume=0.01;
        await au.play();
        au.pause();
        au.volume=1;
        audioUnlocked=true;
    }}catch(e){{}}
}}

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
let silenceTimer=null;

if(SR){{
    rec=new SR();
    rec.lang='lt-LT';
    rec.continuous=false;
    rec.interimResults=true;

    rec.onstart=()=>{{
        listening=true;
        mic.classList.add('on');
        mic.classList.remove('off');
        st.textContent='Klausau...';
        st.className='listen';
    }};

    rec.onresult=(e)=>{{
        const result=e.results[e.results.length-1];
        const text=result[0].transcript;
        st.textContent=text||'Klausau...';

        // If final result, wait a bit then send (allows continuing)
        if(result.isFinal){{
            if(silenceTimer) clearTimeout(silenceTimer);
            silenceTimer=setTimeout(()=>{{
                if(!isProcessing){{
                    sendMessage(text);
                }}
            }}, 800); // 0.8 sec after final = send
        }}
    }};

    rec.onend=()=>{{
        listening=false;
        mic.classList.remove('on');
        if(!isProcessing){{
            st.textContent='Pasiruošusi';
            st.className='';
        }}
    }};

    rec.onerror=(e)=>{{
        listening=false;
        mic.classList.remove('on');
        if(silenceTimer) clearTimeout(silenceTimer);
        if(e.error==='not-allowed'){{
            st.textContent='Nėra prieigos prie mikrofono';
            st.className='err';
            mic.classList.add('off');
        }}else if(e.error==='no-speech'){{
            st.textContent='Pasiruošusi';
            st.className='';
        }}
    }};
}}else{{
    mic.classList.add('off');
}}

async function toggleMic(){{
    await unlockAudio();
    if(!rec){{ st.textContent='Naudok teksto įvestį'; return; }}
    if(listening){{ rec.stop(); return; }}
    if(isProcessing||isPlaying){{
        au.pause();
        audioQueue=[];
        isPlaying=false;
        isProcessing=false;
    }}
    try{{ rec.start(); }}catch(e){{ st.textContent='Mikrofono klaida'; st.className='err'; }}
}}

function sendText(){{
    const text=txtInput.value.trim();
    if(text){{
        unlockAudio();
        txtInput.value='';
        sendMessage(text);
    }}
}}

function detectLang(text){{
    const ltChars=/[ąčęėįšųūž]/i;
    const ruChars=/[а-яё]/i;
    if(ruChars.test(text)) return 'ru';
    if(ltChars.test(text)) return 'lt';
    return 'en';
}}

function addMsg(role,text){{
    const d=document.createElement('div');
    d.className='msg '+(role==='user'?'user':'ai');
    const lang=detectLang(text);
    const langLabel={{lt:'LT',en:'EN',ru:'RU'}}[lang]||'';
    d.innerHTML='<small>'+(role==='user'?userName:'Mila')+' <span class="lang-indicator">'+langLabel+'</span></small><span class="txt">'+text+'</span>';
    chat.appendChild(d);
    chat.scrollTop=chat.scrollHeight;
    return d;
}}

async function sendMessage(text){{
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

    try{{
        const response=await fetch('{chat_url}',{{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body:JSON.stringify({{message:text}})
        }});

        if(!response.ok) throw new Error('HTTP '+response.status);

        const reader=response.body.getReader();
        const decoder=new TextDecoder();
        let fullText='';
        let buffer='';

        while(true){{
            const{{done,value}}=await reader.read();
            if(done) break;

            buffer+=decoder.decode(value,{{stream:true}});
            const lines=buffer.split('\\n');
            buffer=lines.pop()||'';

            for(const line of lines){{
                if(line.startsWith('data: ')){{
                    const data=line.slice(6).trim();
                    if(data==='[DONE]'||!data) continue;
                    try{{
                        const p=JSON.parse(data);
                        if(p.type==='text'&&p.content){{
                            fullText+=p.content;
                            gm.querySelector('.txt').textContent=fullText;
                            chat.scrollTop=chat.scrollHeight;
                        }}
                        if(p.type==='audio'&&p.audio){{
                            audioQueue.push(p.audio);
                        }}
                    }}catch(e){{}}
                }}
            }}
        }}

        if(audioQueue.length>0){{
            st.textContent='Kalbu...';
            st.className='speak';
            playNext();
        }}else{{
            st.textContent='Pasiruošusi';
            st.className='';
            isProcessing=false;
        }}

    }}catch(e){{
        st.textContent='Klaida';
        st.className='err';
        gm.querySelector('.txt').textContent='Ryšio klaida';
        isProcessing=false;
    }}
}}

function playNext(){{
    if(audioQueue.length===0){{
        isPlaying=false;
        isProcessing=false;
        st.textContent='Pasiruošusi';
        st.className='';
        return;
    }}

    isPlaying=true;
    const audioData=audioQueue.shift();

    au.src='data:audio/mp3;base64,'+audioData;
    au.volume=1.0;
    au.onended=playNext;
    au.onerror=(e)=>{{ playNext(); }};

    au.play().then(()=>{{
    }}).catch((e)=>{{
        playBtn.style.display='block';
        st.textContent='Paspausk paleisti';
        st.className='speak';
    }});
}}

function playAudio(){{
    playBtn.style.display='none';
    au.play().catch((e)=>{{ playNext(); }});
}}
</script>
</body>
</html>
"""

def create_user_app(user_id, profile):
    """Create routes for specific user"""

    @app.route(f"/{user_id}")
    def user_index():
        return get_html(profile, user_id)

    @app.route(f"/{user_id}/chat-stream", methods=["POST"])
    def user_chat():
        global CONVERSATIONS

        if user_id not in CONVERSATIONS:
            CONVERSATIONS[user_id] = load_conversation(user_id)

        msg = request.json.get("message", "")
        if not msg:
            return jsonify({"error": "empty"})

        print(f"[{user_id}] {msg}")

        # Detect language
        lang = detect_language(msg)
        print(f"[{user_id}] Language: {lang}")

        # Save message
        save_message(user_id, "user", msg)
        CONVERSATIONS[user_id].append({"role": "user", "content": msg})
        if len(CONVERSATIONS[user_id]) > 20:
            CONVERSATIONS[user_id] = CONVERSATIONS[user_id][-20:]

        # Search if needed
        search_context = ""
        print(f"[{user_id}] Checking search for: {msg[:50]}")
        if needs_search(msg):
            print(f"[{user_id}] SEARCH TRIGGERED!")
            result = search_perplexity(msg)
            if result:
                print(f"[{user_id}] Got search result: {len(result)} chars")
                search_context = f"\n\nCURRENT INFO FROM INTERNET:\n{result}\n"
            else:
                print(f"[{user_id}] No search result")

        # Build system prompt
        today = datetime.now(ZoneInfo("Europe/Vilnius")).strftime("%Y-%m-%d %H:%M")
        base_prompt = profile.get("system_prompt", "You are a helpful assistant.")

        # Add English teacher instructions if enabled
        english_mode = ""
        if profile.get("english_teacher_mode") and lang == "en":
            english_mode = """
ENGLISH TEACHING MODE:
- The user is practicing English
- If there are grammar/spelling mistakes, GENTLY correct them
- Say the correct version naturally in your response
- Be encouraging!
- Example: If user says "I go yesterday", respond with something like "Nice try! You mean 'I went yesterday'. So, where did you go?"
"""

        system_prompt = f"""{base_prompt}
{english_mode}
{search_context}
Current time: {today}
Detected language: {lang}

IMPORTANT:
- NO emojis! This is voice output
- Keep answers SHORT (1-3 sentences)
- Match the user's language
"""

        msgs = [{"role": "system", "content": system_prompt}] + CONVERSATIONS[user_id]

        # Get voice for detected language
        voice = get_voice(profile, lang)
        print(f"[{user_id}] Using voice: {voice}")

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
                            ad = gen_tts(s, voice)
                            yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                        except Exception as e:
                            print(f"[TTS ERROR] {e}")
                    buf = ""

            if buf:
                s = clean_tts(buf)
                if s:
                    try:
                        ad = gen_tts(s, voice)
                        yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                    except Exception as e:
                        print(f"[TTS ERROR] {e}")

            save_message(user_id, "assistant", full)
            CONVERSATIONS[user_id].append({"role": "assistant", "content": full})
            yield "data: [DONE]\n\n"

        return Response(gen(), mimetype="text/event-stream")

    return user_index, user_chat

# Register routes for all profiles
for user_id, profile in PROFILES.items():
    if not user_id.startswith("_"):  # Skip templates
        create_user_app(user_id, profile)
        print(f"[ROUTES] Created /{user_id} for {profile.get('name', user_id)}")

@app.route("/")
def index():
    """List all available profiles"""
    users = [f"<li><a href='/{uid}'>{p.get('display_name', uid)}</a> - {p.get('description', '')}</li>"
             for uid, p in PROFILES.items() if not uid.startswith("_")]
    return f"""
    <html>
    <head><title>Personal AI Assistants</title></head>
    <body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff">
    <h1>Personal AI Assistants</h1>
    <ul>{''.join(users)}</ul>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5560))
    print("=" * 50)
    print("PERSONAL AI ASSISTANT SERVER")
    print(f"http://localhost:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, threaded=True)
