from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.bot.i18n import t
from app.config import settings
from app.bot.knowledge import ARTICLES, EGOV


def webapp_url(lang: str) -> str | None:
    """Mini App открывается только по https — есть лишь при публичном адресе сервиса."""
    return f"{settings.webhook_base}/?tg=1&lang={lang}" if settings.webhook_base.startswith("https://") else None


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "btn_status"))],
        [KeyboardButton(text=t(lang, "btn_report"))],
        [KeyboardButton(text=t(lang, "btn_kb")), KeyboardButton(text=t(lang, "btn_lang"))],
    ]
    if url := webapp_url(lang):
        rows.insert(2, [KeyboardButton(text=t(lang, "btn_map"), web_app=WebAppInfo(url=url))])
    return ReplyKeyboardMarkup(
        keyboard=rows,
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


def knowledge_article(lang: str, key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_egov"), url=ARTICLES[key][lang].get("url", EGOV[lang]))],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="kb:menu")],
    ])


def subscription(lang: str, track_no: str, subscribed: bool) -> InlineKeyboardMarkup:
    if subscribed:
        button = InlineKeyboardButton(text=t(lang, "btn_unsubscribe"), callback_data=f"unsub:{track_no}")
    else:
        button = InlineKeyboardButton(text=t(lang, "btn_subscribe"), callback_data=f"sub:{track_no}")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


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
