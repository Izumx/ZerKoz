import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models import Application
from tests.factories import make_parcel


@pytest.fixture
def client():
    return TestClient(app)  # без контекста: lifespan (бот) не запускается


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, "PNG")
    return buf.getvalue()


def test_parcels_feature_collection(client, session):
    make_parcel(session)
    body = client.get("/api/parcels").json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["color"] == "green"


def test_patch_lifecycle_and_conflict(client, session):
    p = make_parcel(session)
    r = client.patch(f"/api/parcels/{p.id}", json={"lifecycle": "resolved"})
    assert r.status_code == 409 and "недопустим" in r.json()["detail"]
    r = client.patch(f"/api/parcels/{p.id}", json={"lifecycle": "detected", "violation_type": "unused"})
    assert r.status_code == 200
    assert r.json()["color"] == "red"
    assert r.json()["history"][0]["action"] == "lifecycle"
    r = client.patch(f"/api/parcels/{p.id}", json={"lifecycle": "in_progress", "deadline": "2026-12-01"})
    assert r.json()["deadline"] == "2026-12-01"


def test_parcel_404(client):
    assert client.get("/api/parcels/999").status_code == 404


def test_upload_photos(client, session):
    p = make_parcel(session)
    r = client.post(f"/api/parcels/{p.id}/photos", files=[("files", ("a.png", png(), "image/png"))])
    assert r.status_code == 200
    assert r.json()["photos"][0]["url"].endswith(".png")
    r = client.post(f"/api/parcels/{p.id}/photos", files=[("files", ("a.txt", b"hello", "text/plain"))])
    assert r.status_code == 400


def test_demo_signal_and_status_flow(client, session):
    p = make_parcel(session)
    sig = client.post("/api/demo/signal").json()
    assert sig["code"] == "SIG-0001" and sig["parcel"]["id"] == p.id and len(sig["photos"]) == 1
    assert client.get("/api/signals").json()[0]["code"] == "SIG-0001"
    r = client.patch(f"/api/signals/{sig['id']}", json={"status": "confirmed", "violation_type": "unused"})
    assert r.json()["status"] == "confirmed"
    assert client.get(f"/api/parcels/{p.id}").json()["lifecycle"] == "detected"
    assert client.patch(f"/api/signals/{sig['id']}", json={"status": "new"}).status_code == 409


def test_application_lookup(client, session):
    session.add(Application(track_no="KZ-2026-042", applicant="А.", type="izhs", stage="approved", note_ru="Ок"))
    session.commit()
    assert client.get("/api/applications/kz2026042").json()["stage"] == "approved"
    assert client.get("/api/applications/KZ-2026-001").status_code == 404


def test_stats_and_csv(client, session):
    make_parcel(session)
    assert client.get("/api/stats").json()["green"] == 1
    r = client.get("/api/export/parcels.csv")
    assert r.status_code == 200 and "06-097-001-001" in r.text
    assert client.get("/api/health").json()["ok"] is True
