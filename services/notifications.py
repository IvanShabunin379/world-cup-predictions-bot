"""
Scheduled notifications:
- 10:00 MSK daily: morning digest of matches in next 24h without predictions
- 20:00 MSK daily: evening reminder for matches in next 12h without predictions
- Per-match: results ~2h15m after kickoff
"""
import asyncio
import logging
from datetime import timezone, timedelta
from dateutil import parser as dtparser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from database.db import get_db
from utils.timezone import fmt_msk, now_utc, utc_to_msk
from utils.flags import fmt_match, flag
from services.scoring import score_group, score_playoff
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler(bot):
    # 10:00 MSK = 07:00 UTC
    scheduler.add_job(
        _morning_digest,
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        args=[bot],
        id="morning_digest",
        replace_existing=True,
    )
    # 20:00 MSK = 17:00 UTC
    scheduler.add_job(
        _evening_reminder,
        trigger=CronTrigger(hour=17, minute=0, timezone="UTC"),
        args=[bot],
        id="evening_reminder",
        replace_existing=True,
    )
    # Hourly self-healing catch-up: fetch results for any finished match the
    # bot may have missed while offline.
    scheduler.add_job(
        _catch_up_results,
        trigger=CronTrigger(minute=20, timezone="UTC"),
        args=[bot],
        id="catch_up_results",
        replace_existing=True,
    )
    scheduler.start()
    asyncio.create_task(_schedule_result_jobs(bot))
    asyncio.create_task(_catch_up_results(bot))
    # One-off: auto-fill Nik's prediction for Алжир–Австрия (match 59) if he misses it
    from datetime import datetime
    kickoff_59 = datetime(2026, 6, 28, 2, 0, tzinfo=timezone.utc)
    if kickoff_59 > now_utc():
        scheduler.add_job(
            _fill_default_prediction,
            trigger=DateTrigger(run_date=kickoff_59),
            args=[bot, 59, NIK_TELEGRAM_ID, 1, 1],
            id="default_pred_59_nik",
            replace_existing=True,
            misfire_grace_time=300,
        )


async def _fill_default_prediction(bot, match_id: int, telegram_id: int, home_score: int, away_score: int):
    """At kickoff, insert a default prediction for a user in every league they belong to, if they haven't predicted."""
    db = get_db()
    user = db.table("users").select("id, name").eq("telegram_id", telegram_id).execute().data
    if not user:
        return
    user = user[0]

    members = db.table("league_members").select("league_id").eq("user_id", user["id"]).execute().data
    filled = []
    for row in members:
        league_id = row["league_id"]
        existing = db.table("predictions").select("id").eq("user_id", user["id"]).eq("match_id", match_id).eq("league_id", league_id).execute().data
        if not existing:
            db.table("predictions").insert({
                "user_id": user["id"],
                "match_id": match_id,
                "league_id": league_id,
                "home_score": home_score,
                "away_score": away_score,
            }).execute()
            league = db.table("leagues").select("name").eq("id", league_id).execute().data
            filled.append((league[0]["name"] if league else str(league_id)))

    if filled:
        leagues_str = ", ".join(filled)
        try:
            await bot.send_message(
                telegram_id,
                f"⏰ Матч начался, а прогноза не было — автоматически поставлено {home_score}:{away_score} ({leagues_str}).",
            )
        except Exception:
            pass


async def _catch_up_results(bot):
    """Process any past matches still marked 'upcoming' (missed while offline)."""
    db = get_db()
    try:
        matches = db.table("matches").select("id, kickoff_at").eq("status", "upcoming").execute().data
    except Exception:
        return
    now = now_utc()
    for m in matches:
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        # Match should be over (kickoff + ~2h) before we try to fetch a result.
        if kickoff + timedelta(hours=2) <= now:
            await _fetch_and_send_results(bot, m["id"])


async def _schedule_result_jobs(bot):
    """Schedule result-fetch jobs for all upcoming matches."""
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
            logging.warning(f"Scheduler load attempt {attempt+1} failed: {e}")
            await asyncio.sleep(5 * (attempt + 1))
    else:
        logging.error("Failed to load matches for scheduler after 5 attempts.")
        return

    now = now_utc()
    # Track how many matches share the same kickoff so we can stagger notifications.
    # Two concurrent reveal jobs sending to the same users in the same second would
    # hit Telegram's 1-msg/sec per-chat limit; 15-second gaps between simultaneous
    # matches prevent that.
    kickoff_seq: dict[str, int] = {}
    for m in matches:
        kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
        results_time = kickoff + timedelta(hours=2, minutes=15)

        seq = kickoff_seq.get(m["kickoff_at"], 0)
        kickoff_seq[m["kickoff_at"]] = seq + 1
        reveal_time = kickoff + timedelta(seconds=seq * 15)

        if reveal_time > now:
            scheduler.add_job(
                _reveal_public_predictions,
                trigger=DateTrigger(run_date=reveal_time),
                args=[bot, m["id"]],
                id=f"reveal_{m['id']}",
                replace_existing=True,
                misfire_grace_time=300,
            )
        if results_time > now:
            scheduler.add_job(
                _fetch_and_send_results,
                trigger=DateTrigger(run_date=results_time),
                args=[bot, m["id"]],
                id=f"results_{m['id']}",
                replace_existing=True,
                misfire_grace_time=300,
            )


