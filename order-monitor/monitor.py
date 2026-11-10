"""Watches public Telegram freelance channels and forwards bot/scraper/Python orders to you.

Setup: create a bot with @BotFather, put BOT_TOKEN=<token> into order-monitor/.env,
run `python monitor.py`, then send /start to your bot once.
Without a token: `python monitor.py --dry-run` prints the matches and exits.
"""
import argparse
import html
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).parent
STATE = HERE / "state.json"
POLL_SECONDS = 300
LIVE_SECONDS = 30  # /live mode; one scan of 5 channels already takes ~10 s, so going lower gains nothing
COMMANDS = {"/check", "/live", "/normal"}
FIRST_RUN_MAX_AGE = timedelta(hours=12)
UA = {"User-Agent": "order-monitor/0.1 (personal job alerts)"}

WANT = re.compile("|".join([
    # bots, scrapers, scripts. \bбот keeps "работа" out; the lookbehinds drop call-centre "по скриптам".
    r"\bбот", r"\bbots?\b", r"парс", r"pars", r"scrap", r"python", r"питон", r"(?<!по )(?<!есть )скрипт",
    r"автоматиз", r"\bapi\b", r"интеграц", r"discord", r"дискорд", r"selenium", r"mini ?app",
    # websites. Bare "сайт" is in every SEO/content post, so only "make/build a site" phrases.
    r"(?:созда|разработ|сделать|сверстать|нужен|переделать|доработ)\w*\s+(?:\S+\s+){0,2}сайт",
    r"лендинг", r"landing", r"в[её]рст", r"\bhtml", r"\bcss\b", r"javascript", r"фронтенд", r"frontend",
    r"react", r"wordpress", r"вордпресс",
    # spreadsheets automation
    r"google ?sheets", r"гугл[ -]?таблиц", r"apps ?script", r"макрос", r"\bvba\b",
]), re.I)
SKIP = re.compile("|".join([
    r"казино", r"ставк", r"ставок", r"накрут", r"спам", r"форекс", r"forex", r"\b18\+",
    # vacancies for other roles that only mention automation/API/sites in passing
    r"seo[-‑ ]?специалист", r"smm[-‑ ]?специалист", r"копирайтер", r"веб[-‑ ]?дизайнер", r"таргетолог", r"маркетолог",
]), re.I)


PORTFOLIO = "https://github.com/biokiller59/bots-portfolio"
TAIL = (f"\nОплата 50/50: половина до начала, вторая после видео, где всё работает. "
        f"Отдаю исходный код и инструкцию, 7 дней бесплатных правок.\nПримеры: {PORTFOLIO}")
# First matching topic wins, so the specific ones (Discord, parser) go before the generic "бот".
TOPICS = [
    (r"discord|дискорд", "Здравствуйте! Сделаю Discord-бота. Есть готовый пример — бот тикетов: приватный канал поддержки одной кнопкой.\n"
     "Уточню: 1) какие команды и роли нужны? 2) где бот будет работать — ваш сервер или нужен совет по хостингу?\n"
     "Оценка: 20–40 $, срок 1–3 дня."),
    (r"парс|pars|scrap|selenium|собрать данные|выгруз", "Здравствуйте! Сделаю парсер. Есть готовый пример — сбор каталога (название, цена, наличие, ссылка) в Excel со всех страниц.\n"
     "Уточню: 1) какой сайт и какие поля собирать? 2) нужен разовый сбор или по расписанию?\n"
     "Оценка: 10–30 $, срок 1–2 дня."),
    (r"сайт|лендинг|landing|в[её]рст|html|css|javascript|фронтенд|frontend|react|wordpress|вордпресс",
     "Здравствуйте! Сделаю сайт: лендинг или сайт-визитку, адаптивно под телефон.\n"
     "Уточню: 1) есть макет или пример сайта, который нравится? 2) тексты и фото готовы, нужен ли домен и хостинг?\n"
     "Оценка: 25–60 $, срок 2–4 дня."),
    (r"google ?sheets|гугл[ -]?таблиц|apps ?script|макрос|\bvba\b|excel|эксел",
     "Здравствуйте! Сделаю автоматизацию таблиц (Google Таблицы / Excel): формулы, скрипты, выгрузки, связь с другими сервисами.\n"
     "Уточню: 1) пришлите пример таблицы и что должно происходить автоматически. 2) как часто это нужно запускать?\n"
     "Оценка: 10–30 $, срок 1–2 дня."),
    (r"\bбот|\bbots?\b|mini ?app", "Здравствуйте! Сделаю Telegram-бота. Есть готовый пример — бот записи клиентов: услуга → день → время, "
     "без двойных записей, уведомления владельцу.\n"
     "Уточню: 1) какие функции нужны (меню, заказы, оплата, админка)? 2) где бот будет работать — ваш сервер или нужен совет по хостингу?\n"
     "Оценка: 20–50 $, срок 2–4 дня."),
]
GENERIC = ("Здравствуйте! Сделаю на Python: скрипты, интеграции через API, задачи по расписанию.\n"
           "Уточню: 1) что именно должно происходить и откуда берутся данные? 2) где это будет запускаться?\n"
           "Оценка: от 10 $, срок назову после уточнений.")


