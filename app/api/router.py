from fastapi import APIRouter
from app.api.endpoints import health, copilot, auth, interview

api_router = APIRouter()
api_router.include_router(health.router, prefix="/system", tags=["System"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["GenAI Copilot"])
api_router.include_router(interview.router, prefix="/interview", tags=["Interview System"])
# Example of future endpoints
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
