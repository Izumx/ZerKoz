"""Вся геологика проекта. Переход на PostGIS меняет только этот модуль."""
import math
import random

from shapely.geometry import Point, Polygon, shape
from sqlmodel import Session, select

from app.models import Parcel

M_PER_DEG = 111_320.0


def point_in(geometry: dict, *, lat: float, lon: float) -> bool:
    return shape(geometry).covers(Point(lon, lat))


def find_parcel(session: Session, *, lat: float, lon: float) -> Parcel | None:
    """Участок, внутри которого лежит точка (при пересечении — наименьший)."""
    matches = [p for p in session.exec(select(Parcel)).all() if point_in(p.geometry, lat=lat, lon=lon)]
    return min(matches, key=lambda p: p.area_ha) if matches else None


def centroid(geometry: dict) -> tuple[float, float]:
    c = shape(geometry).centroid
    return c.y, c.x


def random_point_in(geometry: dict, rng: random.Random) -> tuple[float, float]:
    poly = shape(geometry)
    minx, miny, maxx, maxy = poly.bounds
    for _ in range(1000):
        pt = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if poly.contains(pt):
            return pt.y, pt.x
    c = poly.representative_point()
    return c.y, c.x


def area_ha(geometry: dict) -> float:
    """Площадь в гектарах (локальная равнопромежуточная проекция — точно для участков до десятков км)."""
    poly = shape(geometry)
    lat0 = math.radians(poly.centroid.y)
    kx = M_PER_DEG * math.cos(lat0)

    def project(ring):
        return [((x - poly.centroid.x) * kx, (y - poly.centroid.y) * M_PER_DEG) for x, y in ring]

    projected = Polygon(project(poly.exterior.coords), [project(r.coords) for r in poly.interiors])
    return projected.area / 10_000
