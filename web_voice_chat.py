#!/usr/bin/env python3
"""
Grok Voice Chat - Auto VAD with Wave Visualization + Session Memory
Open http://localhost:5555 in browser
"""

import os
import json
import base64
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_sock import Sock
from dotenv import load_dotenv
import websocket

load_dotenv()

app = Flask(__name__)
sock = Sock(app)

XAI_API_KEY = os.getenv("XAI_API_KEY")
GROK_WS_URL = "wss://api.x.ai/v1/realtime"
SESSIONS_FILE = "chat_sessions.json"

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sessions": []}

def save_sessions(data):
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_session_context(session_id):
    data = load_sessions()
    for session in data["sessions"]:
        if session["id"] == session_id:
            return session
    return None

def create_new_session():
    data = load_sessions()
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_session = {
        "id": session_id,
        "created": datetime.now().isoformat(),
        "name": f"Chat {len(data['sessions']) + 1}",
        "messages": [],
        "summary": ""
    }
    data["sessions"].append(new_session)
    save_sessions(data)
    return new_session

def add_message_to_session(session_id, role, text):
    data = load_sessions()
    for session in data["sessions"]:
        if session["id"] == session_id:
            session["messages"].append({
                "role": role,
                "text": text,
                "time": datetime.now().isoformat()
            })
            if len(session["messages"]) > 50:
                session["messages"] = session["messages"][-50:]
            if len(session["messages"]) >= 3:
                last_msgs = session["messages"][-5:]
                session["summary"] = " | ".join([m["text"][:30] for m in last_msgs])
            save_sessions(data)
            return

