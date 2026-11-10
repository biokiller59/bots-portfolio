"""Appointment booking bot for a small business (demo: a barbershop).

Run:  set BOT_TOKEN=...  &&  set ADMIN_ID=<your telegram id>  &&  python bot.py
"""
import asyncio
import os
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import booking

ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
dp = Dispatcher()
db = booking.connect()


def keyboard(buttons, width=1):
    b = InlineKeyboardBuilder()
    for text, data in buttons:
        b.button(text=text, callback_data=data)
    return b.adjust(width).as_markup()


def services_kb():
    return keyboard([(f"{name} — ${price}", f"svc|{key}") for key, (name, price) in booking.SERVICES.items()])


def slots_kb(service, day):
    slots = [(s, f"slot|{service}|{day}|{s}") for s in booking.free_slots(db, day)]
    return keyboard(slots + [("« Back", f"svc|{service}")], width=3)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Welcome! Choose a service:\n\n/my — your bookings", reply_markup=services_kb())


@dp.callback_query(F.data.startswith("svc|"))
async def pick_day(call: CallbackQuery):
    service = call.data.split("|")[1]
    buttons = [(booking.pretty_day(d), f"day|{service}|{d}") for d in booking.days()]
    await call.message.edit_text("Choose a day:", reply_markup=keyboard(buttons, width=2))
    await call.answer()


@dp.callback_query(F.data.startswith("day|"))
async def pick_slot(call: CallbackQuery):
    _, service, day = call.data.split("|")
    await call.message.edit_text(f"Free time on {booking.pretty_day(day)}:", reply_markup=slots_kb(service, day))
    await call.answer()


@dp.callback_query(F.data.startswith("slot|"))
async def confirm(call: CallbackQuery, bot: Bot):
    _, service, day, slot = call.data.split("|")
    if not booking.book(db, call.from_user.id, call.from_user.full_name, service, day, slot):
        await call.answer("Sorry, this time was just taken. Pick another one.", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=slots_kb(service, day))
        return
    name = booking.SERVICES[service][0]
    await call.message.edit_text(f"✅ Booked: {name}, {booking.pretty_day(day)} at {slot}.\n\n/my — view or cancel")
    await call.answer()
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, f"New booking: {call.from_user.full_name} — {name}, {day} {slot}")


@dp.message(Command("my"))
async def my_bookings(message: Message):
    rows = booking.user_bookings(db, message.from_user.id)
    if not rows:
        await message.answer("You have no bookings. /start to make one.")
        return
    buttons = [
        (f"❌ {booking.SERVICES[svc][0]}, {booking.pretty_day(day)} {slot}", f"cancel|{id_}")
        for id_, svc, day, slot in rows
    ]
    await message.answer("Your bookings (tap to cancel):", reply_markup=keyboard(buttons))


@dp.callback_query(F.data.startswith("cancel|"))
async def cancel(call: CallbackQuery):
    done = booking.cancel(db, call.from_user.id, int(call.data.split("|")[1]))
    await call.message.edit_text("Booking cancelled." if done else "This booking no longer exists.")
    await call.answer()


@dp.message(Command("today"), F.from_user.id == ADMIN_ID)
async def today(message: Message):
    rows = booking.day_bookings(db, date.today().isoformat())
    lines = [f"{slot} — {booking.SERVICES[svc][0]} — {name}" for slot, svc, name in rows]
    await message.answer("\n".join(lines) or "No bookings today.")


if __name__ == "__main__":
    asyncio.run(dp.start_polling(Bot(os.environ["BOT_TOKEN"])))
