from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bot.i18n import t
from app.bot.knowledge import ARTICLES, EGOV


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_status"))],
            [KeyboardButton(text=t(lang, "btn_report"))],
            [KeyboardButton(text=t(lang, "btn_kb")), KeyboardButton(text=t(lang, "btn_lang"))],
        ],
        resize_keyboard=True,
        input_field_placeholder="KZ-2026-042",
    )


def language() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
    ]])


def knowledge_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=article[lang]["title"], callback_data=f"kb:{key}")]
        for key, article in ARTICLES.items()
    ])


def knowledge_article(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_egov"), url=EGOV[lang])],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="kb:menu")],
    ])


def cancel_only(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(lang, "btn_cancel"))]], resize_keyboard=True)


def send_location(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_send_location"), request_location=True)],
            [KeyboardButton(text=t(lang, "btn_cancel"))],
        ],
        resize_keyboard=True,
    )


def photos_done(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_done")), KeyboardButton(text=t(lang, "btn_cancel"))]],
        resize_keyboard=True,
    )


def confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_submit"), callback_data="report:submit"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="report:cancel"),
    ]])
