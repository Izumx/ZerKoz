from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.services import photos

router = APIRouter(tags=["media"])


@router.get("/media/{name}")
def media(name: str, session: Session = Depends(get_session)) -> Response:
    found = photos.load(session, name)
    if found is None:
        raise HTTPException(404, "Фото не найдено")
    data, content_type = found
    return Response(data, media_type=content_type, headers={"Cache-Control": "private, max-age=86400, immutable"})
