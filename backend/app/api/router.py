from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.review import router as review_router
from app.api.v1.upload import router as upload_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(review_router)
api_router.include_router(upload_router)
