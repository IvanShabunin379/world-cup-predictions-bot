from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_db
from utils.timezone import fmt_msk
from utils.flags import fmt_match
from datetime import timezone
from dateutil import parser as dtparser

router = Router()


def _get_user_id(telegram_id: int) -> int | None:
    db = get_db()
    res = db.table("users").select("id").eq("telegram_id", telegram_id).execute().data
    return res[0]["id"] if res else None


@router.message(Command("history"))
@router.message(F.text == "📋 История")
async def cmd_history(message: Message):
    user_id = _get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    db = get_db()
    preds = (
        db.table("predictions")
        .select("*, matches(home_team, away_team, kickoff_at, home_score, away_score, status, group_name)")
        .eq("user_id", user_id)
        .execute()
        .data
    )

    # Keep only finished matches, sort by kickoff descending, take last 10.
    finished = [
        p for p in preds
        if (p.get("matches") or {}).get("status") == "finished"
    ]
    finished.sort(key=lambda p: p["matches"]["kickoff_at"], reverse=True)
    preds = finished[:10]

    if not preds:
        await message.answer("У тебя пока нет завершённых прогнозов.")
        return

    league_rows = db.table("leagues").select("id, name").execute().data
    league_names = {l["id"]: l["name"] for l in league_rows}

    lines = ["📋 Последние прогнозы:\n"]
    for p in preds:
        m = p.get("matches") or {}
        if not m:
            continue
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        actual = ""
        if m["home_score"] is not None:
            actual = f"· Счёт: {m['home_score']}:{m['away_score']}"
        points_str = f"+{p['points']} очков" if p["points"] is not None else "ожидает"
        league_name = league_names.get(p["league_id"], "")

        lines.append(
            f"{fmt_match(m['home_team'], m['away_team'])}\n"
            f"   {fmt_msk(kickoff)}\n"
            f"   [{league_name}] Прогноз: {p['home_score']}:{p['away_score']}  {actual}\n"
            f"   {points_str}"
        )

    await message.answer("\n\n".join(lines))
