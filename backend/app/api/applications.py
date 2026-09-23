from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.services import applications

router = APIRouter(tags=["applications"])


@router.get("/applications/{track_no}")
def get_application(track_no: str, session: Session = Depends(get_session)) -> dict:
    parsed = applications.normalize_code(track_no)
    app = applications.find(session, parsed[1]) if parsed and parsed[0] == "application" else None
    if app is None:
        raise HTTPException(404, "Заявление не найдено")
    return {
        "track_no": app.track_no,
        "type": app.type,
        "stage": app.stage,
        "note_ru": app.note_ru,
        "note_kz": app.note_kz,
        "updated_at": app.updated_at.isoformat(),
    }
