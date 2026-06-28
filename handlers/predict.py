"""
/predict flow using inline buttons for match selection.

Private league rule: sequential predictions (first_user_id from match_assignments).
Public league: always open, no ordering.

Playoff flow: outcome selection first → score entry second (with validation).
"""
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_db
from keyboards.inline import confirm_prediction_kb, league_choice_kb, playoff_outcome_kb
from utils.timezone import utc_to_msk, fmt_msk, now_utc, get_match_window, MSK
from utils.flags import fmt_match, flag, fmt_pred_short, fmt_playoff_confirm
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID
from datetime import timezone
from dateutil import parser as dtparser

router = Router()


class PredictStates(StatesGroup):
    choosing_match = State()
    choosing_outcome = State()   # playoff only: pick outcome FIRST
    entering_score = State()     # then enter score (validated by outcome)
    choosing_league = State()
    confirming = State()


# ── DB helpers ────────────────────────────────────────────────────────────────

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


def _get_prediction(user_id: int, match_id: int, league_id: int) -> dict | None:
    db = get_db()
    res = (
        db.table("predictions")
        .select("*")
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


# ── Match fetching ─────────────────────────────────────────────────────────────

def _fetch_window_matches() -> list[dict]:
    """Today + tomorrow MSK, or next day with matches if none in that window."""
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
            first_date = (
                dtparser.parse(all_next[0]["kickoff_at"])
                .replace(tzinfo=timezone.utc)
                .astimezone(MSK)
                .date()
            )
            matches = [
                m for m in all_next
                if dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc).astimezone(MSK).date() == first_date
            ]

    return matches


# ── Match list builder ────────────────────────────────────────────────────────

def _build_match_list(matches: list[dict], user_db_id: int, leagues: list[dict], tg_id: int):
    """
    Returns (text, keyboard, matches_by_id) where keyboard contains buttons
    only for matches the user can currently predict.
    """
    is_private_member = tg_id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID)
    private_league = next((l for l in leagues if l["type"] == "private"), None)
    public_league = next((l for l in leagues if l["type"] == "public"), None)

    vanya_id, nik_id = _get_vanya_nik_ids() if is_private_member else (None, None)
    partner_id = nik_id if (user_db_id == vanya_id) else vanya_id
    partner_nom = "Ник" if (user_db_id == vanya_id) else "Ваня"

    can_predict = []
    done = []

    for m in matches:
        mid = m["id"]
        private_pred = _get_prediction(user_db_id, mid, private_league["id"]) if private_league else None
        public_pred = _get_prediction(user_db_id, mid, public_league["id"]) if public_league else None

        needs_private = private_league and not private_pred
        needs_public = public_league and not public_pred
        if not needs_private and not needs_public:
            done.append((m, private_pred, public_pred))
            continue

        if is_private_member and private_league and needs_private:
            partner_pred = _get_prediction(partner_id, mid, private_league["id"]) if partner_id else None
            note = f"{partner_nom} уже поставил" if partner_pred else ""
            can_predict.append((m, note, private_pred, public_pred))
        else:
            can_predict.append((m, "", private_pred, public_pred))

    def _pred_str(pred, m) -> str:
        if not pred:
            return "–"
        return fmt_pred_short(pred, m["home_team"], m["away_team"])

    def _league_status(private_pred, public_pred, m) -> str:
        parts = []
        if private_league:
            parts.append(f"{private_league['name']}: {_pred_str(private_pred, m)}")
        if public_league:
            parts.append(f"{public_league['name']}: {_pred_str(public_pred, m)}")
        return " | ".join(parts)

    builder = InlineKeyboardBuilder()
    for m, _, _, _ in can_predict:
        btn_text = f"{flag(m['home_team'])} {m['home_team']} – {flag(m['away_team'])} {m['away_team']}"
        builder.button(text=btn_text, callback_data=f"match_{m['id']}")
    builder.adjust(1)

    lines = []
    if can_predict:
        lines.append("Выбери матч для прогноза:")
        for m, note, priv, pub in can_predict:
            kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
            hint = f"  ({note})" if note else ""
            lines.append(f"  {fmt_match(m['home_team'], m['away_team'])} · {fmt_msk(kickoff)}{hint}")
            lines.append(f"    {_league_status(priv, pub, m)}")
    else:
        lines.append("Нет матчей, на которые можно поставить прямо сейчас.")

    if done:
        lines.append("")
        lines.append("✅ Уже сделано:")
        for m, priv, pub in done:
            kickoff = dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc)
            lines.append(f"  {fmt_match(m['home_team'], m['away_team'])} · {fmt_msk(kickoff)}")
            lines.append(f"    {_league_status(priv, pub, m)}")

    matches_by_id = {m["id"]: m for m in matches}
    kb = builder.as_markup() if can_predict else None
    return "\n".join(lines), kb, matches_by_id


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("predict_"))
async def handle_predict_shortcut(callback: CallbackQuery, state: FSMContext):
    """Button from match reminder notification — jumps straight to that match."""
    match_id = int(callback.data[8:])
    await callback.answer()

    user = _get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Сначала зарегистрируйся: /start")
        return

    leagues = _get_leagues_for_user(user["id"])
    if not leagues:
        await callback.message.answer("Ты не состоишь ни в одной лиге.")
        return

    db = get_db()
    match_data = db.table("matches").select("*").eq("id", match_id).execute().data
    if not match_data:
        await callback.message.answer("Матч не найден.")
        return
    match = match_data[0]

    kickoff = dtparser.parse(match["kickoff_at"]).replace(tzinfo=timezone.utc)
    if now_utc() >= kickoff:
        await callback.message.answer("Приём прогнозов на этот матч уже закрыт.")
        return

    matches = _fetch_window_matches()
    matches_by_id = {m["id"]: m for m in matches}
    if match_id not in matches_by_id:
        matches_by_id[match_id] = match

    await state.update_data(matches_by_id=matches_by_id, match=match, user_id=user["id"], leagues=leagues)
    await _ask_outcome_or_score(callback.message, state, match, kickoff)


