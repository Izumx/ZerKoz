import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import signals, webapp
from tests.factories import make_parcel

TOKEN = "42:TEST"


def sign(fields: dict, token: str = TOKEN) -> str:
    """initData так, как её подписывает Telegram."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def user_fields(user_id: int = 777, auth_date: int | None = None) -> dict:
    return {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH",
            "user": json.dumps({"id": user_id, "first_name": "Айгерим", "language_code": "kk"}, ensure_ascii=False)}


def test_init_data_signature():
    assert webapp.validate_init_data(sign(user_fields()), TOKEN)["id"] == 777
    assert webapp.validate_init_data(sign(user_fields(), token="1:OTHER"), TOKEN) is None  # чужой бот
    tampered = sign(user_fields()).replace("777", "778")
    assert webapp.validate_init_data(tampered, TOKEN) is None
    stale = sign(user_fields(auth_date=int(time.time()) - 2 * 86400))
    assert webapp.validate_init_data(stale, TOKEN) is None
    assert webapp.validate_init_data("", TOKEN) is None


def test_public_signals_hide_private_fields(session):
    make_parcel(session)
    s = signals.create_signal(session, lat=42.0051234, lon=71.0059876, description="Мой адрес: ул. Абая 5",
                              tg_chat_id=777)
    rejected = signals.create_signal(session, lat=43.0, lon=72.0)
    signals.set_status(session, rejected.id, "rejected")
    body = TestClient(app).get("/api/public/signals").json()
    assert [x["code"] for x in body] == [s.code]  # отклонённые не показываются
    item = body[0]
    assert item["lat"] == 42.0051 and item["lon"] == 71.006  # округлены
    assert "description" not in item and "photos" not in item and "tg_chat_id" not in item


def test_my_signals_requires_valid_init_data(session, monkeypatch):
    monkeypatch.setattr(settings, "bot_token", TOKEN)
    signals.create_signal(session, lat=42.0, lon=71.0, description="Свалка", tg_chat_id=777)
    signals.create_signal(session, lat=43.0, lon=72.0, description="Чужой", tg_chat_id=999)
    client = TestClient(app)
    assert client.post("/api/public/my-signals", json={"init_data": "hash=bad"}).status_code == 401
    body = client.post("/api/public/my-signals", json={"init_data": sign(user_fields())}).json()
    assert body["lang"] == "kz"
    assert [x["description"] for x in body["signals"]] == ["Свалка"]
