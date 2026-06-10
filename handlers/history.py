from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_db
from utils.timezone import fmt_msk
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
        .not_.is_("matches.status", "upcoming")
        .order("matches.kickoff_at", desc=True)
        .limit(10)
        .execute()
        .data
    )

    if not preds:
        await message.answer("У тебя пока нет завершённых прогнозов.")
        return

    lines = ["📋 Последние прогнозы:\n"]
    for p in preds:
        m = p.get("matches") or {}
        if not m:
            continue
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        actual = ""
        if m["home_score"] is not None:
            actual = f"Счёт: {m['home_score']}:{m['away_score']}"
        points_str = f"+{p['points']} очков" if p["points"] is not None else "ожидает"

        lines.append(
            f"⚽ {m['home_team']} — {m['away_team']}\n"
            f"   {fmt_msk(kickoff)}\n"
            f"   Прогноз: {p['home_score']}:{p['away_score']}  {actual}\n"
            f"   {points_str}"
        )

    await message.answer("\n\n".join(lines))
