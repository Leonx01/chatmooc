from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.chat import router as chat_router
from app.api.v1.routes.resources import router as resources_router
from app.api.v1.routes.test import router as redis_test_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(resources_router)

api_router.include_router(redis_test_router)

api_router.include_router(chat_router)