def build_context_instructions(session_id):
    session = get_session_context(session_id)
    if not session or not session["messages"]:
        return "You are a helpful voice assistant. Always respond in Russian (русский язык). Be concise and natural. Отвечай коротко и по делу."

    history = []
    for msg in session["messages"][-10:]:
        role = "User" if msg["role"] == "user" else "You"
        history.append(f"{role}: {msg['text']}")

    history_text = "\n".join(history)

    return f"""You are a helpful voice assistant. Always respond in Russian (русский язык). Be concise and natural.

IMPORTANT: This is a continuing conversation. Here is the recent history:
{history_text}

Continue this conversation naturally. Remember what was discussed. Отвечай коротко и по делу."""


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Grok Voice</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 100%);
            min-height: 100vh;
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 15px;
        }

        h1 {
            font-size: 1.8em;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status {
            font-size: 1em;
            margin-bottom: 15px;
        }
        .status.listening { color: #00ff88; }
        .status.speaking { color: #00d4ff; }
        .status.connecting { color: #ffaa00; }
        .status.error { color: #ff4444; }

        /* Start button for mobile */
        .start-btn {
            padding: 15px 40px;
            font-size: 1.2em;
            border: none;
            border-radius: 30px;
            background: linear-gradient(135deg, #00d4ff, #00ff88);
            color: #000;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 20px;
            display: none;
        }
        .start-btn.show { display: block; }
        .start-btn:active {
            transform: scale(0.95);
        }

        .controls {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }

        .ctrl-btn {
            padding: 8px 15px;
            border: 2px solid #00d4ff;
            background: transparent;
            color: #00d4ff;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .ctrl-btn:active {
            background: rgba(0, 212, 255, 0.3);
        }
        .ctrl-btn.new-chat {
            border-color: #00ff88;
            color: #00ff88;
        }

        .voice-select select {
            padding: 8px 15px;
            font-size: 0.85em;
            border-radius: 20px;
            border: 2px solid #00d4ff;
            background: #1a1a3e;
            color: white;
        }

        .wave-container {
            width: 100%;
            max-width: 500px;
            height: 120px;
            background: rgba(0,0,0,0.3);
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 15px;
        }
        .wave-container.active {
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
        }
        .wave-container.grok-speaking {
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.5);
        }

        #waveCanvas {
            width: 100%;
            height: 100%;
        }

        .transcript {
            width: 100%;
            max-width: 500px;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 12px;
            min-height: 120px;
            max-height: 200px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        .message {
            margin: 6px 0;
            padding: 8px 12px;
            border-radius: 10px;
            font-size: 0.9em;
        }
        .user {
            background: rgba(0, 212, 255, 0.2);
            text-align: right;
            margin-left: 15%;
        }
        .grok {
            background: rgba(0, 255, 136, 0.2);
            margin-right: 15%;
        }
        .label {
            font-size: 0.65em;
            opacity: 0.6;
            margin-bottom: 3px;
            text-transform: uppercase;
        }

        /* Debug panel */
        .debug-panel {
            width: 100%;
            max-width: 500px;
            background: rgba(0,0,0,0.5);
            border-radius: 12px;
            padding: 10px;
            font-family: monospace;
            font-size: 0.75em;
        }
        .debug-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }
        .debug-header span {
            color: #ff8800;
            font-weight: bold;
        }
        .debug-clear {
            padding: 3px 8px;
            font-size: 0.8em;
            background: rgba(255,0,0,0.3);
            border: none;
            color: white;
            border-radius: 5px;
            cursor: pointer;
        }
        .debug-log {
            max-height: 150px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 2px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .log-entry.error { color: #ff4444; }
        .log-entry.success { color: #00ff88; }
        .log-entry.info { color: #00d4ff; }
        .log-entry.warn { color: #ffaa00; }

        .session-info {
            font-size: 0.8em;
            opacity: 0.5;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <h1>Grok Voice</h1>
    <div id="status" class="status connecting">Initializing...</div>

    <button id="startBtn" class="start-btn show" onclick="initAudio()">TAP TO START</button>

    <div class="controls" id="controls" style="display:none;">
        <button class="ctrl-btn new-chat" onclick="startNewChat()">+ New</button>
        <button class="ctrl-btn" onclick="showSessions()">History</button>
        <div class="voice-select">
            <select id="voiceSelect">
                <option value="Ara">Ara</option>
                <option value="Rex">Rex</option>
                <option value="Sal">Sal</option>
                <option value="Eve">Eve</option>
                <option value="Leo">Leo</option>
            </select>
        </div>
    </div>

    <div id="sessionInfo" class="session-info"></div>

    <div class="wave-container" id="waveContainer">
        <canvas id="waveCanvas"></canvas>
    </div>

    <div class="transcript" id="transcript"></div>

    <!-- Debug Panel -->
    <div class="debug-panel">
        <div class="debug-header">
            <span>DEBUG LOG</span>
            <button class="debug-clear" onclick="clearLog()">Clear</button>
        </div>
        <div class="debug-log" id="debugLog"></div>
    </div>

    <script>
        const statusEl = document.getElementById('status');
        const startBtn = document.getElementById('startBtn');
        const controlsEl = document.getElementById('controls');
        const voiceSelect = document.getElementById('voiceSelect');
        const transcriptEl = document.getElementById('transcript');
        const waveContainer = document.getElementById('waveContainer');
        const sessionInfoEl = document.getElementById('sessionInfo');
        const canvas = document.getElementById('waveCanvas');
        const ctx = canvas.getContext('2d');
        const debugLog = document.getElementById('debugLog');

        let ws = null;
        let audioContext = null;
        let analyser = null;
        let mediaStream = null;
        let isGrokSpeaking = false;
        let animationId = null;
        let reconnectAttempts = 0;
        let currentSessionId = null;
        let audioQueue = [];
        let isPlaying = false;

        // Debug logging
        function log(msg, type = 'info') {
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.textContent = `[${time}] ${msg}`;
            debugLog.appendChild(entry);
            debugLog.scrollTop = debugLog.scrollHeight;
            console.log(`[${type}] ${msg}`);
        }

        function clearLog() {
            debugLog.innerHTML = '';
        }

        // Initial checks
        log('Page loaded', 'info');
        log('Protocol: ' + location.protocol, 'info');
        log('UserAgent: ' + navigator.userAgent.substring(0, 50) + '...', 'info');

        if (!navigator.mediaDevices) {
            log('mediaDevices: NOT AVAILABLE', 'error');
            if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
                log('HTTPS required for microphone!', 'error');
            }
        } else {
            log('mediaDevices: Available', 'success');
        }

        // Resize canvas
        function resizeCanvas() {
            canvas.width = canvas.offsetWidth * 2;
            canvas.height = canvas.offsetHeight * 2;
        }
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        // Draw wave
        function drawWave() {
            const bufferLength = analyser ? analyser.frequencyBinCount : 128;
            const dataArray = new Uint8Array(bufferLength);
            if (analyser) analyser.getByteTimeDomainData(dataArray);

            ctx.fillStyle = 'rgba(10, 10, 26, 0.3)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
            if (isGrokSpeaking) {
                gradient.addColorStop(0, '#00ff88');
                gradient.addColorStop(1, '#00ffcc');
            } else {
                gradient.addColorStop(0, '#00d4ff');
                gradient.addColorStop(1, '#00aaff');
            }

            ctx.lineWidth = 3;
            ctx.strokeStyle = gradient;
            ctx.beginPath();

            const sliceWidth = canvas.width / bufferLength;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const v = (analyser ? dataArray[i] : 128) / 128.0;
                const y = (v * canvas.height) / 2;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
                x += sliceWidth;
            }

            ctx.lineTo(canvas.width, canvas.height / 2);
            ctx.stroke();
            animationId = requestAnimationFrame(drawWave);
        }

        function arrayBufferToBase64(buffer) {
            let binary = '';
            const bytes = new Uint8Array(buffer);
            const chunkSize = 8192;
            for (let i = 0; i < bytes.length; i += chunkSize) {
                const chunk = bytes.subarray(i, i + chunkSize);
                binary += String.fromCharCode.apply(null, chunk);
            }
            return btoa(binary);
        }

        // Initialize audio (must be triggered by user interaction on mobile)
        async function initAudio() {
            log('initAudio() called', 'info');
            startBtn.textContent = 'Starting...';
            startBtn.disabled = true;

            try {
                // Check for mediaDevices
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error('getUserMedia not supported. Need HTTPS!');
                }
                log('getUserMedia available', 'success');

                // Request microphone
                log('Requesting microphone...', 'info');
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });
                log('Microphone access granted!', 'success');

                // Create AudioContext
                log('Creating AudioContext...', 'info');
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                audioContext = new AudioContextClass();
                log('AudioContext created, sampleRate: ' + audioContext.sampleRate, 'success');

                // Resume if suspended (required on mobile)
                if (audioContext.state === 'suspended') {
                    log('Resuming suspended AudioContext...', 'warn');
                    await audioContext.resume();
                    log('AudioContext resumed', 'success');
                }

                // Setup audio processing
                const source = audioContext.createMediaStreamSource(mediaStream);
                analyser = audioContext.createAnalyser();
                analyser.fftSize = 2048;
                source.connect(analyser);

                // Create processor for sending audio
                const processor = audioContext.createScriptProcessor(4096, 1, 1);
                let chunkCount = 0;

                processor.onaudioprocess = (e) => {
                    if (isGrokSpeaking || !ws || ws.readyState !== WebSocket.OPEN) return;

                    const float32 = e.inputBuffer.getChannelData(0);
                    const int16 = new Int16Array(float32.length);

                    for (let i = 0; i < float32.length; i++) {
                        int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
                    }

                    const base64 = arrayBufferToBase64(int16.buffer);
                    ws.send(JSON.stringify({type: 'audio', audio: base64}));
                    chunkCount++;
                    if (chunkCount % 25 === 0) {
                        log('Audio chunks sent: ' + chunkCount, 'info');
                    }
                };

                source.connect(processor);
                processor.connect(audioContext.destination);

                // Hide start button, show controls
                startBtn.classList.remove('show');
                controlsEl.style.display = 'flex';

                // Start visualization
                drawWave();
                log('Visualization started', 'success');

                // Start new chat
                await startNewChat();

            } catch (e) {
                log('ERROR: ' + e.message, 'error');
                statusEl.textContent = 'Error: ' + e.message;
                statusEl.className = 'status error';
                startBtn.textContent = 'TAP TO RETRY';
                startBtn.disabled = false;
            }
        }

        // Session management
        async function loadSessions() {
            const resp = await fetch('/api/sessions');
            return await resp.json();
        }

        async function startNewChat() {
            log('Starting new chat...', 'info');
            const resp = await fetch('/api/sessions/new', {method: 'POST'});
            const session = await resp.json();
            currentSessionId = session.id;
            sessionInfoEl.textContent = 'Session: ' + session.name;
            transcriptEl.innerHTML = '';
            reconnect();
        }

        async function continueSession(sessionId) {
            currentSessionId = sessionId;
            const sessions = await loadSessions();
            const session = sessions.sessions.find(s => s.id === sessionId);
            if (session) {
                sessionInfoEl.textContent = 'Session: ' + session.name;
                transcriptEl.innerHTML = '';
                session.messages.slice(-10).forEach(msg => {
                    addMessage(msg.role, msg.text, true);
                });
            }
            hideModal();
            reconnect();
        }

        function showSessions() {
            log('showSessions() - not implemented in mobile version', 'warn');
            alert('History feature - use desktop version');
        }

        function hideModal() {}

        function reconnect() {
            if (ws) ws.close();
            connect();
        }

        function connect() {
            const sessionParam = currentSessionId ? '?session=' + currentSessionId : '';
            // Auto-detect protocol: wss:// for HTTPS, ws:// for HTTP
            const wsProtocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = wsProtocol + location.host + '/ws' + sessionParam;
            log('Connecting to: ' + wsUrl, 'info');

            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                log('WebSocket connected!', 'success');
                // Don't reset reconnectAttempts here - wait for session_id
                ws.send(JSON.stringify({type: 'set_voice', voice: voiceSelect.value}));
                statusEl.textContent = 'Connecting to Grok...';
                statusEl.className = 'status connecting';
            };

            ws.onmessage = async (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'audio') {
                    playAudio(data.audio);
                } else if (data.type === 'user_transcript') {
                    addMessage('user', data.text);
                    log('User: ' + data.text.substring(0, 30) + '...', 'info');
                } else if (data.type === 'grok_transcript') {
                    addMessage('grok', data.text);
                    log('Grok: ' + data.text.substring(0, 30) + '...', 'success');
                } else if (data.type === 'speaking') {
                    isGrokSpeaking = true;
                    waveContainer.classList.add('grok-speaking');
                    waveContainer.classList.remove('active');
                    statusEl.textContent = 'Grok speaking...';
                    statusEl.className = 'status speaking';
                } else if (data.type === 'speech_started') {
                    statusEl.textContent = 'Hearing you...';
                    log('Speech detected', 'info');
                } else if (data.type === 'session_id') {
                    currentSessionId = data.id;
                    sessionInfoEl.textContent = 'Session: ' + data.name;
                    reconnectAttempts = 0;  // Reset only after Grok connected successfully
                    statusEl.textContent = 'Listening...';
                    statusEl.className = 'status listening';
                    waveContainer.classList.add('active');
                    log('Grok ready! Session: ' + data.name, 'success');
                } else if (data.type === 'error') {
                    log('Server error: ' + data.message, 'error');
                    statusEl.textContent = 'Error - see log';
                    statusEl.className = 'status error';
                }
            };

            ws.onclose = () => {
                reconnectAttempts++;
                if (reconnectAttempts > 5) {
                    log('Too many reconnect attempts. Please refresh the page manually.', 'error');
                    statusEl.textContent = 'Connection failed - refresh page';
                    statusEl.className = 'status error';
                    return;
                }
                const delay = Math.min(2000 * Math.pow(2, reconnectAttempts - 1), 30000);
                log('WebSocket closed, reconnecting in ' + (delay/1000) + 's... (attempt ' + reconnectAttempts + '/5)', 'warn');
                statusEl.textContent = 'Reconnecting...';
                statusEl.className = 'status connecting';
                setTimeout(connect, delay);
            };

            ws.onerror = (e) => {
                log('WebSocket error', 'error');
            };
        }

        async function playAudio(base64Audio) {
            audioQueue.push(base64Audio);
            if (!isPlaying) processAudioQueue();
        }

        async function processAudioQueue() {
            if (audioQueue.length === 0) {
                isPlaying = false;
                isGrokSpeaking = false;
                waveContainer.classList.remove('grok-speaking');
                waveContainer.classList.add('active');
                statusEl.textContent = 'Listening...';
                statusEl.className = 'status listening';
                return;
            }

            isPlaying = true;
            const base64Audio = audioQueue.shift();

            try {
                if (!audioContext) {
                    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                    audioContext = new AudioContextClass();
                }

                const audioData = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0));
                const int16Array = new Int16Array(audioData.buffer);
                const float32Array = new Float32Array(int16Array.length);

                for (let i = 0; i < int16Array.length; i++) {
                    float32Array[i] = int16Array[i] / 32768.0;
                }

                const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
                audioBuffer.getChannelData(0).set(float32Array);

                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;

                if (analyser) {
                    source.connect(analyser);
                    analyser.connect(audioContext.destination);
                } else {
                    source.connect(audioContext.destination);
                }

                source.onended = () => processAudioQueue();
                source.start();
            } catch (e) {
                log('Audio playback error: ' + e.message, 'error');
                processAudioQueue();
            }
        }

        function addMessage(role, text, isHistory = false) {
            const div = document.createElement('div');
            div.className = 'message ' + role + (isHistory ? ' history-msg' : '');
            div.innerHTML = '<div class="label">' + (role === 'user' ? 'You' : 'Grok') + '</div>' + text;
            transcriptEl.appendChild(div);
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        voiceSelect.onchange = () => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'set_voice', voice: voiceSelect.value}));
                log('Voice changed to: ' + voiceSelect.value, 'info');
            }
        };

        // Start visualization immediately (without audio)
        drawWave();
        log('Ready - tap START button', 'success');
    </script>
