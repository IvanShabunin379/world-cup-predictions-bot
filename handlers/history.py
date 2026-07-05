from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import get_db
from keyboards.inline import history_league_kb
from utils.timezone import fmt_date_msk
from utils.text import plural_points
from utils.flags import flag, fmt_pred_short
from services.scoring import playoff_winner_guessed
from datetime import timezone
from dateutil import parser as dtparser

router = Router()

MAX_MSG = 3500  # stay under Telegram's 4096 limit per message


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


def _pts_label(pts, is_playoff: bool, winner_ok: bool) -> str:
    # ✅🎯 = максимум (группа 3, плей-офф 4); ✅ = угадан победитель/исход;
    # 🟡 = очки есть, но победитель не угадан (только плей-офф); ❌ = 0
    pts = pts or 0
    if pts == (4 if is_playoff else 3):
        emoji = "✅🎯"
    elif winner_ok if is_playoff else pts > 0:
        emoji = "✅"
    elif pts > 0:
        emoji = "🟡"
    else:
        emoji = "❌"
    return f"{emoji} {pts} {plural_points(pts)}"


def _build_history_blocks(league_id: int, is_private: bool) -> list[str]:
    """One text block per finished match, newest first."""
    db = get_db()

    preds = (
        db.table("predictions")
        .select("home_score, away_score, outcome_type, points, user_id, match_id, "
                "matches(home_team, away_team, home_score, away_score, outcome, stage, kickoff_at, status), "
                "users(name)")
        .eq("league_id", league_id)
        .execute()
        .data
    )

    # Group predictions by finished match
    by_match: dict[int, dict] = {}
    for p in preds:
        m = p.get("matches") or {}
        if m.get("status") != "finished":
            continue
        mid = p["match_id"]
        by_match.setdefault(mid, {"match": m, "preds": []})
        by_match[mid]["preds"].append(p)

    if not by_match:
        return []

    # Who predicted first (private league only)
    first_by_match: dict[int, int] = {}
    if is_private:
        rows = (
            db.table("match_assignments")
            .select("match_id, first_user_id")
            .in_("match_id", list(by_match.keys()))
            .execute()
            .data
        )
        first_by_match = {r["match_id"]: r["first_user_id"] for r in rows}
        try:
            blk = (
                db.table("blocked_attempts")
                .select("match_id, user_id")
                .in_("match_id", list(by_match.keys()))
                .execute()
                .data
            )
            blocked_by_match = {r["match_id"]: r["user_id"] for r in blk}
        except Exception:
            blocked_by_match = {}
    else:
        blocked_by_match = {}

    # Sort matches by kickoff ascending (opening match → latest finished)
    ordered = sorted(
        by_match.items(),
        key=lambda kv: kv[1]["match"]["kickoff_at"],
    )

    blocks = []
    for mid, data in ordered:
        m = data["match"]
        score_s = f"{m['home_score']}:{m['away_score']}"
        oc = m.get("outcome")
        if oc in ("NP1", "NP2"):
            score_s += " (доп. вр.)"
        elif oc in ("NPP1", "NPP2"):
            winner = m["home_team"] if oc == "NPP1" else m["away_team"]
            score_s += f" (по пен. {winner})"
        head = (
            f"{flag(m['home_team'])} {m['home_team']} "
            f"{score_s} "
            f"{m['away_team']} {flag(m['away_team'])} · {fmt_date_msk(dtparser.parse(m['kickoff_at']).replace(tzinfo=timezone.utc))}"
        )
        lines = [head]

        first_uid = first_by_match.get(mid)
        if is_private and first_uid:
            first_name = next(
                (p["users"]["name"] for p in data["preds"] if p["user_id"] == first_uid),
                None,
            )
            if first_name:
                lines.append(f"Первым ставил: {first_name}")

            blocked_uid = blocked_by_match.get(mid)
            if blocked_uid:
                blocked_name = next(
                    (p["users"]["name"] for p in data["preds"] if p["user_id"] == blocked_uid),
                    None,
                )
                if blocked_name:
                    lines.append(f"🤫 {blocked_name} хотел поставить так же, но не смог")

        # Order predictions: first predictor on top (private), then by points desc
        def sort_key(p):
            is_first = is_private and p["user_id"] == first_uid
            return (0 if is_first else 1, -(p["points"] or 0))

        lines.append("")
        is_playoff = m.get("stage") == "playoff"
        actual_oc = m.get("outcome") or (
            "P1" if (m["home_score"] or 0) > (m["away_score"] or 0) else "P2"
        )
        for p in sorted(data["preds"], key=sort_key):
            name = (p.get("users") or {}).get("name") or "?"
            tag = " (1-й)" if (is_private and p["user_id"] == first_uid) else ""
            winner_ok = playoff_winner_guessed(p.get("outcome_type") or "P1", actual_oc)
            label = _pts_label(p["points"], is_playoff, winner_ok)
            pred_s = fmt_pred_short(p, m["home_team"], m["away_team"])
            lines.append(f"{name}{tag}: {pred_s} → {label}")

        blocks.append("\n".join(lines))

    return blocks


def _chunk_blocks(blocks: list[str], header: str) -> list[str]:
    """Pack match blocks into messages under the Telegram size limit."""
    messages = []
    current = header
    for block in blocks:
        candidate = current + "\n\n" + block
        if len(candidate) > MAX_MSG:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


async def _send_history(target, league: dict, is_private: bool):
    blocks = _build_history_blocks(league["id"], is_private)
    if not blocks:
        await target.answer("В этой лиге пока нет завершённых матчей.")
        return
    header = f"📋 История — {league['name']}"
    for msg in _chunk_blocks(blocks, header):
        await target.answer(msg)


@router.message(Command("history"))
@router.message(F.text == "📋 История")
async def cmd_history(message: Message, state: FSMContext):
    user_id = _get_user_id(message.from_user.id)
    if not user_id:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    leagues = _get_leagues_for_user(user_id)
    if not leagues:
        await message.answer("Ты не состоишь ни в одной лиге.")
        return

    if len(leagues) == 1:
        league = leagues[0]
        await _send_history(message, league, league["type"] == "private")
    else:
        await state.update_data(leagues=leagues)
        await message.answer("Выбери лигу:", reply_markup=history_league_kb(leagues))


@router.callback_query(F.data.startswith("history_"))
async def handle_history_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data[8:]  # "private" or "public"
    data = await state.get_data()
    leagues = data.get("leagues", [])
    league = next((l for l in leagues if l["type"] == choice), None)
    if not league:
        await callback.answer("Лига не найдена.", show_alert=True)
        return
    await callback.answer()
    await _send_history(callback.message, league, choice == "private")
