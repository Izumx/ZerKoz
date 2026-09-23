"""Сквозной тест бота без сети: апдейты подаются в Dispatcher, запросы к Telegram перехватываются."""
import asyncio
import io
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetFile, TelegramMethod
from aiogram.types import CallbackQuery, Chat, File, Location, Message, PhotoSize, Update, User
from PIL import Image
from sqlmodel import select

from app.bot import runner
from app.bot.handlers import build_router
from app.models import Application, Photo, Signal
from app.services import notify, signals
from tests.factories import make_parcel

CHAT = Chat(id=4242, type="private")
USER = User(id=4242, is_bot=False, first_name="Айгерим")


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), "brown").save(buf, "JPEG")
    return buf.getvalue()


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):
        self.sent.append(method)
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path="photos/p.jpg")
        returning = method.__returning__
        if returning is bool:
            return True
        return Message(message_id=len(self.sent), date=datetime.now(), chat=CHAT, text=getattr(method, "text", None))

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield jpeg()

    async def close(self):
        pass

    def texts(self) -> list[str]:
        return [m.text for m in self.sent if getattr(m, "text", None)]


_dispatcher: Dispatcher | None = None


def dispatcher() -> Dispatcher:
    """Роутеры aiogram подключаются к диспетчеру один раз — общий на все тесты."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(storage=MemoryStorage())
        _dispatcher.include_router(build_router())
    return _dispatcher


class Harness:
    def __init__(self):
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session)
        self.dp = dispatcher()
        self.n = 0

    def _message(self, **kw) -> Message:
        self.n += 1
        return Message(message_id=self.n, date=datetime.now(), chat=CHAT, from_user=USER, **kw)

    async def send(self, **kw):
        await self.dp.feed_update(self.bot, Update(update_id=self.n + 1, message=self._message(**kw)))

    async def press(self, data: str):
        self.n += 1
        cb = CallbackQuery(id=str(self.n), from_user=USER, chat_instance="c", data=data,
                           message=self._message(text="кнопки"))
        await self.dp.feed_update(self.bot, Update(update_id=self.n + 1, callback_query=cb))

    def last(self) -> str:
        return self.session.texts()[-1]


def test_citizen_report_flow_end_to_end(session):
    parcel = make_parcel(session, lon=71.36, lat=42.90)
    session.add(Application(track_no="KZ-2026-042", applicant="И.", type="izhs", stage="inspection",
                            note_ru="Выезд 25.09", note_kz="Шығу 25.09"))
    session.commit()

    async def scenario():
        h = Harness()
        await h.send(text="/start")
        assert "Выберите язык" in h.last()
        await h.press("lang:ru")
        assert "ЖерКөз" in h.last()

        # статус заявления — номер можно прислать сразу, в свободной форме
        await h.send(text="kz 2026 42")
        assert "Назначен выезд инспектора" in h.last() and "Выезд 25.09" in h.last()

        # база знаний
        await h.send(text="📚 База знаний")
        await h.press("kb:izhs")
        assert any("ИЖС" in (getattr(m, "text", "") or "") for m in h.session.sent[-3:])

        # народный контроль
        await h.send(text="🚨 Народный контроль")
        assert "Шаг 1/3" in h.last()
        await h.send(text="что-то не то")
        assert "Нужна геолокация" in h.last()
        await h.send(location=Location(latitude=42.905, longitude=71.365))
        assert parcel.cadastral_no in h.last() and "Шаг 2/3" in h.last()
        await h.send(photo=[PhotoSize(file_id="ph1", file_unique_id="u1", width=16, height=16)])
        assert "1/3" in h.last()
        await h.send(text="✅ Готово")
        assert "Шаг 3/3" in h.last()
        await h.send(text="Свалка <мусора>")
        assert "Свалка &lt;мусора&gt;" in h.last()
        await h.press("report:submit")
        assert "SIG-0001" in h.last() and "принят" in h.last()

        # уведомление жителю при смене статуса инспектором
        notify.set_notifier(runner.make_notifier(h.bot, asyncio.get_running_loop()))
        try:
            await asyncio.to_thread(_confirm_signal)
            await asyncio.sleep(0.05)
            assert "Нарушение подтверждено" in h.last()
        finally:
            notify.set_notifier(None)

    asyncio.run(scenario())

    signal = session.exec(select(Signal)).one()
    assert signal.tg_chat_id == CHAT.id and signal.parcel_id == parcel.id
    assert signal.description == "Свалка <мусора>"
    assert session.exec(select(Photo).where(Photo.signal_id == signal.id)).one().source == "citizen"


def _confirm_signal():
    from app import db

    with db.new_session() as s:
        signals.set_status(s, 1, "confirmed")


def test_menu_button_interrupts_status_input(session):
    async def scenario():
        h = Harness()
        await h.send(text="/start")
        await h.press("lang:kz")
        await h.send(text="📄 Өтініш мәртебесі")
        await h.send(text="🚨 Халықтық бақылау")  # не должно распознаться как «неверный номер»
        assert "1/3-қадам" in h.last()
        await h.send(text="❌ Болдырмау")
        assert "басты мәзірдесіз" in h.last()

    asyncio.run(scenario())
