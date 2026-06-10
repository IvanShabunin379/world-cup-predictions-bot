from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.db import get_db
from keyboards.reply import main_menu_kb
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID

router = Router()


def _get_or_create_user(telegram_id: int, username: str | None, name: str) -> dict:
    db = get_db()
    user = db.table("users").select("*").eq("telegram_id", telegram_id).execute().data
    if user:
        return user[0]
    res = db.table("users").insert({
        "telegram_id": telegram_id,
        "username": username,
        "name": name,
    }).execute()
    return res.data[0]


def _get_public_league() -> dict | None:
    db = get_db()
    leagues = db.table("leagues").select("*").eq("type", "public").execute().data
    return leagues[0] if leagues else None


def _get_private_league() -> dict | None:
    db = get_db()
    leagues = db.table("leagues").select("*").eq("type", "private").execute().data
    return leagues[0] if leagues else None


def _join_league(user_id: int, league_id: int):
    db = get_db()
    existing = (
        db.table("league_members")
        .select("user_id")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
        .data
    )
    if not existing:
        db.table("league_members").insert({"league_id": league_id, "user_id": user_id}).execute()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg = message.from_user
    name = tg.full_name or tg.username or str(tg.id)
    user = _get_or_create_user(tg.id, tg.username, name)

    # Check for invite deep-link: /start join_<token>
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("join_"):
        token = args[1][5:]
        await _handle_invite(message, user, token)
        return

    is_private_member = tg.id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID)

    if is_private_member:
        # Auto-add to both leagues
        private = _get_private_league()
        public = _get_public_league()
        if private:
            _join_league(user["id"], private["id"])
        if public:
            _join_league(user["id"], public["id"])

        await message.answer(
            f"Привет, {name}! 👋\n\n"
            "Ты участвуешь в обеих лигах:\n"
            "• Личная лига (Ваня vs Ник) — со своими правилами\n"
            "• Общая лига — для всех друзей\n\n"
            "Используй кнопки внизу для навигации.",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(
            f"Привет, {name}! 👋\n\n"
            "Добро пожаловать в турнир прогнозов ЧМ-2026!\n\n"
            "Чтобы вступить в общую лигу — попроси у Вани инвайт-ссылку.",
            reply_markup=main_menu_kb(),
        )


async def _handle_invite(message: Message, user: dict, token: str):
    db = get_db()
    invite = (
        db.table("invite_tokens")
        .select("*")
        .eq("token", token)
        .eq("used", False)
        .execute()
        .data
    )
    if not invite:
        await message.answer("Ссылка недействительна или уже использована.", reply_markup=main_menu_kb())
        return

    invite = invite[0]
    league_id = invite["league_id"]

    existing = (
        db.table("league_members")
        .select("user_id")
        .eq("league_id", league_id)
        .eq("user_id", user["id"])
        .execute()
        .data
    )
    if existing:
        await message.answer("Ты уже в лиге! Используй кнопки внизу.", reply_markup=main_menu_kb())
        return

    db.table("league_members").insert({"league_id": league_id, "user_id": user["id"]}).execute()

    await message.answer(
        "🏆 Ты вступил в турнир прогнозов ЧМ-2026!\n\n"
        "Используй кнопки внизу для навигации. Удачи! ⚽",
        reply_markup=main_menu_kb(),
    )
