# NyxReportPro

Professional single-window Telegram full-spectrum reporting tool.

**UI-first** — one app for login, proxies, harvest, internal reports, official bots, external email pressure, live log, session auto-save.

## Features
- External `data/api_keys.txt` — hundreds of `api_id:api_hash`, random pick per phone
- External `data/phones.txt` — one number per line (500+)
- Sessions folder auto-updates (`.session` files)
- Proxy channel field → join → fetch → test → save alive → auto-assign sticky per account
- Internal multi-account reports + official bot escalation + SMTP email pressure
- Live log + status + temp cleanup

## Setup (Windows)

```powershell
cd NyxReportPro
python -m venv .venv
.\./.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install aiohttp-socks
python app.py
```

## Data files

### data/api_keys.txt
```
12345678:abcdef0123456789abcdef0123456789
87654321:fedcba9876543210fedcba9876543210
```

### data/phones.txt
```
+2010xxxxxxxx
+905xxxxxxxxx
```

### data/smtp.json (optional)
```json
[{"host":"smtp.gmail.com","port":587,"user":"x@gmail.com","password":"app_pass","from_name":"Desk","use_tls":true}]
```

## UI flow
1. Put keys + phones in data files
2. Open app → Login next phone (code / 2FA) until sessions exist
3. Enter target + optional proxy channels
4. Set posts / emails / reports-per-account
5. Start Campaign
6. Watch live log

Sessions in `sessions/`. Proxies in `proxies/alive_proxies.txt`. Logs in `logs/`.
