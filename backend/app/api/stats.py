from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session

from app.db import get_session
from app.services import stats

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(session: Session = Depends(get_session)) -> dict:
    return stats.dashboard(session)


@router.get("/export/parcels.csv")
def export_csv(session: Session = Depends(get_session)) -> Response:
    return Response(
        stats.parcels_csv(session),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zherkoz-parcels.csv"'},
    )
