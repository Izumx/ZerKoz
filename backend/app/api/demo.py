from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.seed.simulate import simulate_signal
from app.services import signals

router = APIRouter(tags=["demo"])


@router.post("/demo/signal")
def demo_signal(session: Session = Depends(get_session)) -> dict:
    """Создать симулированный сигнал жителя (страховка для демонстрации)."""
    return signals.signal_dict(session, simulate_signal(session))
