import random

from app.services import geo
from tests.factories import make_parcel, square


def test_point_in_polygon():
    poly = square(71.0, 42.0)
    assert geo.point_in(poly, lat=42.005, lon=71.005)
    assert not geo.point_in(poly, lat=42.02, lon=71.005)


def test_find_parcel_picks_containing_polygon(session):
    make_parcel(session, 1, lon=71.0, lat=42.0)
    p2 = make_parcel(session, 2, lon=71.1, lat=42.0)
    assert geo.find_parcel(session, lat=42.005, lon=71.105).id == p2.id
    assert geo.find_parcel(session, lat=43.0, lon=72.0) is None


def test_centroid_and_random_point():
    poly = square(71.0, 42.0)
    lat, lon = geo.centroid(poly)
    assert abs(lat - 42.005) < 1e-9 and abs(lon - 71.005) < 1e-9
    rng = random.Random(1)
    for _ in range(20):
        lat, lon = geo.random_point_in(poly, rng)
        assert geo.point_in(poly, lat=lat, lon=lon)


def test_area_ha_uses_metres():
    # 0.01° x 0.01° на широте 42° ≈ 1113 м x 827 м ≈ 92 га
    assert 85 < geo.area_ha(square(71.0, 42.0)) < 100
