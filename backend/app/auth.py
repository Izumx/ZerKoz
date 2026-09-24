"""Вход инспектора по паролю: подписанная HttpOnly-cookie (HMAC-SHA256).

Если INSPECTOR_PASSWORD не задан — панель открыта (локальная разработка).
Cookie автоматически уходит и с EventSource, и с <img>, поэтому фронтенду не нужно хранить токен.
"""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.config import settings

COOKIE = "zherkoz_session"
TTL_SECONDS = 12 * 3600
MAX_FAILURES = 10
FAILURE_WINDOW = 600

_secret = (settings.secret_key or secrets.token_hex(32)).encode()
_failures: dict[str, list[float]] = defaultdict(list)


def auth_required() -> bool:
    return bool(settings.inspector_password)


def _sign(message: str) -> str:
    return hmac.new(_secret, message.encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    message = f"inspector.{int(time.time()) + TTL_SECONDS}"
    return f"{message}.{_sign(message)}"


def verify_token(token: str | None) -> bool:
    if not token or token.count(".") != 2:
        return False
    role, expires, signature = token.split(".")
    if not hmac.compare_digest(signature, _sign(f"{role}.{expires}")):
        return False
    return expires.isdigit() and int(expires) > time.time()


def is_authenticated(request: Request) -> bool:
    return not auth_required() or verify_token(request.cookies.get(COOKIE))


def check_password(client: str, password: str) -> bool:
    now = time.time()
    _failures[client] = [t for t in _failures[client] if now - t < FAILURE_WINDOW]
    if len(_failures[client]) >= MAX_FAILURES:
        raise HTTPException(429, "Слишком много попыток входа, подождите 10 минут")
    ok = hmac.compare_digest(password.encode(), settings.inspector_password.encode())
    if not ok:
        _failures[client].append(now)
    return ok


async def require_inspector(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Требуется вход инспектора")
