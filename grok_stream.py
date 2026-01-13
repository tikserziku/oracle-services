#!/usr/bin/env python3
import os, json, asyncio, requests, edge_tts, base64, re
from flask import Flask, render_template_string, request, jsonify, Response
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

load_dotenv()
app = Flask(__name__)
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
VOICE = "ru-RU-SvetlanaNeural"
HISTORY_FILE = Path("conversation_history.json")

# Load conversation from file on startup
def load_conversation():
    try:
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            # Convert to API format, keep last 20 messages
            conv = [{"role": m["role"], "content": m["content"]} for m in history[-20:]]
            print(f"[MEMORY] Loaded {len(conv)} messages from history")
            return conv
    except Exception as e:
        print(f"[MEMORY ERR] {e}")
    return []

conversation = load_conversation()

def save_message(role, content):
    """Save message to history file"""
    try:
        history = []
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        })
        # Keep last 500 messages
        if len(history) > 500:
            history = history[-500:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[SAVE ERR] {e}")

def clean_tts(text):
    # Remove markdown and ALL emojis
    text = re.sub(r"[#*`\[\]]", "", text)
    # Remove emojis (unicode ranges for emojis)
    text = re.sub(r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]", "", text)
    return text.strip()

def gen_tts(text):
    async def _g():
        c = edge_tts.Communicate(text, VOICE)
        d = b""
        async for ch in c.stream():
            if ch["type"] == "audio": d += ch["data"]
        return d
    return asyncio.run(_g())

def stream_grok(msgs):
    if not XAI_API_KEY:
        yield "[NO KEY]"
        return
    try:
        request_body = {
            "model": "grok-3-mini-fast",
            "messages": msgs,
            "max_tokens": 800,
            "temperature": 0.7,
            "reasoning_effort": "low",
            "stream": True
        }
        r = requests.post(XAI_API_URL, headers={"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"},
            json=request_body, stream=True, timeout=60)
        print(f"[API] Status: {r.status_code}")
        if r.status_code != 200:
            yield f"[ERR {r.status_code}]"
            return
        for ln in r.iter_lines():
            if ln:
                ln = ln.decode("utf-8")
                if ln.startswith("data: "):
                    d = ln[6:]
                    if d == "[DONE]": break
                    try:
                        cnt = json.loads(d).get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if cnt: yield cnt
                    except: pass
    except Exception as e:
        print(f"[ERROR] {e}")
        yield f"[ERR]"

HTML = """<!DOCTYPE html><html><head><title>Grok Stream</title><meta charset=utf-8>
<style>body{font-family:sans-serif;background:#1a1a2e;color:#fff;padding:20px;display:flex;flex-direction:column;align-items:center}
h1{color:#0df;margin-bottom:5px}
.sub{color:#888;font-size:.85em;margin-bottom:15px}
#st{padding:12px 25px;border-radius:25px;background:rgba(100,100,100,.3);margin:10px;font-size:1.1em}
#st.listen{background:rgba(0,255,136,.2);color:#0f8;border:2px solid #0f8}
#st.stream{background:rgba(0,212,255,.2);color:#0df;border:2px solid #0df}
#st.speak{background:rgba(168,85,247,.2);color:#a8f;border:2px solid #a8f}
#tr{width:600px;background:rgba(255,255,255,.05);border-radius:10px;padding:15px;min-height:200px;max-height:350px;overflow-y:auto}
.m{margin:8px 0;padding:10px;border-radius:8px}.u{background:rgba(0,212,255,.2);text-align:right}.g{background:rgba(0,255,136,.2)}
.ctrl{display:flex;gap:15px;margin:15px 0;align-items:center}
#mic{width:80px;height:80px;border-radius:50%;border:3px solid #0f8;background:rgba(0,255,136,.1);color:#0f8;font-size:2em;cursor:pointer}
#mic.on{border-color:#0f8;background:rgba(0,255,136,.3);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,255,136,.4)}50%{box-shadow:0 0 0 20px rgba(0,255,136,0)}}
.toggle{display:flex;align-items:center;gap:8px;padding:8px 15px;background:rgba(255,255,255,.1);border-radius:20px;cursor:pointer}
.toggle input{width:18px;height:18px}
#db{width:600px;margin-top:10px;padding:8px;background:rgba(255,100,0,.1);border:1px solid #f60;border-radius:8px;font-family:monospace;font-size:.6em;max-height:80px;overflow-y:auto}
.dt{color:#f60;font-weight:bold}.ds{color:#0f8}.de{color:#f44}
</style></head>
<body><h1>Grok Stream</h1>
<div class=sub>Streaming Voice Assistant</div>
<div class=ctrl>
<button id=mic onclick=toggleAuto()>🎤</button>
<label class=toggle><input type=checkbox id=autoChk checked onchange=toggleAuto()> Auto Listen</label>
</div>
<div id=st>Click mic to start</div>
<div id=tr></div>
<div id=q style="margin-top:8px;color:#a8f;font-size:.85em">Queue: 0</div>
<div id=db><div class=dt>LOG</div><div id=lg></div></div>
<audio id=au></audio>
<script>
const st=document.getElementById("st"),tr=document.getElementById("tr"),
q=document.getElementById("q"),au=document.getElementById("au"),lg=document.getElementById("lg"),
mic=document.getElementById("mic"),autoChk=document.getElementById("autoChk");

let audioQueue=[];
let isPlaying=false;
let isProcessing=false;
let autoMode=true;
let listening=false;
let rec=null;
let gm=null;
let userInteracted=false;
let speechBuffer="";
let silenceTimer=null;
let micError=false; // Track if mic had error
let abortController=null; // To cancel previous request
const SILENCE_DELAY=3500; // 3.5 seconds of silence before sending

function log(m,e){
    const d=document.createElement("div");
    d.className=e?"de":"ds";
    d.textContent="["+new Date().toLocaleTimeString()+"] "+m;
    lg.appendChild(d);
    lg.parentElement.scrollTop=9999;
    console.log(m);
}

// Speech Recognition
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR){
    rec=new SR();
    rec.lang="ru-RU";
    rec.continuous=true;
    rec.interimResults=true;

    rec.onstart=()=>{
        listening=true;
        micError=false;
        mic.classList.add("on");
        st.textContent="Listening...";
        st.className="listen";
        log("Listening");
    };

    rec.onresult=(e)=>{
        for(let i=e.resultIndex;i<e.results.length;i++){
            if(e.results[i].isFinal){
                const text=e.results[i][0].transcript;
                // If AI is speaking, interrupt immediately!
                if(isPlaying || isProcessing){
                    interruptAI();
                    log("User interrupted!");
                }
                speechBuffer+=text+" ";
                log("Buffer: "+speechBuffer.length+" chars");
                // Reset silence timer - wait 2.5s before sending
                clearTimeout(silenceTimer);
                silenceTimer=setTimeout(()=>{
                    if(speechBuffer.trim()){
                        log("Sending after silence: "+speechBuffer.length+" chars");
                        const msg=speechBuffer.trim();
                        speechBuffer="";
                        clearTimeout(silenceTimer);
                        stopListen();
                        sendMessage(msg);
                    }
                },SILENCE_DELAY);
            }
        }
    };

    rec.onend=()=>{
        listening=false;
        mic.classList.remove("on");
        // Only restart if NOT playing (avoid feedback loop!)
        if(autoMode && !micError && !isPlaying && !isProcessing){
            setTimeout(startListen,300);
        }
        micError=false;
    };

    rec.onerror=(e)=>{
        if(e.error!="aborted") log("Mic: "+e.error,true);
        micError=true;
        listening=false;
        mic.classList.remove("on");
        // Restart for no-speech errors
        if(autoMode && e.error=="no-speech"){
            setTimeout(startListen,500);
        }
    };
}

function startListen(){
    if(!rec || listening) return;
    // Don't listen while playing - avoid feedback!
    if(isPlaying || isProcessing) return;
    try{ rec.start(); }catch(e){ log("Mic start err",true); }
}

function interruptAI(){
    log("Interrupting AI...");
    audioQueue=[];
    isPlaying=false;
    isProcessing=false;
    au.pause();
    au.currentTime=0;
    st.textContent="Interrupted";
    st.className="";
}

function stopListen(){
    listening=false;
    mic.classList.remove("on");
    clearTimeout(silenceTimer);
    if(rec){ try{ rec.stop(); }catch(e){} }
}

function toggleAuto(){
    userInteracted=true; // User clicked - autoplay now allowed
    autoMode=autoChk.checked;
    log(autoMode?"Auto ON":"Auto OFF");
    if(autoMode && !isProcessing && !isPlaying){
        startListen();
    }else if(!autoMode){
        stopListen();
        speechBuffer="";
        clearTimeout(silenceTimer);
        st.textContent="Auto OFF";
        st.className="";
    }
}

// AUDIO QUEUE - FIXED
function addAudio(base64){
    log("Audio queued ("+Math.round(base64.length/1024)+"KB)");
    audioQueue.push(base64);
    q.textContent="Queue: "+audioQueue.length;
    if(!isPlaying){
        playNext();
    }
}

function playNext(){
    if(audioQueue.length===0){
        isPlaying=false;
        isProcessing=false;
        q.textContent="Queue: 0";
        log("Playback done");
        if(autoMode){
            st.textContent="Listening...";
            st.className="listen";
            setTimeout(startListen,500);
        }else{
            st.textContent="Ready";
            st.className="";
        }
        return;
    }

    isPlaying=true;
    stopListen(); // Stop mic while speaking to avoid feedback!
    st.textContent="Speaking...";
    st.className="speak";

    const audioData=audioQueue.shift();
    q.textContent="Queue: "+audioQueue.length;

    log("Playing audio...");
    au.src="data:audio/mp3;base64,"+audioData;

    au.onended=function(){
        log("Audio ended");
        playNext();
    };

    au.onerror=function(e){
        log("Audio error: "+e.type,true);
        playNext();
    };

    au.play().then(()=>{
        log("Audio started");
    }).catch((e)=>{
        log("Play failed: "+e.message,true);
        playNext();
    });
}

function addM(role,text){
    const d=document.createElement("div");
    d.className="m "+(role=="user"?"u":"g");
    d.innerHTML="<small>"+(role=="user"?"You":"Grok")+"</small><div class=c>"+text+"</div>";
    tr.appendChild(d);
    tr.scrollTop=9999;
    return d;
}

async function sendMessage(text){
    if(!text) return;

    // Cancel previous request if any
    if(abortController){
        log("Canceling previous request");
        abortController.abort();
    }
    abortController=new AbortController();

    stopListen();
    audioQueue=[];
    isPlaying=false;
    isProcessing=true;
    au.pause();
    au.currentTime=0;

    log("Send: "+text);
    addM("user",text);
    gm=addM("grok","...");

    st.textContent="Streaming...";
    st.className="stream";

    try{
        const response=await fetch("/chat-stream",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text}),
            signal:abortController.signal
        });

        log("HTTP "+response.status);
        if(!response.ok){
            st.textContent="Error";
            isProcessing=false;
            if(autoMode) setTimeout(startListen,1000);
            return;
        }

        const reader=response.body.getReader();
        const decoder=new TextDecoder();
        let fullText="";
        let sseBuffer="";

        while(true){
            const{done,value}=await reader.read();
            if(done) break;

            sseBuffer+=decoder.decode(value,{stream:true});
            const parts=sseBuffer.split(/\\r?\\n/);
            sseBuffer=parts.pop()||"";

            for(const line of parts){
                if(line.startsWith("data: ")){
                    const data=line.slice(6).trim();
                    if(data=="[DONE]"||!data) continue;

                    try{
                        const parsed=JSON.parse(data);
                        if(parsed.type=="text"&&parsed.content){
                            fullText+=parsed.content;
                            gm.querySelector(".c").textContent=fullText;
                        }
                        if(parsed.type=="audio"&&parsed.audio){
                            addAudio(parsed.audio);
                        }
                    }catch(e){log("JSON err",true);}
                }
            }
        }

        log("Stream done, text: "+fullText.length+" chars");

    }catch(e){
        if(e.name==="AbortError"){
            log("Request canceled");
            return; // Don't reset state - new request is taking over
        }
        log("Fetch error: "+e.message,true);
        isProcessing=false;
        if(autoMode) setTimeout(startListen,1000);
    }

    // If no audio was queued, reset state
    if(audioQueue.length===0 && !isPlaying){
        isProcessing=false;
        if(autoMode){
            st.textContent="Listening...";
            st.className="listen";
            setTimeout(startListen,500);
        }
    }
}

// Start - require user click first for Chrome autoplay policy
log("Ready! Click mic to start");
st.textContent="Click mic to start";
// Don't auto-start - wait for user interaction
</script></body></html>"""

@app.route("/")
def idx(): return render_template_string(HTML)

@app.route("/chat-stream", methods=["POST"])
def chat():
    global conversation
    msg = request.json.get("message", "")
    print(f"[CHAT] {msg}")
    if not msg: return jsonify({"error": "empty"})

    # Save user message
    save_message("user", msg)
    conversation.append({"role": "user", "content": msg})
    if len(conversation) > 20: conversation = conversation[-20:]

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_prompt = f"""You are Grok, a smart voice assistant with MEMORY.
Current date and time: {today}

IMPORTANT: You HAVE conversation memory! The previous messages in this chat are your memory.
If user asks about previous topics - refer to the chat history, you remember everything!

STRICT RULES:
- NEVER use emojis - this is voice output!
- Always respond in Russian
- NEVER say "I don't have memory" - you DO have memory from this conversation!
- ADAPT response length to question complexity:
  * Simple (time, weather, yes/no, greetings) = 1 short sentence
  * Medium (facts, definitions, prices) = 2-3 sentences
  * Complex (analysis, how-to, explanations) = 4-5 sentences
- Don't over-explain simple things!
- Be concise, friendly and natural"""

    msgs = [{"role": "system", "content": system_prompt}] + conversation
    def gen():
        full, buf = "", ""
        for tok in stream_grok(msgs):
            full += tok
            buf += tok
            yield f'data: {json.dumps({"type": "text", "content": tok})}\n\n'
            # Split ONLY at sentence endings or comma - never mid-word!
            if re.search(r"[.!?,:;]\s*$", buf) and len(buf) > 20:
                s = clean_tts(buf)
                if s:
                    print(f"[TTS] {s[:50]}")
                    try:
                        ad = gen_tts(s)
                        yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                    except Exception as e: print(f"[TTS ERR] {e}")
                buf = ""
        if buf:
            s = clean_tts(buf)
            if s:
                try:
                    ad = gen_tts(s)
                    yield f'data: {json.dumps({"type": "audio", "audio": base64.b64encode(ad).decode()})}\n\n'
                except: pass
        # Save assistant response
        save_message("assistant", full)
        conversation.append({"role": "assistant", "content": full})
        yield "data: [DONE]\n\n"
    return Response(gen(), mimetype="text/event-stream")

if __name__ == "__main__":
    print("="*40)
    print("GROK STREAM")
    print("http://localhost:5556")
    print("="*40)
    app.run(host="0.0.0.0", port=5556, threaded=True)
