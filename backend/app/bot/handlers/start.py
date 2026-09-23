from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot.i18n import all_langs, t
from app.bot.util import get_lang, set_lang

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.chat.id)
    if lang is None:
        await message.answer(t("ru", "choose_lang"), reply_markup=kb.language())
        return
    await message.answer(t(lang, "welcome"), reply_markup=kb.main_menu(lang))


@router.message(Command("lang"))
@router.message(F.text.in_(all_langs("btn_lang")))
async def ask_language(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.chat.id) or "ru"
    await message.answer(t(lang, "choose_lang"), reply_markup=kb.language())


@router.callback_query(F.data.in_({"lang:ru", "lang:kz"}))
async def choose_language(callback: CallbackQuery) -> None:
    lang = callback.data.split(":")[1]
    await set_lang(callback.message.chat.id, lang)
    await callback.message.edit_text("🇰🇿 Қазақша ✅" if lang == "kz" else "🇷🇺 Русский ✅")
    await callback.message.answer(t(lang, "welcome"), reply_markup=kb.main_menu(lang))
    await callback.answer()


@router.message(Command("cancel"))
@router.message(F.text.in_(all_langs("btn_cancel")))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.chat.id) or "ru"
    await message.answer(t(lang, "cancelled"), reply_markup=kb.main_menu(lang))