@router.message(Command("predict"))
@router.message(F.text == "⚽ Прогноз")
async def cmd_predict(message: Message, state: FSMContext):
    await state.clear()
    user = _get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    leagues = _get_leagues_for_user(user["id"])
    if not leagues:
        await message.answer("Ты не состоишь ни в одной лиге. Попроси у Вани инвайт-ссылку.")
        return

    matches = _fetch_window_matches()
    if not matches:
        await message.answer("Нет предстоящих матчей.")
        return

    text, kb, matches_by_id = _build_match_list(matches, user["id"], leagues, message.from_user.id)
    await state.update_data(matches_by_id=matches_by_id, user_id=user["id"], leagues=leagues)
    await state.set_state(PredictStates.choosing_match)

    if kb:
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text)


@router.callback_query(PredictStates.choosing_match, F.data.startswith("match_"))
async def handle_match_button(callback: CallbackQuery, state: FSMContext):
    match_id = int(callback.data[6:])
    data = await state.get_data()
    matches_by_id = data.get("matches_by_id", {})
    match = matches_by_id.get(match_id)
    if not match:
        await callback.answer("Матч не найден.", show_alert=True)
        return

    await state.update_data(match=match)
    kickoff = dtparser.parse(match["kickoff_at"]).replace(tzinfo=timezone.utc)
    await callback.answer()
    await _ask_outcome_or_score(callback.message, state, match, kickoff)


async def _ask_outcome_or_score(message: Message, state: FSMContext, match: dict, kickoff):
    """For playoff: show 6-outcome keyboard. For group: ask for score directly."""
    header = f"{fmt_match(match['home_team'], match['away_team'])}\n{fmt_msk(kickoff)}\n\n"
    if match["stage"] == "playoff":
        await state.set_state(PredictStates.choosing_outcome)
        await message.answer(
            header + "Выбери исход матча:",
            reply_markup=playoff_outcome_kb(match["home_team"], match["away_team"]),
        )
    else:
        await state.set_state(PredictStates.entering_score)
        await message.answer(header + "Введи счёт (например: 2:1)")


@router.callback_query(PredictStates.choosing_outcome, F.data.startswith("po_"))
async def handle_playoff_outcome(callback: CallbackQuery, state: FSMContext):
    outcome = callback.data[3:]  # P1, P2, NP1, NP2, NPP1, NPP2
    await state.update_data(outcome_type=outcome)
    await callback.answer()

    data = await state.get_data()
    match = data["match"]

    if outcome in ("P1", "P2"):
        winner = match["home_team"] if outcome == "P1" else match["away_team"]
        prompt = f"Введи счёт (победа {winner}, например: 2:1)"
    elif outcome in ("NP1", "NP2"):
        winner = match["home_team"] if outcome == "NP1" else match["away_team"]
        prompt = f"Введи счёт после доп. времени (победа {winner}, например: 3:1)"
    else:  # NPP1, NPP2
        prompt = "Введи счёт после доп. времени (ничья, например: 1:1)"

    await state.set_state(PredictStates.entering_score)
    await callback.message.answer(prompt)


