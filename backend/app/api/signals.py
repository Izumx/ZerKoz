from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import signals

router = APIRouter(tags=["signals"])


class SignalPatch(BaseModel):
    status: str
    violation_type: str | None = None


@router.get("/signals")
def list_signals(status: str | None = None, session: Session = Depends(get_session)) -> list[dict]:
    return signals.list_signals(session, status)


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int, session: Session = Depends(get_session)) -> dict:
    return signals.signal_dict(session, signals.get_signal(session, signal_id))


@router.patch("/signals/{signal_id}")
def patch_signal(signal_id: int, body: SignalPatch, session: Session = Depends(get_session)) -> dict:
    signal = signals.set_status(session, signal_id, body.status, body.violation_type)
    return signals.signal_dict(session, signal)
