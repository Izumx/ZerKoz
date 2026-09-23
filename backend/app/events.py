"""Шина событий внутри процесса → Server-Sent Events.

publish() можно вызывать из любого потока (FastAPI выполняет sync-эндпоинты в threadpool).
"""
import asyncio
import threading
from contextlib import contextmanager


class Subscription:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.queue: asyncio.Queue[dict] = asyncio.Queue()

    async def get(self, timeout: float) -> dict | None:
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except asyncio.TimeoutError:
            return None


class EventBus:
    def __init__(self) -> None:
        self._subs: set[Subscription] = set()
        self._lock = threading.Lock()

    def publish(self, type_: str, data: dict) -> None:
        message = {"type": type_, "data": data}
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, message)
            except RuntimeError:  # цикл событий уже закрыт
                pass

    @contextmanager
    def subscription(self):
        sub = Subscription()
        with self._lock:
            self._subs.add(sub)
        try:
            yield sub
        finally:
            with self._lock:
                self._subs.discard(sub)


bus = EventBus()
