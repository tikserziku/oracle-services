from flask import Flask, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Hub — Services Portal</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0a;
            --bg-secondary: #141414;
            --bg-card: #1a1a1a;
            --bg-card-hover: #222222;
            --text-primary: #fafafa;
            --text-secondary: #a0a0a0;
            --text-muted: #666666;
            --accent: #e07a3c;
            --accent-glow: rgba(224, 122, 60, 0.15);
            --accent-hover: #f08a4c;
            --green: #22c55e;
            --green-glow: rgba(34, 197, 94, 0.2);
            --border: #2a2a2a;
            --border-hover: #3a3a3a;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background-image: 
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }
        header { padding: 80px 0 60px; text-align: center; }
        .logo { display: inline-flex; align-items: center; gap: 12px; margin-bottom: 24px; animation: fadeInDown 0.6s ease-out; }
        .logo-icon {
            width: 48px; height: 48px;
            background: linear-gradient(135deg, var(--accent) 0%, #c46830 100%);
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Source Code Pro', monospace;
            font-weight: 600; font-size: 20px; color: var(--bg-primary);
            box-shadow: 0 0 40px var(--accent-glow);
        }
        .logo-text { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; }
        .logo-text span { color: var(--accent); }
        h1 {
            font-size: 56px; font-weight: 600; letter-spacing: -2px; margin-bottom: 16px;
            background: linear-gradient(180deg, var(--text-primary) 0%, var(--text-secondary) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
            animation: fadeInUp 0.6s ease-out 0.1s both;
        }
        .subtitle { font-size: 18px; color: var(--text-secondary); max-width: 500px; margin: 0 auto; animation: fadeInUp 0.6s ease-out 0.2s both; }
        .status-bar {
            display: inline-flex; align-items: center; gap: 8px;
            background: var(--bg-secondary); border: 1px solid var(--border);
            border-radius: 100px; padding: 8px 16px; margin-top: 32px;
            font-family: 'Source Code Pro', monospace; font-size: 13px;
            animation: fadeInUp 0.6s ease-out 0.3s both;
        }
        .status-dot {
            width: 8px; height: 8px; background: var(--green);
            border-radius: 50%; box-shadow: 0 0 12px var(--green-glow);
            animation: pulse 2s ease-in-out infinite;
        }
        .status-text { color: var(--text-secondary); }
        .status-count { color: var(--green); font-weight: 500; }
        .services-section { padding: 40px 0 100px; }
        .section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 32px; animation: fadeInUp 0.6s ease-out 0.4s both; }
        .section-line { flex: 1; height: 1px; background: linear-gradient(90deg, var(--border) 0%, transparent 100%); }
        .section-title { font-family: 'Source Code Pro', monospace; font-size: 12px; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 2px; }
        .services-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }
        .service-card {
            background: var(--bg-card); border: 1px solid var(--border);
            border-radius: 16px; padding: 28px;
            transition: all 0.3s ease; cursor: pointer;
            position: relative; overflow: hidden;
            animation: fadeInUp 0.6s ease-out both;
            text-decoration: none; display: block;
        }
        .service-card:nth-child(1) { animation-delay: 0.5s; }
        .service-card:nth-child(2) { animation-delay: 0.6s; }
        .service-card:nth-child(3) { animation-delay: 0.7s; }
        .service-card:nth-child(4) { animation-delay: 0.8s; }
        .service-card:nth-child(5) { animation-delay: 0.9s; }
        .service-card::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
            opacity: 0; transition: opacity 0.3s ease;
        }
        .service-card:hover {
            background: var(--bg-card-hover); border-color: var(--border-hover);
            transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        }
        .service-card:hover::before { opacity: 1; }
        .card-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
        .service-icon {
            width: 44px; height: 44px; background: var(--bg-secondary);
            border: 1px solid var(--border); border-radius: 10px;
            display: flex; align-items: center; justify-content: center; font-size: 20px;
        }
        .service-status {
            display: flex; align-items: center; gap: 6px;
            font-family: 'Source Code Pro', monospace; font-size: 11px;
            color: var(--green); background: var(--green-glow);
            padding: 4px 10px; border-radius: 100px;
        }
        .service-status::before {
            content: ''; width: 6px; height: 6px; background: var(--green);
            border-radius: 50%; animation: pulse 2s ease-in-out infinite;
        }
        .service-name { font-family: 'Source Code Pro', monospace; font-size: 18px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
        .service-description { font-size: 14px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.5; }
        .service-meta { display: flex; align-items: center; gap: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
        .meta-item { display: flex; align-items: center; gap: 6px; font-family: 'Source Code Pro', monospace; font-size: 12px; color: var(--text-muted); }
        .meta-item svg { width: 14px; height: 14px; opacity: 0.6; }
        footer { padding: 40px 0; border-top: 1px solid var(--border); text-align: center; }
        .footer-content { display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap; font-family: 'Source Code Pro', monospace; font-size: 13px; color: var(--text-muted); }
        .footer-content a { color: var(--accent); text-decoration: none; transition: color 0.2s ease; }
        .footer-content a:hover { color: var(--accent-hover); }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .terminal-decoration { position: fixed; bottom: 20px; right: 20px; font-family: 'Source Code Pro', monospace; font-size: 11px; color: var(--text-muted); opacity: 0.3; pointer-events: none; }
        @media (max-width: 768px) { h1 { font-size: 36px; } .services-grid { grid-template-columns: 1fr; } header { padding: 60px 0 40px; } }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">M</div>
                <div class="logo-text">MCP<span>Hub</span></div>
            </div>
            <h1>Services Portal</h1>
            <p class="subtitle">Model Context Protocol infrastructure. Voice AI, personal assistants, and automation tools.</p>
            <div class="status-bar">
                <div class="status-dot"></div>
                <span class="status-text">All systems operational</span>
                <span class="status-count">5/5</span>
            </div>
        </header>
        <section class="services-section">
            <div class="section-header">
                <span class="section-title">Active Services</span>
                <div class="section-line"></div>
            </div>
            <div class="services-grid">
                <a class="service-card" href="https://grok-android.visaginas360.com" target="_blank">
                    <div class="card-header">
                        <div class="service-icon">📱</div>
                        <div class="service-status">ONLINE</div>
                    </div>
                    <div class="service-name">grok-android</div>
                    <p class="service-description">Progressive Web App for Android devices. Voice-enabled AI assistant with native-like experience.</p>
                    <div class="service-meta">
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>PWA</div>
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>app_android.py</div>
                    </div>
                </a>
                <a class="service-card" href="https://grok-voice.visaginas360.com" target="_blank">
                    <div class="card-header">
                        <div class="service-icon">🎙️</div>
                        <div class="service-status">ONLINE</div>
                    </div>
                    <div class="service-name">grok-voice</div>
                    <p class="service-description">Real-time voice streaming service. Low-latency speech recognition and synthesis engine.</p>
                    <div class="service-meta">
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>Stream</div>
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>grok_stream.py</div>
                    </div>
                </a>
                <a class="service-card" href="https://grok-emilia.visaginas360.com" target="_blank">
                    <div class="card-header">
                        <div class="service-icon">👩</div>
                        <div class="service-status">ONLINE</div>
                    </div>
                    <div class="service-name">grok-emilia</div>
                    <p class="service-description">Personal AI assistant "Emilija". Customized voice personality with conversational memory.</p>
                    <div class="service-meta">
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>AI Agent</div>
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>app_emilia.py</div>
                    </div>
                </a>
                <a class="service-card" href="https://grok-zigminta.visaginas360.com" target="_blank">
                    <div class="card-header">
                        <div class="service-icon">👨</div>
                        <div class="service-status">ONLINE</div>
                    </div>
                    <div class="service-name">grok-zigminta</div>
                    <p class="service-description">Personal AI assistant "Zigminta". Custom personality for task management and daily planning.</p>
                    <div class="service-meta">
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>AI Agent</div>
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>app_personal.py</div>
                    </div>
                </a>
                <a class="service-card" href="https://grok-admin-api.visaginas360.com" target="_blank">
                    <div class="card-header">
                        <div class="service-icon">⚙️</div>
                        <div class="service-status">ONLINE</div>
                    </div>
                    <div class="service-name">grok-admin-api</div>
                    <p class="service-description">Administration API for service management. Health checks, logs, and deployment controls.</p>
                    <div class="service-meta">
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>REST API</div>
                        <div class="meta-item"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>oracle-admin-api.py</div>
                    </div>
                </a>
            </div>
        </section>
        <footer>
            <div class="footer-content">
                <span>Built with</span>
                <a href="https://github.com/anthropics/anthropic-cookbook" target="_blank">MCP</a>
                <span>• Powered by Oracle VM •</span>
                <span>visaginas360</span>
            </div>
        </footer>
    </div>
    <div class="terminal-decoration">> mcp-hub v1.0.0<br>> oracle-vm:~/services</div>
</body>
</html>'''

@app.route('/')
def index():
    return HTML

@app.route('/health')
def health():
    return {'status': 'ok', 'service': 'mcp-portal'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8090)
