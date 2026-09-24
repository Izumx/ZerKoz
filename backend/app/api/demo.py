from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.seed.simulate import simulate_signal
from app.services import route, signals

router = APIRouter(tags=["demo"])


@router.post("/demo/signal")
def demo_signal(session: Session = Depends(get_session)) -> dict:
    """Создать симулированный сигнал жителя (страховка для демонстрации). Отключается DEMO_MODE=false."""
    if not settings.demo_mode:
        raise HTTPException(404, "Демо-режим выключен")
    return signals.signal_dict(session, simulate_signal(session))


@router.get("/route")
def route_plan(session: Session = Depends(get_session)) -> dict:
    """Маршрут выезда: просроченные нарушения, участки на проверке, сигналы вне участков."""
    return route.plan(session)
