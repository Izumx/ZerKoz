from datetime import date, timedelta

import pytest

from app.models import Event, Signal
from app.services import parcels
from app.services.parcels import TransitionError
from tests.factories import make_parcel
from sqlmodel import select


def test_color_rules(session):
    p = make_parcel(session)
    assert parcels.compute_color(p, open_signals=0) == "green"
    assert parcels.compute_color(p, open_signals=1) == "yellow"
    p.under_check = True
    assert parcels.compute_color(p, open_signals=0) == "yellow"
    p.lifecycle = "detected"
    assert parcels.compute_color(p, open_signals=1) == "red"
    p.lifecycle = "in_progress"
    assert parcels.compute_color(p, open_signals=0) == "red"
    p.lifecycle, p.under_check = "resolved", False
    assert parcels.compute_color(p, open_signals=0) == "green"


def test_overdue(session):
    today = date(2026, 9, 23)
    p = make_parcel(session, lifecycle="in_progress", deadline=date(2026, 9, 22))
    assert parcels.is_overdue(p, today)
    p.deadline = today
    assert not parcels.is_overdue(p, today)
    p.deadline, p.lifecycle = date(2026, 1, 1), "resolved"
    assert not parcels.is_overdue(p, today)


def test_full_lifecycle(session):
    p = make_parcel(session)
    parcels.update_parcel(session, p.id, {"lifecycle": "detected", "violation_type": "dump"})
    deadline = date.today() + timedelta(days=30)
    parcels.update_parcel(session, p.id, {"lifecycle": "in_progress", "deadline": deadline})
    updated = parcels.update_parcel(session, p.id, {"lifecycle": "returned"})
    assert updated.lifecycle == "returned"
    assert updated.deadline == deadline
    actions = session.exec(select(Event.action).where(Event.entity == "parcel")).all()
    assert actions.count("lifecycle") == 3


def test_detected_requires_violation_type(session):
    p = make_parcel(session)
    with pytest.raises(TransitionError):
        parcels.update_parcel(session, p.id, {"lifecycle": "detected"})


def test_in_progress_requires_deadline(session):
    p = make_parcel(session, lifecycle="detected", violation_type="unused")
    with pytest.raises(TransitionError):
        parcels.update_parcel(session, p.id, {"lifecycle": "in_progress"})


def test_forbidden_transition(session):
    p = make_parcel(session)
    with pytest.raises(TransitionError):
        parcels.update_parcel(session, p.id, {"lifecycle": "resolved"})


def test_invalid_violation_type(session):
    p = make_parcel(session)
    with pytest.raises(TransitionError):
        parcels.update_parcel(session, p.id, {"violation_type": "alien"})


def test_detected_clears_under_check(session):
    p = make_parcel(session, under_check=True)
    updated = parcels.update_parcel(session, p.id, {"lifecycle": "detected", "violation_type": "seizure"})
    assert updated.under_check is False


def test_feature_collection_counts_open_signals(session):
    p = make_parcel(session)
    session.add(Signal(lat=42.005, lon=71.005, parcel_id=p.id, status="new"))
    session.add(Signal(lat=42.005, lon=71.005, parcel_id=p.id, status="rejected"))
    session.commit()
    fc = parcels.feature_collection(session)
    props = fc["features"][0]["properties"]
    assert fc["type"] == "FeatureCollection"
    assert props["color"] == "yellow"
    assert props["open_signals"] == 1
    assert props["cadastral_no"] == "06-097-001-001"
