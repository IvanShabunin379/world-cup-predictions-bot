from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_db
from utils.timezone import utc_to_msk, get_match_window, now_utc, MSK
from utils.flags import fmt_match
from datetime import timezone, timedelta
from dateutil import parser as dtparser

router = Router()


def _fetch_window_matches() -> list[dict]:
    """Fetch matches for today+tomorrow MSK. Fallback: next day with matches."""
    db = get_db()
    start_iso, end_iso = get_match_window()

    matches = (
        db.table("matches")
        .select("*")
        .eq("status", "upcoming")
        .gt("kickoff_at", start_iso)
        .lte("kickoff_at", end_iso)
        .order("kickoff_at")
        .execute()
        .data
    )

    if not matches:
        all_next = (
            db.table("matches")
            .select("*")
            .eq("status", "upcoming")
            .gt("kickoff_at", start_iso)
            .order("kickoff_at")
            .limit(20)
            .execute()
            .data
        )
        if all_next:
            first_date = dtparser.parse(all_next[0]["kickoff_at"]).replace(tzinfo=timezone.utc).astimezone(MSK).date()
            matches = [
                m for m in all_next
                if dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc).astimezone(MSK).date() == first_date
            ]

    return matches


@router.message(Command("upcoming"))
@router.message(F.text == "📅 Ближайшие")
async def cmd_upcoming(message: Message):
    matches = _fetch_window_matches()
    if not matches:
        await message.answer("Нет предстоящих матчей.")
        return

    # Group matches by MSK date
    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for m in matches:
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        msk_date = utc_to_msk(kickoff).date()
        by_date[msk_date].append((m, kickoff))

    today_msk = utc_to_msk(now_utc()).date()
    months_gen = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    blocks = []

    for date in sorted(by_date.keys()):
        date_label = f"{date.day} {months_gen[date.month]}"
        if date == today_msk:
            header = f"<b>Сегодня, {date_label}</b>"
        elif date == today_msk + timedelta(days=1):
            header = f"<b>Завтра, {date_label}</b>"
        else:
            header = f"<b>{date_label}</b>"

        block_lines = [header]

        for m, kickoff in by_date[date]:
            time_str = utc_to_msk(kickoff).strftime("%H:%M")
            match_line = f"{fmt_match(m['home_team'], m['away_team'])} · {time_str} МСК"

            block_lines.append(match_line)

        blocks.append("\n".join(block_lines))

    await message.answer("📅 Ближайшие матчи:\n\n" + "\n\n".join(blocks), parse_mode="HTML")
