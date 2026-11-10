from datetime import datetime

import booking

NOW = datetime(2026, 11, 10, 14, 30)


def test_booking_flow():
    db = booking.connect(":memory:")
    today, tomorrow = booking.days(NOW)[:2]

    assert booking.free_slots(db, today, NOW)[0] == "15:00"  # past hours are hidden
    assert booking.book(db, 1, "Ann", "cut", tomorrow, "10:00", NOW)
    assert not booking.book(db, 2, "Bob", "cut", tomorrow, "10:00", NOW)  # double booking
    assert "10:00" not in booking.free_slots(db, tomorrow, NOW)

    # forged button data is rejected
    assert not booking.book(db, 2, "Bob", "nope", tomorrow, "11:00", NOW)
    assert not booking.book(db, 2, "Bob", "cut", "2030-01-01", "11:00", NOW)
    assert not booking.book(db, 2, "Bob", "cut", today, "10:00", NOW)  # already past

    (booking_id, *_), = booking.user_bookings(db, 1, NOW)
    assert not booking.cancel(db, 2, booking_id)  # someone else's booking
    assert booking.cancel(db, 1, booking_id)
    assert "10:00" in booking.free_slots(db, tomorrow, NOW)
