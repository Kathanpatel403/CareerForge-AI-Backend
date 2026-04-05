from typing import Optional
from datetime import datetime
from beanie import Document
from pydantic import EmailStr, Field

class User(Document):
    """
    User Document Models. 
    Inheriting from beanie.Document adds ODM functionality out of the box.
    """
    email: EmailStr
    full_name: str
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    profile_picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    reset_token: Optional[str] = None
    reset_token_expires: Optional[datetime] = None

    class Settings:
        name = "users" # collection name
