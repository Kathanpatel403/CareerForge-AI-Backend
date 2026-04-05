from typing import List, Optional
from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field, BaseModel

class ChatMessage(BaseModel):
    role: str  # "user" or "ai"
    content: str
    file_id: Optional[str] = None      # GridFS ID (stored as string)
    file_name: Optional[str] = None    # Readable filename
    file_type: Optional[str] = None    # MIME type
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatSession(Document):
    user_id: Indexed(str)
    title: Optional[str] = "New Chat"
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "chat_sessions"
