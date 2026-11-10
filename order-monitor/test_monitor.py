from datetime import datetime, timezone

from monitor import Telegram, new_matches, parse, reply_for, wanted

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


def test_commands_only_from_owner():
    tg = Telegram("x")
    batches = [[{"update_id": 5, "message": {"chat": {"id": 999}, "text": "/live"}},
                {"update_id": 6, "message": {"chat": {"id": 1}, "text": "hi"}}],
               [{"update_id": 7, "message": {"chat": {"id": 1}, "text": "/live@testbot"}}]]
    tg.call = lambda method, **p: batches.pop(0)
    assert tg.wait_for_command(chat_id=1, seconds=60) == "/live"
    assert tg.offset == 8
