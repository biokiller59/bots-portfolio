"""Watches public Telegram freelance channels and forwards bot/scraper/Python orders to you.

Setup: create a bot with @BotFather, put BOT_TOKEN=<token> into order-monitor/.env,
run `python monitor.py`, then send /start to your bot once.
Without a token: `python monitor.py --dry-run` prints the matches and exits.
"""
import argparse
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
FIRST_RUN_MAX_AGE = timedelta(hours=12)
UA = {"User-Agent": "order-monitor/0.1 (personal job alerts)"}

# \bбот keeps "работа" out; the lookbehinds drop call-centre "по скриптам" / "есть скрипты".
WANT = re.compile(r"\bбот|\bbots?\b|парс|pars|scrap|python|питон|(?<!по )(?<!есть )скрипт|автоматиз|\bapi\b|discord|дискорд|selenium", re.I)
SKIP = re.compile(r"казино|ставк|ставок|накрут|спам|форекс|forex|\b18\+", re.I)


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

    def call(self, method, **params):
        r = requests.post(self.base + method, json=params, timeout=30)
        r.raise_for_status()
        return r.json()["result"]

    def find_chat(self):
        for upd in reversed(self.call("getUpdates")):
            msg = upd.get("message")
            if msg and msg.get("text", "").startswith("/start"):
                return msg["chat"]["id"]
        return None

    def send(self, chat_id, post):
        body = post["text"] if len(post["text"]) < 3500 else post["text"][:3500] + "…"
        self.call("sendMessage", chat_id=chat_id, text=f"{body}\n\n{post['link']}",
                  disable_web_page_preview=True)


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
        try:
            found += new_matches(fetch(ch), seen, first_run, datetime.now(timezone.utc))
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
            print(f"--- {p['date']:%d.%m %H:%M} {p['link']}\n{p['text'][:300]}\n")
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
    tg.call("sendMessage", chat_id=chat_id, text="Order monitor is running. New matching orders will appear here.")

    first_run = not seen
    while True:
        for post in scan(seen, first_run):
            try:
                tg.send(chat_id, post)
            except requests.RequestException as e:
                print(f"send failed: {e}", file=sys.stderr)
            time.sleep(1)
        first_run = False
        save_state(chat_id, seen)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
