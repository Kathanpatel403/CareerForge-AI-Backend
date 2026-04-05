from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint to ensure API and DB are reachable.
    """
    # Later add actual db pings or dependency checks
    return {"status": "ok", "message": "API is healthy and running!"}