</body>
</html>
"""

class GrokSession:
    def __init__(self, voice="Ara", instructions=None):
        self.voice = voice
        self.ws = None
        self.instructions = instructions or "You are a helpful voice assistant. Always respond in Russian (русский язык). Be concise and natural. Отвечай коротко и по делу."

    def connect(self):
        self.ws = websocket.create_connection(
            GROK_WS_URL,
            header={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json"
            }
        )

        config = {
            "type": "session.update",
            "session": {
                "instructions": self.instructions,
                "voice": self.voice,
                "turn_detection": {"type": "server_vad"},
                "input_audio_transcription": {"model": "whisper-1"},
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": 24000}},
                    "output": {"format": {"type": "audio/pcm", "rate": 24000}}
                }
            }
        }
        self.ws.send(json.dumps(config))

        while True:
            data = json.loads(self.ws.recv())
            if data.get("type") == "session.updated":
                break

        print(f"Grok session ready with voice: {self.voice}")

    def send_audio(self, audio_b64):
        if self.ws:
            self.ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))

    def recv(self):
        if self.ws:
            return json.loads(self.ws.recv())
        return None

    def close(self):
        if self.ws:
            self.ws.close()


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/sessions')
def get_sessions():
    return jsonify(load_sessions())


@app.route('/api/sessions/new', methods=['POST'])
def new_session():
    session = create_new_session()
    return jsonify(session)


@sock.route('/ws')
def websocket_handler(ws):
    print(f"[WS] New WebSocket connection from {request.remote_addr}", flush=True)
    session = None
    voice = "Ara"
    chat_session_id = request.args.get('session')
    print(f"[WS] Session ID: {chat_session_id}", flush=True)

    if not chat_session_id:
        chat_session = create_new_session()
        chat_session_id = chat_session["id"]
        print(f"[WS] Created new session: {chat_session_id}", flush=True)

    try:
        instructions = build_context_instructions(chat_session_id)
        print(f"[WS] Connecting to Grok...", flush=True)
        session = GrokSession(voice, instructions)
        try:
            session.connect()
        except Exception as conn_error:
            error_str = str(conn_error)
            if "429" in error_str:
                print(f"[WS] Rate limit hit! Sending error to client.", flush=True)
                ws.send(json.dumps({
                    "type": "error",
                    "message": "Rate limit exceeded. Please wait 2-3 minutes and try again."
                }))
                return
            raise
        print(f"[WS] Connected to Grok successfully!", flush=True)

        chat_data = get_session_context(chat_session_id)
        ws.send(json.dumps({
            "type": "session_id",
            "id": chat_session_id,
            "name": chat_data["name"] if chat_data else "New Chat"
        }))

        import threading
        current_grok_response = []

        def receive_from_grok():
            nonlocal current_grok_response
            try:
                while True:
                    resp = session.recv()
                    if not resp:
                        break

                    msg_type = resp.get("type")

                    if msg_type == "input_audio_buffer.speech_started":
                        ws.send(json.dumps({"type": "speech_started"}))
                        current_grok_response = []

                    elif msg_type == "conversation.item.input_audio_transcription.completed":
                        user_text = resp.get("transcript", "")
                        if user_text:
                            ws.send(json.dumps({"type": "user_transcript", "text": user_text}))
                            add_message_to_session(chat_session_id, "user", user_text)

                    elif msg_type == "response.output_audio_transcript.delta":
                        delta = resp.get("delta", "")
                        if delta:
                            current_grok_response.append(delta)

                    elif msg_type == "response.output_audio.delta":
                        ws.send(json.dumps({"type": "speaking"}))
                        audio = resp.get("delta", "")
                        if audio:
                            ws.send(json.dumps({"type": "audio", "audio": audio}))

                    elif msg_type == "response.done":
                        full_response = "".join(current_grok_response)
                        if full_response:
                            ws.send(json.dumps({"type": "grok_transcript", "text": full_response}))
                            add_message_to_session(chat_session_id, "grok", full_response)
                        current_grok_response = []
                        ws.send(json.dumps({"type": "done"}))

                    elif msg_type == "error":
                        error_msg = resp.get("error", {}).get("message", "Unknown error")
                        ws.send(json.dumps({"type": "error", "message": error_msg}))

            except Exception as e:
                print(f"Receive error: {e}")

        recv_thread = threading.Thread(target=receive_from_grok, daemon=True)
        recv_thread.start()

        while True:
            message = ws.receive()
            if not message:
                break

            data = json.loads(message)

            if data['type'] == 'set_voice':
                voice = data['voice']
                if session:
                    session.close()
                instructions = build_context_instructions(chat_session_id)
                session = GrokSession(voice, instructions)
                session.connect()
                recv_thread = threading.Thread(target=receive_from_grok, daemon=True)
                recv_thread.start()

            elif data['type'] == 'audio':
                session.send_audio(data['audio'])

    except Exception as e:
        import traceback
        print(f"[WS] WebSocket error: {e}", flush=True)
        print(f"[WS] Traceback: {traceback.format_exc()}", flush=True)
    finally:
        print(f"[WS] Connection closing", flush=True)
        if session:
            session.close()


if __name__ == '__main__':
    print("="*50)
    print("GROK VOICE CHAT - WITH DEBUG")
    print("="*50)
    print()
    print("Open: http://localhost:5555")
    print()
    print("Press Ctrl+C to stop")
    print("="*50)

    app.run(host='0.0.0.0', port=5555, debug=False, threaded=True)