def reply_for(text):
    """Ready-to-send reply for an order, picked by topic."""
    body = next((r for pattern, r in TOPICS if re.search(pattern, text, re.I)), GENERIC)
    return body + TAIL


def load_env(path):
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                env[key.strip()] = value.strip()
    return env


def parse(html, channel):
    posts = []
    for msg in BeautifulSoup(html, "html.parser").select(".tgme_widget_message[data-post]"):
        text_el, time_el = msg.select_one(".tgme_widget_message_text"), msg.select_one("time[datetime]")
        if not text_el or not time_el:
            continue
        post_id = msg["data-post"]  # "channel/123"
        posts.append({
            "id": post_id,
            "date": datetime.fromisoformat(time_el["datetime"]),
            # freelance7 appends a "Бот с кучей заказов" ad after this marker to every post
            "text": text_el.get_text("\n").split("Источник сообщения")[0].strip(),
            "link": f"https://t.me/{post_id}",
            "channel": channel,
        })
    return posts


def wanted(text):
    return bool(WANT.search(text)) and not SKIP.search(text)


def fetch(channel):
    r = requests.get(f"https://t.me/s/{channel}", headers=UA, timeout=20)
    r.raise_for_status()
    return parse(r.text, channel)


def new_matches(posts, seen, first_run, now):
    out = []
    for p in posts:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        if first_run and now - p["date"] > FIRST_RUN_MAX_AGE:
            continue
        if wanted(p["text"]):
            out.append(p)
    return out


