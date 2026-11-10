"""Booking rules and storage. No Telegram code here, so it is easy to test."""
import sqlite3
from datetime import date, datetime, timedelta

SERVICES = {"cut": ("Haircut", 20), "beard": ("Beard trim", 12), "combo": ("Haircut + beard", 28)}
SLOTS = [f"{h:02d}:00" for h in range(10, 19)]
DAYS_AHEAD = 7


def connect(path="bookings.db"):
    db = sqlite3.connect(path)
    db.execute(
        """CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, user_name TEXT,
            service TEXT NOT NULL, day TEXT NOT NULL, slot TEXT NOT NULL,
            UNIQUE(day, slot))"""
    )
    return db


def days(now=None):
    today = (now or datetime.now()).date()
    return [(today + timedelta(d)).isoformat() for d in range(DAYS_AHEAD)]


def free_slots(db, day, now=None):
    now = now or datetime.now()
    taken = {s for (s,) in db.execute("SELECT slot FROM bookings WHERE day=?", (day,))}
    past = now.strftime("%H:%M") if day == now.date().isoformat() else ""
    return [s for s in SLOTS if s not in taken and s > past]


def book(db, user_id, user_name, service, day, slot, now=None):
    """Returns True if booked. Button data comes from the user, so everything is re-checked."""
    if service not in SERVICES or day not in days(now) or slot not in free_slots(db, day, now):
        return False
    try:
        with db:
            db.execute(
                "INSERT INTO bookings(user_id, user_name, service, day, slot) VALUES(?,?,?,?,?)",
                (user_id, user_name, service, day, slot),
            )
        return True
    except sqlite3.IntegrityError:  # two people tapped the same slot at once
        return False


def user_bookings(db, user_id, now=None):
    today = (now or datetime.now()).date().isoformat()
    return db.execute(
        "SELECT id, service, day, slot FROM bookings WHERE user_id=? AND day>=? ORDER BY day, slot",
        (user_id, today),
    ).fetchall()


def cancel(db, user_id, booking_id):
    with db:
        return db.execute("DELETE FROM bookings WHERE id=? AND user_id=?", (booking_id, user_id)).rowcount == 1


def day_bookings(db, day):
    return db.execute(
        "SELECT slot, service, user_name FROM bookings WHERE day=? ORDER BY slot", (day,)
    ).fetchall()


def pretty_day(iso):
    return date.fromisoformat(iso).strftime("%a %d %b")
