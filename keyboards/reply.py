from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚽ Прогноз"), KeyboardButton(text="📅 Ближайшие")],
            [KeyboardButton(text="🏆 Таблица"), KeyboardButton(text="📋 История")],
        ],
        resize_keyboard=True,
        persistent=True,
    )
