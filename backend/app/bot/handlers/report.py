"""«Народный контроль»: геолокация → фото (1–3) → описание → подтверждение."""
import asyncio
import html
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot.i18n import all_langs, t
from app.bot.states import Report
from app.bot.util import db_call, get_lang, parse_coords
from app.services import geo, signals

router = Router(name="report")
MAX_PHOTOS = 3
MAX_DESCRIPTION = 500
_photo_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)  # альбом приходит несколькими апдейтами сразу

is_image = F.photo | F.document.mime_type.startswith("image/")


async def _lang(message: Message) -> str:
    return await get_lang(message.chat.id) or "ru"


@router.message(Command("report"))
@router.message(F.text.in_(all_langs("btn_report")))
async def start_report(message: Message, state: FSMContext) -> None:
    lang = await _lang(message)
    await state.clear()
    await state.set_state(Report.location)
    await message.answer(t(lang, "report_intro"), reply_markup=kb.send_location(lang))


async def _accept_location(message: Message, state: FSMContext, lat: float, lon: float) -> None:
    lang = await _lang(message)
    parcel = await db_call(geo.find_parcel, lat=lat, lon=lon)
    place = t(lang, "place_parcel", cad=parcel.cadastral_no) if parcel else t(lang, "report_outside")
    await state.update_data(lat=lat, lon=lon, place=place, photos=[])
    await state.set_state(Report.photo)
    await message.answer(t(lang, "report_location_ok", place=place), reply_markup=kb.cancel_only(lang))


@router.message(Report.location, F.location)
async def got_location(message: Message, state: FSMContext) -> None:
    await _accept_location(message, state, message.location.latitude, message.location.longitude)


@router.message(Report.location, F.text)
async def got_location_text(message: Message, state: FSMContext) -> None:
    coords = parse_coords(message.text)
    if coords is None:
        lang = await _lang(message)
        await message.answer(t(lang, "report_need_location"), reply_markup=kb.send_location(lang))
        return
    await _accept_location(message, state, *coords)


@router.message(Report.location)
async def location_expected(message: Message) -> None:
    lang = await _lang(message)
    await message.answer(t(lang, "report_need_location"), reply_markup=kb.send_location(lang))


async def _ask_description(message: Message, state: FSMContext) -> None:
    lang = await _lang(message)
    await state.set_state(Report.description)
    await message.answer(t(lang, "report_ask_description"), reply_markup=kb.cancel_only(lang))


@router.message(Report.photo, is_image)
async def got_photo(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    async with _photo_locks[message.chat.id]:
        photos = (await state.get_data()).get("photos", [])
        if len(photos) >= MAX_PHOTOS:
            return
        photos = photos + [file_id]
        await state.update_data(photos=photos)
    if len(photos) >= MAX_PHOTOS:
        await _ask_description(message, state)
    else:
        lang = await _lang(message)
        await message.answer(t(lang, "report_photo_ok", n=len(photos)), reply_markup=kb.photos_done(lang))


@router.message(Report.photo, F.text.in_(all_langs("btn_done")))
async def photos_done(message: Message, state: FSMContext) -> None:
    if (await state.get_data()).get("photos"):
        await _ask_description(message, state)
    else:
        await message.answer(t(await _lang(message), "report_need_photo"))


@router.message(Report.photo)
async def photo_expected(message: Message) -> None:
    await message.answer(t(await _lang(message), "report_need_photo"))


async def _show_confirm(message: Message, state: FSMContext) -> None:
    lang = await _lang(message)
    data = await state.get_data()
    await message.answer(
        t(lang, "report_confirm", place=data["place"], n=len(data["photos"]),
          description=html.escape(data["description"])),
        reply_markup=kb.confirm(lang),
    )


@router.message(Report.description, F.text)
async def got_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip()[:MAX_DESCRIPTION])
    await state.set_state(Report.confirm)
    await _show_confirm(message, state)


@router.message(Report.description)
async def description_expected(message: Message) -> None:
    await message.answer(t(await _lang(message), "report_need_text"))


@router.message(Report.confirm)
async def confirm_expected(message: Message, state: FSMContext) -> None:
    await _show_confirm(message, state)


@router.callback_query(Report.confirm, F.data == "report:submit")
async def submit(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    message = callback.message
    lang = await _lang(message)
    data = await state.get_data()
    await state.clear()  # защита от двойного нажатия
    await message.edit_reply_markup(reply_markup=None)
    await callback.answer(t(lang, "report_sending"))
    photos = [(await bot.download(file_id)).read() for file_id in data["photos"]]
    signal = await db_call(
        signals.create_signal, lat=data["lat"], lon=data["lon"], description=data["description"],
        source="telegram", tg_chat_id=message.chat.id, lang=lang, photos=photos,
    )
    await message.answer(t(lang, "report_sent", code=signal.code), reply_markup=kb.main_menu(lang))


@router.callback_query(F.data.in_({"report:submit", "report:cancel"}))
async def cancel_or_stale(callback: CallbackQuery, state: FSMContext) -> None:
    lang = await _lang(callback.message)
    await callback.message.edit_reply_markup(reply_markup=None)
    if callback.data == "report:cancel" and await state.get_state() == Report.confirm.state:
        await state.clear()
        await callback.message.answer(t(lang, "cancelled"), reply_markup=kb.main_menu(lang))
    await callback.answer()
