"""
Scheduled notifications:
- 24h before match: remind all league members
- 2h before match: remind those without predictions
- ~2h after match: send results and points
"""
import asyncio
from datetime import timezone, timedelta
from dateutil import parser as dtparser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from database.db import get_db
from utils.timezone import fmt_msk, now_utc
from utils.flags import fmt_match
from keyboards.inline import predict_match_kb
from services.scoring import score_group, score_playoff
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID


scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler(bot):
    scheduler.start()
    asyncio.create_task(_schedule_all_notifications(bot))


async def _schedule_all_notifications(bot):
    db = get_db()
    for attempt in range(5):
        try:
            matches = (
                db.table("matches")
                .select("*")
                .eq("status", "upcoming")
                .execute()
                .data
            )
            break
        except Exception as e:
            import logging
            logging.warning(f"Scheduler load attempt {attempt+1} failed: {e}")
            await asyncio.sleep(5 * (attempt + 1))
    else:
        import logging
        logging.error("Failed to load matches for scheduler after 5 attempts.")
        return
    for m in matches:
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        now = now_utc()

        remind_24h = kickoff - timedelta(hours=24)
        remind_2h = kickoff - timedelta(hours=2)
        results_time = kickoff + timedelta(hours=2, minutes=15)

        if remind_24h > now:
            scheduler.add_job(
                _send_match_reminder,
                trigger=DateTrigger(run_date=remind_24h),
                args=[bot, m["id"], "24h"],
                id=f"remind_24h_{m['id']}",
                replace_existing=True,
            )
        if remind_2h > now:
            scheduler.add_job(
                _send_match_reminder,
                trigger=DateTrigger(run_date=remind_2h),
                args=[bot, m["id"], "2h"],
                id=f"remind_2h_{m['id']}",
                replace_existing=True,
            )
        if results_time > now:
            scheduler.add_job(
                _fetch_and_send_results,
                trigger=DateTrigger(run_date=results_time),
                args=[bot, m["id"]],
                id=f"results_{m['id']}",
                replace_existing=True,
            )


async def _send_match_reminder(bot, match_id: int, remind_type: str):
    db = get_db()
    match = db.table("matches").select("*").eq("id", match_id).execute().data
    if not match:
        return
    match = match[0]
    kickoff = dtparser.parse(match["kickoff_at"]).replace(tzinfo=timezone.utc)

    league_members = _get_all_league_members()

    for uid, tg_id in league_members.items():
        if remind_type == "2h":
            # Only those without prediction
            preds = _get_user_predictions_for_match(uid, match_id)
            if preds:
                continue

        match_str = fmt_match(match['home_team'], match['away_team'])
        try:
            if remind_type == "24h":
                text = (
                    f"⏰ Напоминание (24 часа)!\n\n"
                    f"{match_str}\n"
                    f"🕐 {fmt_msk(kickoff)}\n\n"
                    "Не забудь сделать прогноз!"
                )
            else:
                text = (
                    f"🚨 2 часа до матча!\n\n"
                    f"{match_str}\n"
                    f"🕐 {fmt_msk(kickoff)}\n\n"
                    "У тебя ещё нет прогноза!"
                )
            await bot.send_message(
                tg_id, text,
                reply_markup=predict_match_kb(match_id),
            )
        except Exception:
            pass


