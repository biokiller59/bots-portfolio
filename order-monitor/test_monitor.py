from datetime import datetime, timezone

from datetime import timedelta

from monitor import Telegram, budget_usd, new_matches, parse, reply_for, top_orders, top_text, wanted

HTML = """
<div class="tgme_widget_message" data-post="chan/10">
  <div class="tgme_widget_message_text">Нужен Telegram-бот для записи клиентов</div>
  <time datetime="2026-11-10T10:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="chan/11">
  <div class="tgme_widget_message_text">Ищем SMM-специалиста, удалённая работа
Источник сообщения — https://t.me/x Бот с кучей заказов</div>
  <time datetime="2026-11-10T11:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="chan/12"><time datetime="2026-11-10T11:00:00+00:00"></time></div>
<div class="tgme_widget_message" data-post="chan/9">
  <div class="tgme_widget_message_text">Парсер сайта в Excel</div>
  <time datetime="2026-11-01T10:00:00+00:00"></time>
</div>
"""
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def test_parse_skips_posts_without_text():
    posts = parse(HTML, "chan")
    assert [p["id"] for p in posts] == ["chan/10", "chan/11", "chan/9"]
    assert posts[0]["link"] == "https://t.me/chan/10"


def test_filter():
    assert wanted("Нужен бот для магазина")
    assert wanted("Write a Python scraper")
    assert not wanted("Удалённая работа менеджером")  # "работа" contains "бот"
    assert not wanted("Бот для ставок на спорт")
    assert not wanted("Обзванивать клиентов по скриптам")
    assert wanted("Нужно сделать сайт-визитку для салона")
    assert wanted("Сверстать лендинг по макету")
    assert not wanted("Ищем SEO-специалиста для продвижения сайта")
    assert not wanted("Ищем копирайтера, знание API плюс")


def test_reply_picks_topic():
    assert "Discord-бота" in reply_for("Нужен бот для Discord сервера")  # Discord beats generic "бот"
    assert "парсер" in reply_for("Спарсить товары с Ozon")
    assert "сайт" in reply_for("Сверстать лендинг")
    assert "Telegram-бота" in reply_for("Нужен бот для записи")
    assert "Python" in reply_for("Интеграция с API CRM")
    assert "github.com" in reply_for("что угодно")


def test_first_run_drops_old_posts_and_marks_everything_seen():
    seen = set()
    found = new_matches(parse(HTML, "chan"), seen, first_run=True, now=NOW)
    assert [p["id"] for p in found] == ["chan/10"]
    assert seen == {"chan/9", "chan/10", "chan/11"}
    assert new_matches(parse(HTML, "chan"), seen, first_run=False, now=NOW) == []


def test_new_channel_only_sends_recent_posts(monkeypatch):
    import monitor
    monkeypatch.setattr(monitor, "channels", lambda: ["chan"])
    posts = parse(HTML, "chan")
    monkeypatch.setattr(monitor, "fetch", lambda ch: posts)
    monkeypatch.setattr(monitor.time, "sleep", lambda s: None)
    monkeypatch.setattr(monitor, "datetime", type("D", (), {"now": staticmethod(lambda tz: NOW)}))
    found = monitor.scan({"other/1"}, first_run=False)
    assert [p["id"] for p in found] == ["chan/10"]  # chan/9 is 9 days old


def test_budget_usd():
    assert round(budget_usd("Бюджет 5000 руб")) == 56
    assert budget_usd("Плачу 50$") == 50
    assert round(budget_usd("до 15к ₽")) == 167
    assert budget_usd("$ 30 за работу") == 30
    assert round(budget_usd("100 eur")) == 110
    assert budget_usd("Нужен бот, цена договорная") == 0


def test_top_orders_ranks_dedupes_and_drops_old():
    def post(i, text, hours_ago):
        return {"id": f"c/{i}", "text": text, "date": NOW - timedelta(hours=hours_ago), "link": f"https://t.me/c/{i}"}
    posts = [
        post(1, "Нужен Telegram-бот, бюджет 10000 руб, пишите @client_one", 3),
        post(2, "Нужен Telegram-бот, бюджет 10000 руб, пишите @client_one", 2),  # repost in another channel
        post(3, "Нужен бот для записи", 1),
        post(4, "Парсер сайта в Excel, 200$", 30),  # older than 24 h
        post(5, "Ищем SMM-специалиста", 1),  # not our topic
    ]
    top = top_orders(posts, NOW)
    assert [p["id"] for p in top] == ["c/1", "c/3"]
    text = top_text(top, NOW)
    assert "~111 $" in text and "https://t.me/c/3" in text
    assert len(top_text(top_orders([post(i, "Нужен бот " + "x" * 500 + str(i), 1) for i in range(30)], NOW), NOW)) < 4096


def test_send_reply_escapes_and_picks_topic():
    tg = Telegram("x")
    sent = []
    tg.call = lambda method, **p: sent.append(p)
    tg.send_reply(1, {"text": "Спарсить <товары> с Ozon"}, "№1 — отклик для https://t.me/c/1:")
    assert sent[0]["parse_mode"] == "HTML" and "<pre>" in sent[0]["text"] and "парсер" in sent[0]["text"]


def test_commands_only_from_owner():
    tg = Telegram("x")
    batches = [[{"update_id": 5, "message": {"chat": {"id": 999}, "text": "/live"}},
                {"update_id": 6, "message": {"chat": {"id": 1}, "text": "hi"}}],
               [{"update_id": 7, "message": {"chat": {"id": 1}, "text": "/live@testbot"}}]]
    tg.call = lambda method, **p: batches.pop(0)
    assert tg.wait_for_command(chat_id=1, seconds=60) == "/live"
    assert tg.offset == 8