async def _morning_digest(bot):
    """10:00 MSK — digest of all matches today (next 24h)."""
    now = now_utc()
    # Floor to the current minute so matches at exactly 10:00 MSK are included
    window_start = now.replace(second=0, microsecond=0)
    await _send_reminders(bot, window_start, window_start + timedelta(hours=24), "⏰ Сегодня")


async def _evening_reminder(bot):
    """20:00 MSK — reminder for matches in next 12h."""
    now = now_utc()
    # Floor to the current minute so matches at exactly 20:00 MSK are included
    window_start = now.replace(second=0, microsecond=0)
    await _send_reminders(bot, window_start, window_start + timedelta(hours=12), "🔔 Скоро")


async def _send_reminders(bot, window_start, window_end, prefix: str):
    db = get_db()
    matches = (
        db.table("matches")
        .select("*")
        .eq("status", "upcoming")
        .gte("kickoff_at", window_start.isoformat())
        .lte("kickoff_at", window_end.isoformat())
        .order("kickoff_at")
        .execute()
        .data
    )
    if not matches:
        return

    league_members = _get_all_league_members()
    for user_id, tg_id in league_members.items():
        missing = [
            m for m in matches
            if not _get_user_predictions_for_match(user_id, m["id"])
        ]
        if not missing:
            continue

        lines = [f"{prefix}:"]
        for m in missing:
            kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
            time_str = utc_to_msk(kickoff).strftime("%H:%M")
            lines.append(f"{fmt_match(m['home_team'], m['away_team'])} · {time_str} МСК")
        lines.append("\nНет прогноза — нажми ⚽ Прогноз")

        try:
            await bot.send_message(tg_id, "\n".join(lines))
        except Exception:
            pass


async def _reveal_public_predictions(bot, match_id: int):
    """At kickoff: send all public league predictions to all public league members."""
    db = get_db()
    match = db.table("matches").select("*").eq("id", match_id).execute().data
    if not match:
        return
    match = match[0]

    public_league = db.table("leagues").select("id").eq("type", "public").execute().data
    if not public_league:
        return
    public_id = public_league[0]["id"]

    preds = (
        db.table("predictions")
        .select("*, users(name)")
        .eq("match_id", match_id)
        .eq("league_id", public_id)
        .execute()
        .data
    )

    match_str = fmt_match(match["home_team"], match["away_team"])
    if preds:
        lines = [f"🏁 Матч начался! {match_str}\n", "Прогнозы футбольных аналитиков Весенних Зорь:"]
        for p in sorted(preds, key=lambda x: x.get("created_at", "")):
            name = (p.get("users") or {}).get("name") or "?"
            lines.append(f"  {name}: {p['home_score']}:{p['away_score']}")
        text = "\n".join(lines)
    else:
        text = f"🏁 Матч начался! {match_str}"
    members = db.table("league_members").select("user_id").eq("league_id", public_id).execute().data
    user_ids = [m["user_id"] for m in members]
    users = db.table("users").select("id, telegram_id").in_("id", user_ids).execute().data

    for u in users:
        try:
            await bot.send_message(u["telegram_id"], text)
        except Exception:
            pass


async def _fetch_and_send_results(bot, match_id: int):
    from services.espn import fetch_match_result

    db = get_db()
    match = db.table("matches").select("*").eq("id", match_id).execute().data
    if not match:
        return
    match = match[0]

    try:
        result = await fetch_match_result(
            match["kickoff_at"], match["home_team"], match["away_team"]
        )
    except Exception:
        result = None

    if not result or not result.get("completed") or result["home_score"] is None:
        retry_time = now_utc() + timedelta(minutes=30)
        scheduler.add_job(
            _fetch_and_send_results,
            trigger=DateTrigger(run_date=retry_time),
            args=[bot, match_id],
            id=f"results_retry_{match_id}",
            replace_existing=True,
        )
        return

    home_score = result["home_score"]
    away_score = result["away_score"]
    db.table("matches").update({
        "home_score": home_score,
        "away_score": away_score,
        "status": "finished",
    }).eq("id", match_id).execute()

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
        pred["points"] = pts  # keep in-memory copy in sync for the messages below

    match_str = f"{flag(match['home_team'])} {match['home_team']} {home_score}:{away_score} {match['away_team']} {flag(match['away_team'])}"
    result_text = f"🏁 Матч завершён!\n\n{match_str}\n\n"

    league_members = _get_all_league_members()
    for user_id, tg_id in league_members.items():
        user_preds = [p for p in preds if p["user_id"] == user_id]
        if not user_preds:
            continue
        text = result_text
        for pred in user_preds:
            pts = pred.get("points", 0) or 0
            league = db.table("leagues").select("name").eq("id", pred["league_id"]).execute().data
            league_name = league[0]["name"] if league else "Лига"
            text += f"{league_name}: {pred['home_score']}:{pred['away_score']} → +{pts} оч.\n"
        try:
            await bot.send_message(tg_id, text)
        except Exception:
            pass

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

    match_str = fmt_match(match["home_team"], match["away_team"])
    lines = [f"🔍 Прогнозы Братья:\n{match_str}\n"]
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
