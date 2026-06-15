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


def _plural_points(n: int) -> str:
    if 11 <= n % 100 <= 14:
        return "очков"
    last = n % 10
    if last == 1:
        return "очко"
    if 2 <= last <= 4:
        return "очка"
    return "очков"


def _build_standings(league_id: int) -> str:
    db = get_db()
    members = db.table("league_members").select("user_id").eq("league_id", league_id).execute().data
    user_ids = [m["user_id"] for m in members]
    if not user_ids:
        return "В лиге нет участников."

    users = db.table("users").select("id, name, username").in_("id", user_ids).execute().data
    user_map = {u["id"]: u for u in users}

    stats: dict[int, dict] = {}
    for uid in user_ids:
        preds = (
            db.table("predictions")
            .select("home_score, away_score, points, matches(home_score, away_score, status)")
            .eq("user_id", uid)
            .eq("league_id", league_id)
            .execute()
            .data
        )
        if not preds:
            continue  # skip users who never made a prediction
        total = exact = outcomes = 0
        for p in preds:
            m = p.get("matches") or {}
            if m.get("status") != "finished":
                continue
            total += p["points"] or 0
            if p["home_score"] == m["home_score"] and p["away_score"] == m["away_score"]:
                exact += 1
            elif (p["points"] or 0) > 0:
                outcomes += 1
        stats[uid] = {"total": total, "exact": exact, "outcomes": outcomes}

    # Sort by points desc, then by exact scores desc as tiebreak
    ranked = sorted(
        stats.items(),
        key=lambda kv: (kv[1]["total"], kv[1]["exact"]),
        reverse=True,
    )

    # Total finished matches in the tournament (same for everyone — shown once on top).
    played_total = (
        db.table("matches").select("id", count="exact").eq("status", "finished").execute().count
    )

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"⚽ Сыграно матчей: {played_total}\n"]

    prev_key = None
    rank = 0
    for i, (uid, s) in enumerate(ranked, 1):
        key = (s["total"], s["exact"])
        if key != prev_key:           # ties (same points AND exact) share a place
            rank = i
            prev_key = key
        u = user_map.get(uid, {})
        name = u.get("name") or u.get("username") or str(uid)
        marker = medals.get(rank, f"{rank}.")
        lines.append(f"{marker} <b>{name}</b> — {s['total']} {_plural_points(s['total'])}")
        lines.append(f"      Угадано: 🎯 точный счёт: {s['exact']} · ✅ исход: {s['outcomes']}")

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
        await message.answer(f"🏆 <b>{leagues[0]['name']}</b>\n\n{text}", parse_mode="HTML")
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
    await callback.message.edit_text(f"🏆 <b>{league['name']}</b>\n\n{text}", parse_mode="HTML")
