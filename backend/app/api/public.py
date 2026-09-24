"""Публичное API для Telegram Mini App жителей (без входа инспектора)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.services import botusers, webapp

router = APIRouter(prefix="/public", tags=["public"])


class InitData(BaseModel):
    init_data: str


@router.get("/signals")
def public_signals(session: Session = Depends(get_session)) -> list[dict]:
    return webapp.public_signals(session)


@router.post("/my-signals")
def my_signals(body: InitData, session: Session = Depends(get_session)) -> dict:
    user = webapp.validate_init_data(body.init_data, settings.bot_token)
    if user is None or "id" not in user:
        raise HTTPException(401, "Откройте карту из Telegram-бота")
    lang = botusers.get_lang(session, user["id"]) or ("kz" if user.get("language_code") == "kk" else "ru")
    return {"lang": lang, "first_name": user.get("first_name", ""), "signals": webapp.my_signals(session, user["id"])}
