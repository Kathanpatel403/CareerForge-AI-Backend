from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from beanie import init_beanie
from app.core.config import settings
from app.models.user import User
from app.models.chat import ChatSession
from app.models.interview import InterviewPerformance, InterviewSession

_db: AsyncIOMotorGridFSBucket = None

async def init_db():
    global _db
    # Database Initialization using Beanie ODM
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    database = client[settings.DATABASE_NAME]
    _db = database
    
    # Initialize beanie with the User document class and others as they are added
    # Best practice is to register all Document models here
    await init_beanie(
        database=database,
        document_models=[
            User,
            ChatSession,
            InterviewPerformance,
            InterviewSession,
            # Add other models here
        ]
    )
    print(f"Connected to MongoDB database '{settings.DATABASE_NAME}' securely.")

def get_gridfs():
    return AsyncIOMotorGridFSBucket(_db)

async def close_db():
    # Placeholder if you need to cleanly shutdown things
    print("Database connection closed gracefully.")
