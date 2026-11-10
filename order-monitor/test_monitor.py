from datetime import datetime, timezone

from monitor import new_matches, parse, wanted

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


def test_first_run_drops_old_posts_and_marks_everything_seen():
    seen = set()
    found = new_matches(parse(HTML, "chan"), seen, first_run=True, now=NOW)
    assert [p["id"] for p in found] == ["chan/10"]
    assert seen == {"chan/9", "chan/10", "chan/11"}
    assert new_matches(parse(HTML, "chan"), seen, first_run=False, now=NOW) == []
