from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.db import get_db
from utils.timezone import fmt_msk, fmt_time, utc_to_msk, get_match_window, now_utc, MSK
from utils.flags import fmt_match
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID
from datetime import timezone, timedelta
from dateutil import parser as dtparser

router = Router()


def _get_user(telegram_id: int) -> dict | None:
    db = get_db()
    res = db.table("users").select("*").eq("telegram_id", telegram_id).execute().data
    return res[0] if res else None


def _get_leagues_for_user(user_id: int) -> list[dict]:
    db = get_db()
    members = db.table("league_members").select("league_id").eq("user_id", user_id).execute().data
    league_ids = [m["league_id"] for m in members]
    if not league_ids:
        return []
    return db.table("leagues").select("*").in_("id", league_ids).execute().data


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


def _get_prediction(user_id: int, match_id: int, league_id: int) -> dict | None:
    db = get_db()
    res = (
        db.table("predictions")
        .select("home_score, away_score")
        .eq("user_id", user_id)
        .eq("match_id", match_id)
        .eq("league_id", league_id)
        .execute()
        .data
    )
    return res[0] if res else None


def _get_assignment(match_id: int) -> int | None:
    db = get_db()
    res = db.table("match_assignments").select("first_user_id").eq("match_id", match_id).execute().data
    return res[0]["first_user_id"] if res else None


def _get_vanya_nik_ids() -> tuple[int | None, int | None]:
    db = get_db()
    v = db.table("users").select("id").eq("telegram_id", VANYA_TELEGRAM_ID).execute().data
    n = db.table("users").select("id").eq("telegram_id", NIK_TELEGRAM_ID).execute().data
    return (v[0]["id"] if v else None), (n[0]["id"] if n else None)


@router.message(Command("upcoming"))
@router.message(F.text == "📅 Ближайшие")
async def cmd_upcoming(message: Message):
    user = _get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    matches = _fetch_window_matches()
    if not matches:
        await message.answer("Нет предстоящих матчей.")
        return

    leagues = _get_leagues_for_user(user["id"])
    is_private = message.from_user.id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID)
    private_league = next((l for l in leagues if l["type"] == "private"), None)
    public_league = next((l for l in leagues if l["type"] == "public"), None)

    vanya_id, nik_id = _get_vanya_nik_ids() if is_private else (None, None)
    partner_id = nik_id if (is_private and user["id"] == vanya_id) else vanya_id

    # Group matches by MSK date
    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for m in matches:
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        msk_date = utc_to_msk(kickoff).date()
        by_date[msk_date].append((m, kickoff))

    today_msk = utc_to_msk(now_utc()).date()
    blocks = []

    for date in sorted(by_date.keys()):
        if date == today_msk:
            header = "<b>Сегодня</b>"
        elif date == today_msk + timedelta(days=1):
            header = "<b>Завтра</b>"
        else:
            months = ["", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
            header = f"<b>{date.day} {months[date.month]}</b>"

        block_lines = [header]

        for m, kickoff in by_date[date]:
            time_str = utc_to_msk(kickoff).strftime("%H:%M")
            match_line = f"{fmt_match(m['home_team'], m['away_team'])} · {time_str} МСК"

            status_parts = []

            if private_league:
                pl = private_league["name"]
                pred = _get_prediction(user["id"], m["id"], private_league["id"])
                if pred:
                    status_parts.append(f"{pl}: {pred['home_score']}:{pred['away_score']}")
                else:
                    first_uid = _get_assignment(m["id"])
                    if first_uid is None:
                        status_parts.append(f"{pl}: –")
                    elif first_uid == user["id"]:
                        status_parts.append(f"{pl}: – (твой ход)")
                    else:
                        partner_pred = _get_prediction(partner_id, m["id"], private_league["id"]) if partner_id else None
                        partner_name = "Ник" if user["id"] == vanya_id else "Ваня"
                        if partner_pred:
                            status_parts.append(f"{pl}: – ({partner_name} поставил)")
                        else:
                            status_parts.append(f"{pl}: ⏳ ждём {partner_name}")

            if public_league:
                pl = public_league["name"]
                pred = _get_prediction(user["id"], m["id"], public_league["id"])
                if pred:
                    status_parts.append(f"{pl}: {pred['home_score']}:{pred['away_score']}")
                else:
                    status_parts.append(f"{pl}: –")

            block_lines.append(match_line)
            if status_parts:
                block_lines.append("   " + " | ".join(status_parts))

        blocks.append("\n".join(block_lines))

    await message.answer("📅 Ближайшие матчи:\n\n" + "\n\n".join(blocks), parse_mode="HTML")
