from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import applications

router = APIRouter(tags=["applications"])


class ApplicationPatch(BaseModel):
    stage: str | None = None
    note_ru: str | None = None
    note_kz: str | None = None


def _track(raw: str) -> str:
    parsed = applications.normalize_code(raw)
    if not parsed or parsed[0] != "application":
        raise HTTPException(404, "Заявление не найдено")
    return parsed[1]


@router.get("/applications")
def list_applications(session: Session = Depends(get_session)) -> list[dict]:
    return applications.list_all(session)


@router.get("/applications/{track_no}")
def get_application(track_no: str, session: Session = Depends(get_session)) -> dict:
    return applications.application_dict(applications.get(session, _track(track_no)))


@router.patch("/applications/{track_no}")
def patch_application(track_no: str, body: ApplicationPatch, session: Session = Depends(get_session)) -> dict:
    track = _track(track_no)
    app = applications.update(session, track, **body.model_dump(exclude_unset=True))
    return applications.application_dict(app, applications.subscriber_counts(session).get(track, 0))
