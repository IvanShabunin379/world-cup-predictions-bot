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
from utils.flags import fmt_match, flag, fmt_pred_short
from services.scoring import score_group, score_playoff, playoff_winner_guessed
from utils.text import pred_result_label
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
    # Every 6h: discover newly announced playoff fixtures (semis, bronze, final)
    # on ESPN and add them to the matches table automatically.
    scheduler.add_job(
        _sync_new_matches,
        trigger=CronTrigger(hour="*/6", minute=40, timezone="UTC"),
        args=[bot],
        id="sync_new_matches",
        replace_existing=True,
    )
    scheduler.start()
    asyncio.create_task(_schedule_result_jobs(bot))
    asyncio.create_task(_catch_up_results(bot))
    asyncio.create_task(_sync_new_matches(bot))
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


# Playoff round by calendar day of kickoff (WC 2026 schedule).
_PLAYOFF_ROUND_WINDOWS = [
    ("2026-07-08", 2),  # 1/8 финала
    ("2026-07-12", 3),  # 1/4 финала
    ("2026-07-16", 4),  # полуфиналы
    ("2026-07-18", 5),  # матч за 3-е место
]
_FINAL_ROUND = 6


def _playoff_round_for(kickoff) -> int:
    day = kickoff.strftime("%Y-%m-%d")
    for last_day, rnd in _PLAYOFF_ROUND_WINDOWS:
        if day <= last_day:
            return rnd
    return _FINAL_ROUND


