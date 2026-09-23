from fastapi import APIRouter

from app.api import applications, demo, events, parcels, signals, stats

router = APIRouter(prefix="/api")
for module in (parcels, signals, applications, stats, events, demo):
    router.include_router(module.router)
