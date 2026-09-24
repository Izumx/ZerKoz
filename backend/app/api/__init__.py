from fastapi import APIRouter, Depends

from app.api import applications, auth, demo, events, media, parcels, signals, stats
from app.auth import require_inspector

# вход и проверка состояния — без авторизации
public = APIRouter(prefix="/api")
public.include_router(auth.router)

# всё остальное — только для инспектора
protected = APIRouter(prefix="/api", dependencies=[Depends(require_inspector)])
for module in (parcels, signals, applications, stats, events, demo):
    protected.include_router(module.router)

media_router = APIRouter(dependencies=[Depends(require_inspector)])
media_router.include_router(media.router)

routers = (public, protected, media_router)
