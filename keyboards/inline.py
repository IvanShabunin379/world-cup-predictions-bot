from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_prediction_kb(home: str, away: str, home_score: int, away_score: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data="pred_confirm")
    builder.button(text="✏️ Изменить", callback_data="pred_cancel")
    builder.adjust(2)
    return builder.as_markup()


def league_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Обеим лигам", callback_data="league_both")
    builder.button(text="Только личному", callback_data="league_private")
    builder.button(text="Только общему", callback_data="league_public")
    builder.adjust(1)
    return builder.as_markup()


def playoff_outcome_kb(team1: str, team2: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"НП1: доп. вр., {team1}", callback_data="po_NP1")
    builder.button(text=f"НП2: доп. вр., {team2}", callback_data="po_NP2")
    builder.button(text=f"НПП1: пен., {team1}", callback_data="po_NPP1")
    builder.button(text=f"НПП2: пен., {team2}", callback_data="po_NPP2")
    builder.adjust(2)
    return builder.as_markup()


def predict_match_kb(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚽ Сделать прогноз", callback_data=f"predict_{match_id}")
    return builder.as_markup()


def standings_league_kb(has_private: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_private:
        builder.button(text="Личная лига", callback_data="standings_private")
    builder.button(text="Общая лига", callback_data="standings_public")
    builder.adjust(1)
    return builder.as_markup()