async def _fetch_and_send_results(bot, match_id: int):
    """Fetch result, calculate points, notify users."""
    from services.api_football import fetch_fixtures_by_date, parse_result

    db = get_db()
    match = db.table("matches").select("*").eq("id", match_id).execute().data
    if not match:
        return
    match = match[0]

    kickoff = dtparser.parse(match["kickoff_at"]).replace(tzinfo=timezone.utc)
    date_str = kickoff.strftime("%Y-%m-%d")

    try:
        fixtures = await fetch_fixtures_by_date(date_str)
        result = None
        for f in fixtures:
            ht = f.get("teams", {}).get("home", {}).get("name", "")
            at = f.get("teams", {}).get("away", {}).get("name", "")
            # Simple name matching (may need improvement for non-Latin names)
            if match["home_team"][:4].lower() in ht.lower() or ht.lower() in match["home_team"].lower():
                result = parse_result(f)
                break
    except Exception:
        result = None

    if not result or result["home_score"] is None:
        # Retry in 30 min
        from apscheduler.triggers.date import DateTrigger
        from datetime import datetime
        retry_time = now_utc() + timedelta(minutes=30)
        scheduler.add_job(
            _fetch_and_send_results,
            trigger=DateTrigger(run_date=retry_time),
            args=[bot, match_id],
            id=f"results_retry_{match_id}",
            replace_existing=True,
        )
        return

    # Update match in DB
    home_score = result["home_score"]
    away_score = result["away_score"]
    db.table("matches").update({
        "home_score": home_score,
        "away_score": away_score,
        "status": "finished",
    }).eq("id", match_id).execute()

    # Calculate and store points for all predictions
    preds = db.table("predictions").select("*").eq("match_id", match_id).execute().data
    for pred in preds:
        if match["stage"] == "group":
            pts = score_group(pred["home_score"], pred["away_score"], home_score, away_score)
        else:
            pts = score_playoff(
                pred["home_score"], pred["away_score"], pred["outcome_type"],
                home_score, away_score, match["outcome"],
            )
        db.table("predictions").update({"points": pts}).eq("id", pred["id"]).execute()

    # Send result messages
    from utils.flags import flag
    result_text = (
        f"🏁 Матч завершён!\n\n"
        f"{flag(match['home_team'])} {match['home_team']} {home_score}:{away_score} {match['away_team']} {flag(match['away_team'])}\n\n"
    )

    league_members = _get_all_league_members()
    for uid, tg_id in league_members.items():
        user_preds = [p for p in preds if p["user_id"] == uid]
        if not user_preds:
            continue
        user_text = result_text
        for pred in user_preds:
            pts = pred.get("points", 0) or 0
            league = db.table("leagues").select("name").eq("id", pred["league_id"]).execute().data
            league_name = league[0]["name"] if league else "Лига"
            user_text += f"Твой прогноз ({league_name}): {pred['home_score']}:{pred['away_score']} → +{pts} очков\n"

        try:
            await bot.send_message(tg_id, user_text)
        except Exception:
            pass

    # Show both predictions in private league
    await _reveal_private_predictions(bot, match, preds, home_score, away_score)


async def _reveal_private_predictions(bot, match, preds, home_score, away_score):
    db = get_db()
    private_league = db.table("leagues").select("id").eq("type", "private").execute().data
    if not private_league:
        return
    private_id = private_league[0]["id"]
    private_preds = [p for p in preds if p["league_id"] == private_id]
    if len(private_preds) < 2:
        return

    lines = [f"🔍 Прогнозы в личной лиге:\n{fmt_match(match['home_team'], match['away_team'])}\n"]
    for pred in private_preds:
        user = db.table("users").select("name").eq("id", pred["user_id"]).execute().data
        name = user[0]["name"] if user else "?"
        pts = pred.get("points", 0) or 0
        lines.append(f"{name}: {pred['home_score']}:{pred['away_score']} → +{pts}")

    text = "\n".join(lines)
    for tg_id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID):
        try:
            await bot.send_message(tg_id, text)
        except Exception:
            pass


def _get_all_league_members() -> dict[int, int]:
    """Returns {user_id: telegram_id}"""
    db = get_db()
    members = db.table("league_members").select("user_id").execute().data
    user_ids = list({m["user_id"] for m in members})
    if not user_ids:
        return {}
    users = db.table("users").select("id, telegram_id").in_("id", user_ids).execute().data
    return {u["id"]: u["telegram_id"] for u in users}


def _get_user_predictions_for_match(user_id: int, match_id: int) -> list:
    db = get_db()
    return db.table("predictions").select("id").eq("user_id", user_id).eq("match_id", match_id).execute().data
