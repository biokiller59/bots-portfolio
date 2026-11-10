# Bots & automation — work samples

Small, finished examples of what I build for clients: Telegram bots, Discord bots and web scrapers in Python.

| Project | What it does | Stack |
|---|---|---|
| [telegram-booking-bot](telegram-booking-bot) | Clients book an appointment in a few taps; the owner gets notified and sees the day's schedule | aiogram 3, SQLite |
| [web-scraper](web-scraper) | Collects a product catalogue (title, price, rating, stock, link) into Excel or CSV | requests, BeautifulSoup, openpyxl |
| [discord-ticket-bot](discord-ticket-bot) | Members open a private support ticket with one button; staff reply and close it | discord.py 2 |
| [order-monitor](order-monitor) | Watches public Telegram channels and forwards posts matching keywords to your Telegram | requests, BeautifulSoup, Bot API |

## Telegram booking bot

- Service → day → free time slot, all with inline buttons
- No double bookings, even if two people tap the same slot at once
- `/my` — view and cancel your bookings
- Owner: instant notification about each booking, `/today` for the day's schedule
- Services, prices and working hours are three lines at the top of `booking.py`

```
set BOT_TOKEN=<token from @BotFather>
set ADMIN_ID=<your Telegram user id>
python telegram-booking-bot/bot.py
```

## Web scraper

- Follows pagination, saves to `.xlsx` or `.csv`
- Polite: delay between requests, clear errors if the site is down
- Demo target is [books.toscrape.com](https://books.toscrape.com), a public sandbox for scraping

```
python web-scraper/scraper.py --pages 3 --out books.xlsx
```

## Discord ticket bot

- `/ticket-panel` (admins only) posts an "Open a ticket" button
- Each ticket is a private channel: the member, the staff role and nobody else
- One open ticket per member; buttons keep working after the bot restarts

```
set DISCORD_TOKEN=<bot token>
python discord-ticket-bot/bot.py
```

## Order monitor

- Channels in `channels.txt`, keywords in two regexes at the top of `monitor.py` (bots, scrapers, scripts, websites and landing pages, spreadsheet automation)
- `/check` in the bot chat runs a check right away
- Checks every 5 minutes, never sends the same post twice, first start only sends posts from the last 12 hours
- Put `BOT_TOKEN=...` in `order-monitor/.env`, run it, send `/start` to your bot

```
python order-monitor/monitor.py --dry-run   # print matches, no token needed
python order-monitor/monitor.py
```

## Setup

```
pip install -r requirements.txt
python -m pytest telegram-booking-bot web-scraper order-monitor
```

## Hire me

I take small and medium tasks: bots, scrapers, API integrations, scheduled scripts.
Typical delivery is 1–3 days, with source code, setup instructions and 7 days of free fixes.
