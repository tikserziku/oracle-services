# grok-android

Grok Voice Android PWA

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
python app_android.py
```

## Systemd Service

```bash
sudo cp grok-android.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable grok-android
sudo systemctl start grok-android
```
