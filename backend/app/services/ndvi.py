"""Реальный NDVI участка по снимкам Sentinel-2 L2A (Copernicus Data Space Ecosystem, Statistical API).

Нужны бесплатные ключи OAuth-клиента CDSE: COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET
(dataspace.copernicus.eu → User settings → OAuth clients). Облака, тени, снег и вода маскируются по слою SCL.
"""
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.events import bus
from app.models import Parcel, utcnow
from app.services import ServiceError, history
from app.timeutil import today_kz

log = logging.getLogger(__name__)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
# в документации CDSE встречаются разные пути — пробуем по очереди
STATS_URLS = (
    "https://sh.dataspace.copernicus.eu/api/v1/statistics",
    "https://sh.dataspace.copernicus.eu/statistics/v1",
)
LOW_NDVI_PEAK = 0.25
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04", "B08", "SCL", "dataMask"]}],
    output: [{id: "ndvi", bands: 1, sampleType: "FLOAT32"}, {id: "dataMask", bands: 1}]
  };
}
function evaluatePixel(s) {
  // 3 — тени, 6 — вода, 8/9/10 — облака, 11 — снег
  var clear = [3, 6, 8, 9, 10, 11].indexOf(s.SCL) === -1 ? 1 : 0;
  var sum = s.B08 + s.B04;
  var ndvi = sum === 0 ? 0 : (s.B08 - s.B04) / sum;
  return {ndvi: [ndvi], dataMask: [s.dataMask * clear * (sum === 0 ? 0 : 1)]};
}"""

_token: tuple[str, float] | None = None


class NdviError(ServiceError):
    pass


def enabled() -> bool:
    return bool(settings.copernicus_client_id and settings.copernicus_client_secret)


def _access_token(client: httpx.Client) -> str:
    global _token
    if _token and _token[1] > time.time() + 60:
        return _token[0]
    r = client.post(TOKEN_URL, data={"grant_type": "client_credentials",
                                     "client_id": settings.copernicus_client_id,
                                     "client_secret": settings.copernicus_client_secret})
    if r.status_code != 200:
        raise NdviError(f"Copernicus: не удалось получить токен ({r.status_code})")
    body = r.json()
    _token = (body["access_token"], time.time() + body.get("expires_in", 600))
    return _token[0]


def _months_range() -> tuple[datetime, datetime]:
    today = today_kz()
    y, m = divmod(today.year * 12 + today.month - 1 - 11, 12)
    start = datetime(y, m + 1, 1, tzinfo=timezone.utc)
    end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def fetch_series(geometry: dict) -> tuple[list[str], list[float | None]]:
    """Средний NDVI по месяцам за последние 12 месяцев. None — месяц без безоблачных снимков."""
    if not enabled():
        raise NdviError("Интеграция с Copernicus не настроена")
    start, end = _months_range()
    body = {
        "input": {
            "bounds": {"geometry": geometry, "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 80}}],
        },
        "aggregation": {
            "timeRange": {"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")},
            "aggregationInterval": {"of": "P1M"},
            "evalscript": EVALSCRIPT,
            "resx": 0.0001,  # ~10 м в градусах
            "resy": 0.0001,
        },
    }
    with httpx.Client(timeout=60) as client:
        headers = {"Authorization": f"Bearer {_access_token(client)}"}
        response = None
        for url in STATS_URLS:
            response = client.post(url, json=body, headers=headers)
            if response.status_code != 404:
                break
        if response.status_code != 200:
            raise NdviError(f"Copernicus Statistical API: {response.status_code} {response.text[:200]}")
    by_month: dict[str, float | None] = {}
    for item in response.json().get("data", []):
        month = item["interval"]["from"][:7]
        stats = item.get("outputs", {}).get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats", {})
        mean = stats.get("mean")
        by_month[month] = round(mean, 3) if isinstance(mean, (int, float)) and stats.get("sampleCount") else None
    months = sorted(by_month)[-12:]
    return months, [by_month[m] for m in months]


def refresh_parcel(session: Session, parcel: Parcel, *, flag_low: bool = False) -> Parcel:
    months, values = fetch_series(parcel.geometry)
    if not any(v is not None for v in values):
        raise NdviError("Нет безоблачных снимков за период")
    parcel.ndvi_months, parcel.ndvi_series, parcel.ndvi_source = months, values, "sentinel-2"
    peak = max(v for v in values if v is not None)
    if flag_low and parcel.purpose in ("agri", "lph") and parcel.lifecycle == "none" and peak < LOW_NDVI_PEAK:
        parcel.under_check = True
        history.log(session, "parcel", parcel.id, "ndvi_low", {"peak": peak})
    parcel.updated_at = utcnow()
    session.add(parcel)
    session.commit()
    bus.publish("parcel.updated", {"id": parcel.id})
    return parcel


def main() -> None:
    """python -m app.services.ndvi [--limit N] [--flag] — обновить NDVI участков из Sentinel-2."""
    import argparse

    from app import db

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--limit", type=int, default=5, help="сколько участков обновить (по умолчанию 5)")
    parser.add_argument("--flag", action="store_true",
                        help="ставить на проверку с/х участки с низким NDVI весь сезон")
    args = parser.parse_args()
    with db.new_session() as session:
        parcels = session.exec(select(Parcel).order_by(Parcel.area_ha.desc()).limit(args.limit)).all()
        for p in parcels:
            try:
                refresh_parcel(session, p, flag_low=args.flag)
                print(f"{p.cadastral_no}: {p.ndvi_series}")
            except NdviError as exc:
                session.rollback()
                print(f"{p.cadastral_no}: {exc}")


if __name__ == "__main__":
    main()
