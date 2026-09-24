import html

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlmodel import Session

from app.bot import keyboards as kb
from app.bot.i18n import APPLICATION_TYPES, all_langs, fmt_dt, signal_status, stage, t
from app.bot.states import StatusQuery
from app.bot.util import db_call, get_lang
from app.models import Parcel
from app.services import applications, signals

router = Router(name="status")
fallback_router = Router(name="fallback")


def _signal_view(session: Session, code: str) -> tuple | None:
    signal = signals.get_by_code(session, code)
    if signal is None:
        return None
    parcel = session.get(Parcel, signal.parcel_id) if signal.parcel_id else None
    return signal, parcel.cadastral_no if parcel else None


def signal_place(lang: str, lat: float, lon: float, cadastral_no: str | None) -> str:
    if cadastral_no:
        return t(lang, "place_parcel", cad=html.escape(cadastral_no))
    return t(lang, "place_point", lat=lat, lon=lon)


async def answer_status(message: Message, lang: str, kind: str, code: str) -> None:
    if kind == "application":
        app = await db_call(applications.find, code)
        if app is None:
            await message.answer(t(lang, "application_not_found", code=code), reply_markup=kb.main_menu(lang))
            return
        emoji, stage_name = stage(lang, app.stage)
        text = t(lang, "application_card", code=app.track_no, type=APPLICATION_TYPES[lang][app.type],
                 emoji=emoji, stage=stage_name, note=html.escape(app.note_kz if lang == "kz" else app.note_ru),
                 updated=fmt_dt(app.updated_at))
        subscribed = await db_call(applications.is_subscribed, app.track_no, message.chat.id)
        await message.answer(text, reply_markup=kb.subscription(lang, app.track_no, subscribed))
        return
    else:
        view = await db_call(_signal_view, code)
        if view is None:
            await message.answer(t(lang, "signal_not_found", code=code), reply_markup=kb.main_menu(lang))
            return
        signal, cadastral_no = view
        emoji, status_name, hint = signal_status(lang, signal.status)
        text = t(lang, "signal_card", code=signal.code, place=signal_place(lang, signal.lat, signal.lon, cadastral_no),
                 emoji=emoji, status=status_name, hint=hint, updated=fmt_dt(signal.updated_at))
    await message.answer(text, reply_markup=kb.main_menu(lang))


@router.callback_query(F.data.startswith("sub:") | F.data.startswith("unsub:"))
async def toggle_subscription(callback: CallbackQuery) -> None:
    lang = await get_lang(callback.message.chat.id) or "ru"
    action, code = callback.data.split(":", 1)
    if action == "sub":
        await db_call(applications.subscribe, code, callback.message.chat.id, lang)
    else:
        await db_call(applications.unsubscribe, code, callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=kb.subscription(lang, code, action == "sub"))
    await callback.answer(t(lang, "subscribed" if action == "sub" else "unsubscribed", code=code), show_alert=False)


@router.message(Command("status"))
@router.message(F.text.in_(all_langs("btn_status")))
async def ask_code(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.chat.id) or "ru"
    await state.set_state(StatusQuery.code)
    await message.answer(t(lang, "status_ask"), reply_markup=kb.main_menu(lang))


MENU_BUTTONS = set().union(*(all_langs(k) for k in ("btn_status", "btn_kb", "btn_report", "btn_lang", "btn_cancel")))


@router.message(StatusQuery.code, F.text, ~F.text.in_(MENU_BUTTONS))
async def got_code(message: Message, state: FSMContext) -> None:
    lang = await get_lang(message.chat.id) or "ru"
    parsed = applications.normalize_code(message.text)
    if parsed is None:
        await message.answer(t(lang, "status_bad_format"))
        return
    await state.clear()
    await answer_status(message, lang, *parsed)


@fallback_router.message(StateFilter(None), F.text)
async def free_text(message: Message) -> None:
    """Номер можно прислать без нажатия кнопок — бот сам его узнает."""
    lang = await get_lang(message.chat.id) or "ru"
    parsed = applications.normalize_code(message.text)
    if parsed:
        await answer_status(message, lang, *parsed)
    else:
        await message.answer(t(lang, "menu_hint"), reply_markup=kb.main_menu(lang))


@fallback_router.message(StateFilter(None))
async def anything_else(message: Message) -> None:
    lang = await get_lang(message.chat.id) or "ru"
    await message.answer(t(lang, "menu_hint"), reply_markup=kb.main_menu(lang))
