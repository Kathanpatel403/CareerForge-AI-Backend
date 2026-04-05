from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    State schema for the Career Copilot LangGraph.
    """
    user_input: str
    intent: Optional[str]
    target_role: Optional[str]  # e.g., 'GenAI Engineer', 'UX Designer'
    resume_data: Optional[Dict[str, Any]]
    skill_gap: Optional[Dict[str, Any]]
    roadmap: Optional[Dict[str, Any]]
    session_id: Optional[str]
    file_content: Optional[str]  # Raw text extracted from PDF/Word
    general_response: Optional[str]  # For greetings and off-topic queries
    error: Optional[str]

class InterviewState(TypedDict):
    """
    State schema for the Interview System LangGraph.
    """
    user_input: Optional[str]
    user_id: Optional[str]
    role: str
    difficulty: str  # beginner, intermediate, advanced
    interview_mode: str  # technical, hr, rapid_fire
    current_question: Optional[Dict[str, Any]]
    user_answer: Optional[str]
    evaluation: Optional[Dict[str, Any]]
    score: Optional[int]
    feedback: Optional[str]
    question_history: List[Dict[str, Any]]
    performance_summary: Optional[Dict[str, Any]]
    resume_data: Optional[Dict[str, Any]]
    skill_gap: Optional[Dict[str, Any]]
    max_questions: int
    question_count: int
    session_id: Optional[str]
    past_performance: Optional[Dict[str, Any]] # For memory integration

# Pydantic models for structured output
class IntentResponse(BaseModel):
    intent: str = Field(description="One of: resume_analysis, roadmap_generation, interview_preparation, general_query")
    target_role: Optional[str] = Field(description="The role mentioned (e.g. 'Backend Developer'), or None if not found")
    reason: str = Field(description="Brief reason for this classification")

class ResumeAnalysis(BaseModel):
    skills: List[str] = Field(description="List of technical and soft skills")
    projects: List[str] = Field(description="Summary of key projects")
    experience_level: str = Field(description="One of: beginner, intermediate, advanced")

class SkillGap(BaseModel):
    missing_skills: List[str] = Field(description="Skills required but not present in resume")
    matched_skills: List[str] = Field(description="Skills present in resume that match role requirements")

class RoadmapStep(BaseModel):
    week: int
    topic: str
    tasks: List[str]

class Roadmap(BaseModel):
    weeks: List[RoadmapStep]
    project_suggestions: List[str]

# --- Interview Related Models ---

class InterviewQuestion(BaseModel):
    question: str = Field(description="The interview question")
    topic: str = Field(description="The topic of the question")
    difficulty: str = Field(description="The difficulty level (beginner, intermediate, advanced)")

class InterviewEvaluation(BaseModel):
    score: int = Field(description="Score from 0 to 10", ge=0, le=10)
    correctness: str = Field(description="Brief assessment of correctness")
    depth: str = Field(description="Assessment of technical depth")
    clarity: str = Field(description="Assessment of communication clarity")
    strengths: List[str] = Field(description="Key strengths in the answer")
    weaknesses: List[str] = Field(description="Areas for improvement")
    ideal_answer: str = Field(description="A concise example of an ideal answer")

class DifficultyResponse(BaseModel):
    next_difficulty: str = Field(description="The next difficulty level (beginner, intermediate, advanced)")

class InterviewSummary(BaseModel):
    overall_score: float = Field(description="Overall percentage score (0-100)")
    average_score: float = Field(description="Average score across all questions (0-10)")
    strong_areas: List[str] = Field(description="Topics the user excelled in")
    weak_areas: List[str] = Field(description="Topics the user struggled with")
    improvement_plan: List[str] = Field(description="Actionable steps for improvement")

class RequiredSkills(BaseModel):
    role: str = Field(description="The normalized name of the role (e.g., UX Designer)")
    skills: List[str] = Field(description="8-10 core technical and soft skills for this role")
