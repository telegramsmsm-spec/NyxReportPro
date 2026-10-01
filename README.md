# NyxReportPro

Multi-account Telegram tool for **legitimate reporting of public abusive content**.

Given N real Telegram accounts + one public target channel, the tool:

1. Scrapes live free proxies from real public proxy channels  
2. Assigns one unique alive proxy per account  
3. Creates / loads isolated Telethon sessions  
4. Health-checks every account  
5. Pulls recent public posts (text, photos, logos, links, etc.)  
6. Marks them as evidence  
7. Generates a unique natural-language report message per account  
8. Executes official client-API reports (`messages.report` / `reportPeer`)  
9. Sends unique DMs to official `@notoscam`  
10. Sends real Gmail (app-password) emails to `abuse@telegram.org`, `dmca@telegram.org`, `spam@telegram.org`  
11. Logs everything into SQLite  

All of the above runs automatically after one **Run Full Cycle** click.

## Requirements

- Python 3.11+
- Telegram API credentials (api_id / api_hash) from https://my.telegram.org
- Gmail account with App Password (2FA required)

## Install

```bash
cd NyxReportPro
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config.example.json config.json
# edit config.json with your SMTP details
python main.py
```

## First-run steps

1. Open **Accounts** tab → enter phone, api_id, api_hash → Add Account  
2. Authorize the session the normal Telethon way (code via Telegram app) the first time  
3. **Proxies** tab → Refresh Proxies from Channels (needs at least one authorized account)  
4. **Targets** tab → paste `@channel` or `t.me/channel` → Fetch Posts  
5. **Evidence** tab → Mark All Current as Evidence  
6. **Email** tab → enter Gmail + App Password → Save SMTP  
7. **Queue** tab → choose reason → **Run Full Cycle**

## How proxy scrape works

The tool reads the last ~100 messages from hard-coded public channels that publish free MTProto / SOCKS5 proxies (`@ProxyMTProto`, `@proxyag`, etc.).  
It parses, deduplicates, tests connectivity (8 s timeout), stores alive proxies, and assigns one unique proxy to every account that does not yet have one.

## Full Cycle sequence

1. Refresh proxies + assign unique  
2. Health-check all accounts  
3. Fetch public posts from target  
4. Auto-mark evidence  
5. Generate unique message text per account  
6. Rate-limited official API report + @notoscam DM from every online account  
7. Send abuse emails with evidence links  
8. Write complete audit to SQLite + show summary  

## Safety

- Official Telegram rate limits only  
- FLOOD_WAIT handled with backoff  
- One unique proxy + one unique message wording per account  
- No mass DMs outside official report bots  
- No account generators or flood bypass  
- Secrets encrypted at rest (Fernet)

## License

Private tool for legitimate moderation reporting only.
