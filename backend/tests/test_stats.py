from datetime import date, timedelta

from app.services import signals, stats
from tests.factories import make_parcel


def test_dashboard_counts(session):
    make_parcel(session, 1, lon=71.0)
    make_parcel(session, 2, lon=71.1, under_check=True)
    make_parcel(session, 3, lon=71.2, lifecycle="in_progress", violation_type="dump",
                deadline=date.today() - timedelta(days=1))
    signals.create_signal(session, lat=42.005, lon=71.005)

    d = stats.dashboard(session)
    assert d == {
        "total": 3, "green": 0, "yellow": 2, "red": 1, "overdue": 1,
        "signals_new": 1, "signals_open": 1, "signals_24h": 1,
    }


def test_csv_export(session):
    make_parcel(session, 1, address="г. Тараз")
    text = stats.parcels_csv(session)
    lines = text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Кадастровый номер;")
    assert "06-097-001-001" in lines[1] and "г. Тараз" in lines[1]
