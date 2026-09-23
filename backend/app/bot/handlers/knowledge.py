from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards as kb
from app.bot.i18n import all_langs, t
from app.bot.knowledge import ARTICLES
from app.bot.util import get_lang

router = Router(name="knowledge")


@router.message(Command("help"))
@router.message(F.text.in_(all_langs("btn_kb")))
async def knowledge_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = await get_lang(message.chat.id) or "ru"
    await message.answer(t(lang, "kb_intro"), reply_markup=kb.knowledge_menu(lang))


@router.callback_query(F.data.startswith("kb:"))
async def knowledge_article(callback: CallbackQuery) -> None:
    lang = await get_lang(callback.message.chat.id) or "ru"
    key = callback.data.split(":", 1)[1]
    if key in ARTICLES:
        await callback.message.edit_text(ARTICLES[key][lang]["body"], reply_markup=kb.knowledge_article(lang),
                                         disable_web_page_preview=True)
    else:
        await callback.message.edit_text(t(lang, "kb_intro"), reply_markup=kb.knowledge_menu(lang))
    await callback.answer()
