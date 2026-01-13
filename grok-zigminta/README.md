# grok-zigminta

Grok Voice ZIGMINTA Personal AI

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
python app_personal.py
```

## Systemd Service

```bash
sudo cp grok-zigminta.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable grok-zigminta
sudo systemctl start grok-zigminta
```