class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.offset = None

    def call(self, method, **params):
        # long-polling getUpdates holds the request open for params["timeout"] seconds
        r = requests.post(self.base + method, json=params, timeout=30 + params.get("timeout", 0))
        r.raise_for_status()
        return r.json()["result"]

    def find_chat(self):
        for upd in reversed(self.call("getUpdates")):
            msg = upd.get("message")
            if msg and msg.get("text", "").startswith("/start"):
                return msg["chat"]["id"]
        return None

    def wait_for_command(self, chat_id, seconds):
        """Waits up to `seconds`; returns the owner's command (/check, /live, /normal) as soon as one arrives."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            try:
                updates = self.call("getUpdates", offset=self.offset, timeout=max(1, int(min(left, 50))))
            except requests.RequestException as e:
                print(f"getUpdates failed: {e}", file=sys.stderr)
                time.sleep(5)
                continue
            for upd in updates:
                self.offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                cmd = msg.get("text", "").split("@")[0].strip()  # "/check@MyBot" in groups
                if msg.get("chat", {}).get("id") == chat_id and cmd in COMMANDS:
                    return cmd
        return None

    def say(self, chat_id, text):
        try:
            self.call("sendMessage", chat_id=chat_id, text=text)
        except requests.RequestException as e:
            print(f"send failed: {e}", file=sys.stderr)

    def send(self, chat_id, post):
        body = post["text"] if len(post["text"]) < 3500 else post["text"][:3500] + "…"
        self.call("sendMessage", chat_id=chat_id, text=f"{body}\n\n{post['link']}",
                  disable_web_page_preview=True)
        # <pre> gives a one-tap copy button in Telegram
        self.call("sendMessage", chat_id=chat_id, parse_mode="HTML", disable_web_page_preview=True,
                  text=f"Готовый отклик (поправь цену и срок):\n<pre>{html.escape(reply_for(post['text']))}</pre>")


def channels():
    lines = (HERE / "channels.txt").read_text(encoding="utf-8").splitlines()
    return [c.strip() for c in lines if c.strip() and not c.startswith("#")]


def load_state():
    if STATE.exists():
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data.get("chat_id"), set(data.get("seen", []))
    return None, set()


def save_state(chat_id, seen):
    # shortcut: the seen list grows forever (~100 ids/day for 5 channels), trim it if it ever gets large.
    STATE.write_text(json.dumps({"chat_id": chat_id, "seen": sorted(seen)}), encoding="utf-8")


def scan(seen, first_run):
    found = []
    for ch in channels():
        # a channel just added to channels.txt gets the same 12-hour limit as a first run
        fresh = first_run or not any(i.startswith(ch + "/") for i in seen)
        try:
            found += new_matches(fetch(ch), seen, fresh, datetime.now(timezone.utc))
        except requests.RequestException as e:
            print(f"{ch}: {e}", file=sys.stderr)
        time.sleep(2)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print matches from the last 12 hours and exit")
    args = ap.parse_args()

    if args.dry_run:
        for p in scan(set(), first_run=True):
            print(f"--- {p['date']:%d.%m %H:%M} {p['link']}\n{p['text'][:300]}\n>>> {reply_for(p['text'])}\n")
        return

    token = load_env(HERE / ".env").get("BOT_TOKEN")
    if not token:
        sys.exit("Put BOT_TOKEN=<token from @BotFather> into order-monitor/.env")
    tg = Telegram(token)
    chat_id, seen = load_state()
    while not chat_id:
        print("Send /start to your bot in Telegram…")
        chat_id = tg.find_chat()
        if not chat_id:
            time.sleep(5)
    tg.call("setMyCommands", commands=[
        {"command": "check", "description": "Проверить каналы сейчас"},
        {"command": "live", "description": f"Постоянное сканирование (каждые {LIVE_SECONDS} с)"},
        {"command": "normal", "description": "Обычный режим (раз в 5 минут)"},
    ])
    tg.call("sendMessage", chat_id=chat_id, text="Order monitor is running. New matching orders will appear here. "
            "/check — проверить сейчас, /live — постоянное сканирование, /normal — раз в 5 минут.")

    # shortcut: live mode is not saved, a restart goes back to 5 minutes; store it in state.json if that annoys.
    first_run = not seen
    interval, cmd = POLL_SECONDS, None
    while True:
        if cmd == "/live":
            interval = LIVE_SECONDS
            tg.say(chat_id, f"Постоянное сканирование включено: проверяю каждые {LIVE_SECONDS} секунд. /normal — выключить.")
        elif cmd == "/normal":
            interval = POLL_SECONDS
            tg.say(chat_id, "Обычный режим: проверяю раз в 5 минут.")
        manual = cmd == "/check"
        if manual:
            tg.say(chat_id, "Проверяю каналы…")
        found = scan(seen, first_run)
        for post in found:
            try:
                tg.send(chat_id, post)
            except requests.RequestException as e:
                print(f"send failed: {e}", file=sys.stderr)
            time.sleep(1)
        if manual and not found:
            tg.say(chat_id, "Новых подходящих заказов нет.")
        first_run = False
        save_state(chat_id, seen)
        cmd = tg.wait_for_command(chat_id, interval)


if __name__ == "__main__":
    main()
