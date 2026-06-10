from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_db
from keyboards.inline import standings_league_kb
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID

router = Router()


def _get_user_id(telegram_id: int) -> int | None:
    db = get_db()
    res = db.table("users").select("id").eq("telegram_id", telegram_id).execute().data
    return res[0]["id"] if res else None


def _get_leagues_for_user(user_id: int) -> list[dict]:
    db = get_db()
    members = db.table("league_members").select("league_id").eq("user_id", user_id).execute().data
    league_ids = [m["league_id"] for m in members]
    if not league_ids:
        return []
    return db.table("leagues").select("*").in_("id", league_ids).execute().data


def _build_standings(league_id: int) -> str:
    db = get_db()
    members = db.table("league_members").select("user_id").eq("league_id", league_id).execute().data
    user_ids = [m["user_id"] for m in members]
    if not user_ids:
        return "В лиге нет участников."

    scores: dict[int, int] = {}
    for uid in user_ids:
        total = (
            db.table("predictions")
            .select("points")
            .eq("user_id", uid)
            .eq("league_id", league_id)
            .not_.is_("points", "null")
            .execute()
            .data
        )
        scores[uid] = sum(r["points"] for r in total if r["points"] is not None)

    users = db.table("users").select("id, name, username").in_("id", user_ids).execute().data
    user_map = {u["id"]: u for u in users}

    sorted_users = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    lines = []
    for rank, (uid, pts) in enumerate(sorted_users, 1):
        u = user_map.get(uid, {})
        name = u.get("name") or u.get("username") or str(uid)
        lines.append(f"{rank}. {name} — {pts} очков")

    return "\n".join(lines) if lines else "Нет данных."


@router.message(Command("standings"))
@router.message(F.text == "🏆 Таблица")
async def cmd_standings(message: Message, state: FSMContext):
    user_id = _get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    leagues = _get_leagues_for_user(user_id)
    if not leagues:
        await message.answer("Ты не состоишь ни в одной лиге.")
        return

    has_private = any(l["type"] == "private" for l in leagues)
    if len(leagues) == 1:
        text = _build_standings(leagues[0]["id"])
        await message.answer(f"🏆 {leagues[0]['name']}\n\n{text}")
    else:
        await state.update_data(leagues=leagues)
        await message.answer(
            "Выбери лигу:",
            reply_markup=standings_league_kb(has_private),
        )


@router.callback_query(F.data.startswith("standings_"))
async def handle_standings_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data[10:]  # "private" or "public"
    data = await state.get_data()
    leagues = data.get("leagues", [])
    league = next((l for l in leagues if l["type"] == choice), None)
    if not league:
        await callback.answer("Лига не найдена.", show_alert=True)
        return

    text = _build_standings(league["id"])
    await callback.answer()
    await callback.message.edit_text(f"🏆 {league['name']}\n\n{text}")