@router.message(PredictStates.entering_score)
async def handle_score_input(message: Message, state: FSMContext):
    text = message.text.strip()
    m = re.match(r"^(\d+)[:\-](\d+)$", text)
    if not m:
        await message.answer("Неверный формат. Введи счёт, например: 2:1")
        return

    home_score = int(m.group(1))
    away_score = int(m.group(2))
    data = await state.get_data()
    match = data["match"]
    outcome = data.get("outcome_type")

    # Validate score against the chosen playoff outcome
    if match["stage"] == "playoff" and outcome:
        if outcome in ("P1", "NP1"):
            if home_score <= away_score:
                winner = match["home_team"]
                await message.answer(f"Для этого исхода счёт должен показывать победу {winner} (левое число больше). Попробуй ещё раз:")
                return
        elif outcome in ("P2", "NP2"):
            if home_score >= away_score:
                winner = match["away_team"]
                await message.answer(f"Для этого исхода счёт должен показывать победу {winner} (правое число больше). Попробуй ещё раз:")
                return
        elif outcome in ("NPP1", "NPP2"):
            if home_score != away_score:
                await message.answer("Для пенальти счёт после доп. времени должен быть ничейным (например, 1:1). Попробуй ещё раз:")
                return

    await state.update_data(home_score=home_score, away_score=away_score)
    await _proceed_to_league_or_confirm(message, state)


async def _proceed_to_league_or_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    leagues = data["leagues"]
    tg_id = message.chat.id

    is_private_member = tg_id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID)
    has_private = any(l["type"] == "private" for l in leagues)
    has_public = any(l["type"] == "public" for l in leagues)

    if is_private_member and has_private and has_public:
        match = data["match"]
        hs, as_ = data["home_score"], data["away_score"]
        outcome = data.get("outcome_type")
        confirm_line = fmt_playoff_confirm(match, hs, as_, outcome)
        await state.set_state(PredictStates.choosing_league)
        await message.answer(
            f"{confirm_line}\nПрименить к:",
            reply_markup=league_choice_kb(),
        )
    else:
        league = leagues[0]
        await state.update_data(selected_leagues=[league["id"]])
        await _show_confirm(message, state)


@router.callback_query(PredictStates.choosing_league, F.data.startswith("league_"))
async def handle_league_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data[7:]
    data = await state.get_data()
    leagues = data["leagues"]

    if choice == "both":
        selected = [l["id"] for l in leagues]
    elif choice == "private":
        selected = [l["id"] for l in leagues if l["type"] == "private"]
    else:
        selected = [l["id"] for l in leagues if l["type"] == "public"]

    await state.update_data(selected_leagues=selected)
    await callback.answer()
    await _show_confirm(callback.message, state)


async def _show_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    match = data["match"]
    hs = data["home_score"]
    as_ = data["away_score"]
    outcome = data.get("outcome_type")

    score_str = fmt_playoff_confirm(match, hs, as_, outcome)

    leagues = data["leagues"]
    selected = data.get("selected_leagues", [])
    league_names = [l["name"] for l in leagues if l["id"] in selected]
    league_str = " + ".join(league_names) if league_names else "лига"

    await state.set_state(PredictStates.confirming)
    await message.answer(
        f"{score_str}\nЛига: {league_str}\n\nВсё верно?",
        reply_markup=confirm_prediction_kb(match["home_team"], match["away_team"], hs, as_),
    )


