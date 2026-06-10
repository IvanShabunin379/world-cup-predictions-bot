"""
Admin commands: /invite, /assignmatches
Only accessible to Vanya (and Nik for /assignmatches).
"""
import secrets
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_db
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID
from services.match_assignments import generate_assignments

router = Router()

ADMIN_IDS = {VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID}


@router.message(Command("invite"))
async def cmd_invite(message: Message):
    if message.from_user.id != VANYA_TELEGRAM_ID:
        await message.answer("Эта команда только для Вани.")
        return

    db = get_db()
    vanya = db.table("users").select("id").eq("telegram_id", VANYA_TELEGRAM_ID).execute().data
    if not vanya:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    public_league = db.table("leagues").select("id").eq("type", "public").execute().data
    if not public_league:
        await message.answer("Публичная лига не найдена. Запусти seed сначала.")
        return

    # Reuse existing token if one already exists (multi-use link)
    existing_token = db.table("invite_tokens").select("token").eq("league_id", public_league[0]["id"]).eq("used", False).limit(1).execute().data
    if existing_token:
        token = existing_token[0]["token"]
    else:
        token = secrets.token_urlsafe(8)
        db.table("invite_tokens").insert({
            "token": token,
            "league_id": public_league[0]["id"],
            "created_by": vanya[0]["id"],
        }).execute()

    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=join_{token}"
    await message.answer(f"🔗 Инвайт-ссылка (постоянная, для всех):\n{link}\n\nМожно скинуть в общий чат — каждый кликнет и вступит.")


@router.message(Command("assignmatches"))
async def cmd_assignmatches(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда только для Вани и Ника.")
        return

    db = get_db()
    existing = db.table("match_assignments").select("match_id").limit(1).execute().data
    if existing:
        await message.answer(
            "Распределение уже существует! Хочешь пересгенерировать?\n"
            "Отправь /assignmatches force чтобы перезаписать."
        )
        return

    await _do_assign(message)


async def _do_assign(message: Message):
    try:
        assignments = generate_assignments()
        db = get_db()
        vanya = db.table("users").select("id").eq("telegram_id", VANYA_TELEGRAM_ID).execute().data[0]
        nik = db.table("users").select("id").eq("telegram_id", NIK_TELEGRAM_ID).execute().data[0]

        vanya_count = sum(1 for uid in assignments.values() if uid == vanya["id"])
        nik_count = sum(1 for uid in assignments.values() if uid == nik["id"])

        await message.answer(
            f"✅ Распределение сгенерировано!\n\n"
            f"Ваня: {vanya_count} матчей первым\n"
            f"Ник: {nik_count} матчей первым\n\n"
            f"Всего: {len(assignments)} матчей"
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("assignmatches"))
async def cmd_assignmatches_force(message: Message):
    """Handle /assignmatches force"""
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.strip().lower()
    if "force" in text:
        await _do_assign(message)