async def _sync_new_matches(bot):
    """Discover newly announced playoff fixtures on ESPN and insert them.

    Placeholder fixtures ("Semifinal 1 Winner" etc.) don't map to real team
    names, so a fixture is only picked up once its bracket slot resolves.
    """
    import aiohttp
    from services.espn import ESPN_URL, TEAM_EN_TO_RU

    db = get_db()
    try:
        existing = db.table("matches").select("id, home_team, away_team, kickoff_at").execute().data
    except Exception:
        return
    existing_keys = set()
    for m in existing:
        day = dtparser.parse(m["kickoff_at"]).strftime("%Y-%m-%d")
        existing_keys.add((frozenset((m["home_team"], m["away_team"])), day))
    next_id = max(m["id"] for m in existing) + 1

    now = now_utc()
    new_rows = []
    async with aiohttp.ClientSession() as session:
        for offset in range(7):
            date_str = (now + timedelta(days=offset)).strftime("%Y%m%d")
            try:
                async with session.get(
                    ESPN_URL, params={"dates": date_str},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    data = await resp.json()
            except Exception:
                continue
            for e in data.get("events", []):
                try:
                    comp = e["competitions"][0]
                    home = away = None
                    for c in comp["competitors"]:
                        ru = TEAM_EN_TO_RU.get(c["team"]["displayName"])
                        if c["homeAway"] == "home":
                            home = ru
                        else:
                            away = ru
                    if not home or not away:
                        continue  # unresolved bracket placeholder
                    kickoff = dtparser.parse(e["date"]).astimezone(timezone.utc)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if kickoff <= now:
                    continue
                key = (frozenset((home, away)), kickoff.strftime("%Y-%m-%d"))
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                new_rows.append({
                    "id": next_id,
                    "home_team": home,
                    "away_team": away,
                    "kickoff_at": kickoff.isoformat(),
                    "stage": "playoff",
                    "round": _playoff_round_for(kickoff),
                    "status": "upcoming",
                })
                next_id += 1

    if not new_rows:
        return
    try:
        db.table("matches").insert(new_rows).execute()
    except Exception:
        logging.exception("Failed to insert auto-discovered matches")
        return

    # Register reveal/result jobs for the new matches right away.
    await _schedule_result_jobs(bot)

    lines = [
        f"{fmt_match(r['home_team'], r['away_team'])} · {fmt_msk(dtparser.parse(r['kickoff_at']))}"
        for r in new_rows
    ]
    text = (
        "🆕 В базу автоматически добавлены новые матчи:\n\n"
        + "\n".join(lines)
        + "\n\nРаспределение «кто первый» для Братьев не назначено."
    )
    try:
        await bot.send_message(VANYA_TELEGRAM_ID, text)
    except Exception:
        pass


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
            pred_str = fmt_pred_short(p, match["home_team"], match["away_team"])
            lines.append(f"  {name}: {pred_str}")
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


def _fmt_result_header(match: dict, home_score: int, away_score: int, outcome_type: str | None, use_spoiler: bool) -> str:
    h, a = match["home_team"], match["away_team"]
    fh, fa = flag(h), flag(a)
    score_s = f"{home_score}:{away_score}"
    if use_spoiler:
        score_s = f"<tg-spoiler>{score_s}</tg-spoiler>"
    if not outcome_type or outcome_type in ("P1", "P2"):
        return f"{fh} {h} {score_s} {fa} {a}"
    elif outcome_type in ("NP1", "NP2"):
        return f"{fh} {h} {score_s} (доп. вр.) {fa} {a}"
    else:  # NPP1, NPP2
        winner = h if outcome_type == "NPP1" else a
        extra = f"(по пен. {winner})"
        if use_spoiler:
            extra = f"<tg-spoiler>{extra}</tg-spoiler>"
        return f"{fh} {h} {score_s} {fa} {a}\n{extra}"


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

    from services.espn import determine_playoff_outcome

    home_score = result["home_score"]
    away_score = result["away_score"]

    outcome_type = None
    if match["stage"] == "playoff":
        outcome_type = determine_playoff_outcome(
            result.get("status_name", ""),
            result.get("short_detail", ""),
            home_score, away_score,
            result.get("home_winner", home_score > away_score),
        )

    match_update = {"home_score": home_score, "away_score": away_score, "status": "finished"}
    if outcome_type:
        match_update["outcome"] = outcome_type
    db.table("matches").update(match_update).eq("id", match_id).execute()
    match["outcome"] = outcome_type  # keep in-memory copy in sync

    preds = db.table("predictions").select("*").eq("match_id", match_id).execute().data
    for pred in preds:
        if match["stage"] == "group":
            pts = score_group(pred["home_score"], pred["away_score"], home_score, away_score)
        else:
            pts = score_playoff(
                pred["home_score"], pred["away_score"], pred.get("outcome_type") or "P1",
                home_score, away_score, outcome_type or "P1",
            )
        db.table("predictions").update({"points": pts}).eq("id", pred["id"]).execute()
        pred["points"] = pts

    kickoff = dtparser.parse(match["kickoff_at"]).replace(tzinfo=timezone.utc)
    use_spoiler = 0 <= utc_to_msk(kickoff).hour < 8

    match_str = _fmt_result_header(match, home_score, away_score, outcome_type, use_spoiler)
    result_text = f"🏁 Матч завершён!\n\n{match_str}\n\n"

    league_names = {l["id"]: l["name"] for l in db.table("leagues").select("id, name").execute().data}
    user_names = {u["id"]: u["name"] for u in db.table("users").select("id, name").execute().data}
    is_playoff = match["stage"] == "playoff"
    actual_oc = outcome_type or ("P1" if home_score > away_score else "P2")

    # Group predictions by league, best result on top
    preds_by_league: dict[int, list] = {}
    for p in preds:
        preds_by_league.setdefault(p["league_id"], []).append(p)
    for ps in preds_by_league.values():
        ps.sort(key=lambda p: -(p["points"] or 0))

    league_members = _get_all_league_members()
    for user_id, tg_id in league_members.items():
        # Each recipient sees every league they predicted in — with everyone's predictions
        user_league_ids = sorted(
            lid for lid, ps in preds_by_league.items()
            if any(p["user_id"] == user_id for p in ps)
        )
        if not user_league_ids:
            continue
        text = result_text
        for lid in user_league_ids:
            text += f"<b>{league_names.get(lid, 'Лига')}</b>\n"
            for p in preds_by_league[lid]:
                name = user_names.get(p["user_id"], "?")
                winner_ok = is_playoff and playoff_winner_guessed(
                    p.get("outcome_type") or "P1", actual_oc
                )
                label = pred_result_label(p.get("points"), is_playoff, winner_ok)
                pred_str = fmt_pred_short(p, match["home_team"], match["away_team"])
                line = f"{name}: {pred_str} → {label}"
                if use_spoiler:
                    line = f"<tg-spoiler>{line}</tg-spoiler>"
                if p["user_id"] == user_id:
                    line = f"<b>{line}</b>"
                text += line + "\n"
            text += "\n"
        try:
            await bot.send_message(tg_id, text.rstrip(), parse_mode="HTML")
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