@router.callback_query(PredictStates.confirming, F.data == "pred_confirm")
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db = get_db()
    user_id = data["user_id"]
    match = data["match"]
    hs = data["home_score"]
    as_ = data["away_score"]
    outcome = data.get("outcome_type")
    selected_leagues = data["selected_leagues"]

    saved_leagues = []

    for league_id in selected_leagues:
        if _get_prediction(user_id, match["id"], league_id):
            continue

        league = next((l for l in data["leagues"] if l["id"] == league_id), None)
        if league and league["type"] == "private":
            vanya_id, nik_id = _get_vanya_nik_ids()
            partner_id = nik_id if user_id == vanya_id else vanya_id
            partner_pred = _get_prediction(partner_id, match["id"], league_id) if partner_id else None

            if partner_pred and partner_pred["home_score"] == hs and partner_pred["away_score"] == as_:
                assignment_first_id = _get_assignment(match["id"])
                i_am_first = (assignment_first_id == user_id) if assignment_first_id else True
                my_name = "Ваня" if user_id == vanya_id else "Ник"
                partner_name = "Ник" if user_id == vanya_id else "Ваня"
                partner_tg = NIK_TELEGRAM_ID if user_id == vanya_id else VANYA_TELEGRAM_ID
                match_str = fmt_match(match["home_team"], match["away_team"])

                if not i_am_first:
                    await callback.answer(
                        f"🚫 {partner_name} уже поставил {hs}:{as_} — выбери другой счёт!",
                        show_alert=True,
                    )
                    try:
                        db.table("blocked_attempts").upsert(
                            {"match_id": match["id"], "user_id": user_id},
                            on_conflict="match_id,user_id",
                        ).execute()
                    except Exception:
                        pass
                    try:
                        await callback.bot.send_message(
                            partner_tg,
                            f"🤫 {my_name} хотел поставить тот же счёт, что и ты "
                            f"({hs}:{as_}) на {match_str}! Придётся ему выбрать другой.",
                        )
                    except Exception:
                        pass
                    await state.set_state(PredictStates.entering_score)
                    await callback.message.answer("Введи другой счёт:")
                    return
                else:
                    try:
                        db.table("predictions").delete() \
                            .eq("user_id", partner_id) \
                            .eq("match_id", match["id"]) \
                            .eq("league_id", league_id) \
                            .execute()
                    except Exception:
                        pass
                    partner_gen = "Ника" if user_id == vanya_id else "Вани"
                    try:
                        await callback.bot.send_message(
                            partner_tg,
                            f"🚫 {my_name} поставил {hs}:{as_} на {match_str} — этот счёт теперь занят.\n"
                            f"Тебе нужно сделать прогноз заново (выбери другой счёт).",
                        )
                    except Exception:
                        pass
                    try:
                        await callback.message.answer(
                            f"🤫 У {partner_gen} стоял тот же счёт ({hs}:{as_}) на {match_str} — "
                            f"ты первый по жребию, его прогноз аннулирован. "
                            f"Ему нужно выбрать другой счёт.",
                        )
                    except Exception:
                        pass

        db.table("predictions").insert({
            "user_id": user_id,
            "match_id": match["id"],
            "league_id": league_id,
            "home_score": hs,
            "away_score": as_,
            "outcome_type": outcome,
        }).execute()
        saved_leagues.append(league_id)

    await callback.answer()
    await state.clear()

    if saved_leagues:
        await callback.message.answer("✅ Прогноз сохранён!")
        await _notify_partner_if_first(callback, data, saved_leagues)
    else:
        await callback.message.answer("Прогноз на этот матч уже был сохранён ранее.")


async def _notify_partner_if_first(callback: CallbackQuery, data: dict, saved_league_ids: list):
    user_id = data["user_id"]
    match = data["match"]

    for league_id in saved_league_ids:
        league = next((l for l in data["leagues"] if l["id"] == league_id), None)
        if not league or league["type"] != "private":
            continue

        vanya_id, nik_id = _get_vanya_nik_ids()
        if not vanya_id or not nik_id:
            continue

        partner_id = nik_id if user_id == vanya_id else vanya_id
        partner_pred = _get_prediction(partner_id, match["id"], league_id)
        match_str = fmt_match(match["home_team"], match["away_team"])
        my_name = "Ваня" if user_id == vanya_id else "Ник"
        partner_tg = NIK_TELEGRAM_ID if user_id == vanya_id else VANYA_TELEGRAM_ID

        if not partner_pred:
            try:
                await callback.bot.send_message(
                    partner_tg,
                    f"⚽ {my_name} сделал прогноз на {match_str}.\nТвой ход!",
                )
            except Exception:
                pass
        else:
            first_uid = _get_assignment(match["id"])
            vanya_pred = _get_prediction(vanya_id, match["id"], league_id)
            nik_pred = _get_prediction(nik_id, match["id"], league_id)
            vanya_score = fmt_pred_short(vanya_pred, match["home_team"], match["away_team"]) if vanya_pred else "–"
            nik_score = fmt_pred_short(nik_pred, match["home_team"], match["away_team"]) if nik_pred else "–"

            if first_uid == vanya_id:
                scores_lines = f"Ваня: {vanya_score}\nНик: {nik_score}"
            else:
                scores_lines = f"Ник: {nik_score}\nВаня: {vanya_score}"

            reveal = (
                f"🎲 Оба брата поставили на {match_str}!\n\n"
                f"{scores_lines}\n\n"
                f"Ждём игры с нетерпением! 🔥"
            )
            for tg_id in (VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID):
                try:
                    await callback.bot.send_message(tg_id, reveal)
                except Exception:
                    pass


@router.callback_query(PredictStates.confirming, F.data == "pred_cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    match = data.get("match", {})
    if match.get("stage") == "playoff":
        await state.set_state(PredictStates.choosing_outcome)
        await callback.message.answer(
            "Выбери исход матча заново:",
            reply_markup=playoff_outcome_kb(match["home_team"], match["away_team"]),
        )
    else:
        await state.set_state(PredictStates.entering_score)
        await callback.message.answer("Введи счёт заново (например: 2:1):")
