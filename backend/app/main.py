"""Точка входа: python -m app.main (веб-панель + API + Telegram-бот в одном процессе)."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.config import settings
from app.db import init_db
from app.services import NotFound, ServiceError
from app.services.photos import PhotoError

log = logging.getLogger("zherkoz")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    bot_task = None
    if settings.bot_token:
        from app.bot.runner import run_bot

        bot_task = asyncio.create_task(run_bot(settings.bot_token))
    else:
        log.warning("BOT_TOKEN не задан — Telegram-бот не запущен, работает только веб-панель")
    yield
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(title="ЖерКөз API", version="1.0", lifespan=lifespan)


@app.exception_handler(NotFound)
async def _not_found(_: Request, exc: NotFound):
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(PhotoError)
async def _bad_photo(_: Request, exc: PhotoError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(ServiceError)
async def _conflict(_: Request, exc: ServiceError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


app.include_router(api_router)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
if settings.frontend_dist.exists():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def _no_frontend() -> dict:
        return {"detail": "Фронтенд не собран: выполните `npm run build` в папке frontend. API: /docs"}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
