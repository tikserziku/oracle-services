# grok-admin-api

Grok Admin API Service

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running

```bash
python oracle-admin-api.py
```

## Systemd Service

```bash
sudo cp grok-admin-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable grok-admin-api
sudo systemctl start grok-admin-api
```
