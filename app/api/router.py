from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.partituras import router as partituras_router
from app.api.dashboard import router as dashboard_router
from app.api.musicians import router as musicians_router
from app.api.users import router as users_router
from app.api.patrimonio import router as patrimonio_router
from app.api.acervo import router as acervo_router
from app.api.misc import (
    settings_router,
    search_router,
    releases_router,
    i18n_router,
)
from app.api.programacao import router as programacao_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(partituras_router)
api_router.include_router(dashboard_router)
api_router.include_router(musicians_router)
api_router.include_router(users_router)
api_router.include_router(patrimonio_router)
api_router.include_router(acervo_router)
api_router.include_router(programacao_router)
api_router.include_router(settings_router)
api_router.include_router(search_router)
api_router.include_router(releases_router)
api_router.include_router(i18n_router)
