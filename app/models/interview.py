from typing import List, Optional, Dict, Any
from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime


class InterviewSession(Document):
    """Active interview session - stores ongoing state in MongoDB."""
    user_id: str
    role: str
    difficulty: str
    interview_mode: str
    max_questions: int = 5
    question_count: int = 0
    current_question: Optional[Dict[str, Any]] = None
    last_evaluation: Optional[Dict[str, Any]] = None
    question_history: List[Dict[str, Any]] = Field(default_factory=list)
    is_completed: bool = False
    status: str = "active"   # "active" | "paused" | "completed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    paused_at: Optional[datetime] = None

    class Settings:
        name = "interview_sessions"


class InterviewPerformance(Document):
    """Completed interview result - stored after session ends."""
    user_id: str
    role: str
    overall_score: float
    average_score: float
    strong_areas: List[str]
    weak_areas: List[str]
    improvement_plan: List[str]
    question_history: List[Dict[str, Any]] = Field(default_factory=list)
    frequently_failed_topics: List[str] = Field(default_factory=list)
    session_date: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "interview_performances"
