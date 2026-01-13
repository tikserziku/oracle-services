# grok-emilia

Grok Voice EMILIJA Personal AI

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
python app_emilia.py
```

## Systemd Service

```bash
sudo cp grok-emilia.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable grok-emilia
sudo systemctl start grok-emilia
```
