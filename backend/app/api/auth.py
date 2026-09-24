from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth, runtime
from app.config import settings

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    password: str


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/session")
def session_info(request: Request) -> dict:
    authenticated = auth.is_authenticated(request)
    return {
        "auth_required": auth.auth_required(),
        "authenticated": authenticated,
        "demo_mode": settings.demo_mode,
        "bot_username": runtime.bot_username if authenticated else None,
    }


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    if not auth.auth_required():
        return {"ok": True}
    client = request.client.host if request.client else "unknown"
    if not auth.check_password(client, body.password):
        raise HTTPException(401, "Неверный пароль")
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(auth.COOKIE, auth.make_token(), max_age=auth.TTL_SECONDS, httponly=True,
                        samesite="lax", secure=secure)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}
