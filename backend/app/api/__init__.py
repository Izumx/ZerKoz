from fastapi import APIRouter, Depends

from app.api import applications, auth, demo, events, media, parcels, public as public_api, signals, stats
from app.auth import require_inspector

# вход, проверка состояния и Mini App жителей — без авторизации инспектора
public = APIRouter(prefix="/api")
public.include_router(auth.router)
public.include_router(public_api.router)

# всё остальное — только для инспектора
protected = APIRouter(prefix="/api", dependencies=[Depends(require_inspector)])
for module in (parcels, signals, applications, stats, events, demo):
    protected.include_router(module.router)

media_router = APIRouter(dependencies=[Depends(require_inspector)])
media_router.include_router(media.router)

routers = (public, protected, media_router)
