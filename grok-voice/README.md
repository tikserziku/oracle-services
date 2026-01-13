# grok-voice

Grok Voice Stream

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Running

```bash
python grok_stream.py
```

## Systemd Service

```bash
sudo cp grok-voice.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable grok-voice
sudo systemctl start grok-voice
```
