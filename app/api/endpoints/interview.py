from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.models.user import User
from app.models.interview import InterviewPerformance
from app.services.interview_service import interview_service

router = APIRouter()


# --- Request / Response Models ---

class InterviewStartRequest(BaseModel):
    role: str = "GenAI Engineer"
    difficulty: str = "intermediate"
    mode: str = "technical"
    max_questions: int = 5


class InterviewAnswerRequest(BaseModel):
    answer: str


class InterviewResponse(BaseModel):
    current_question: Optional[dict] = None
    evaluation:       Optional[dict] = None
    score:            Optional[int]  = None
    question_count:   int            = 0
    max_questions:    int            = 5
    is_completed:     bool           = False
    performance_summary: Optional[dict] = None
    question_history:    List[dict]     = []


# --- Endpoints ---

@router.post("/start", response_model=InterviewResponse)
async def start_interview(
    req: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Start (or restart) an interview session for the current user.
    Closes any existing open session and generates the first question.
    """
    try:
        state = await interview_service.start_interview(
            user_id    = str(current_user.id),
            role       = req.role,
            difficulty = req.difficulty,
            mode       = req.mode,
            max_questions = req.max_questions,
        )
        return InterviewResponse(**state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {e}")


@router.post("/answer", response_model=InterviewResponse)
async def submit_answer(
    req: InterviewAnswerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submit an answer. Evaluates it, then either returns the next question
    or the final performance summary if all questions are done.
    """
    try:
        state = await interview_service.submit_answer(
            user_id = str(current_user.id),
            answer  = req.answer,
        )
        return InterviewResponse(**state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process answer: {e}")


@router.get("/current", response_model=InterviewResponse)
async def get_current_interview(current_user: User = Depends(get_current_user)):
    """
    Returns the active interview session state, or 404 if none exists.
    """
    state = await interview_service.get_current_state(str(current_user.id))
    if not state:
        raise HTTPException(status_code=404, detail="No active interview session found.")
    return InterviewResponse(**state)


@router.delete("/current")
async def abandon_interview(current_user: User = Depends(get_current_user)):
    """
    Permanently delete (abandon) the current active interview session.
    """
    from app.models.interview import InterviewSession
    session = await InterviewSession.find_one(
        InterviewSession.user_id == str(current_user.id),
        InterviewSession.is_completed == False,
        InterviewSession.status != "completed",
    )
    if session:
        await session.delete()
    return {"message": "Session abandoned."}


@router.patch("/pause")
async def pause_interview(current_user: User = Depends(get_current_user)):
    """
    Pause (save) the current active interview session for later resumption.
    """
    result = await interview_service.pause_session(str(current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="No active session to pause.")
    return {"message": "Session paused successfully.", "data": result}


@router.patch("/resume")
async def resume_interview(current_user: User = Depends(get_current_user)):
    """
    Resume the most recently paused interview session.
    """
    result = await interview_service.resume_session(str(current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="No paused session found.")
    return InterviewResponse(**result)


@router.get("/in-progress", response_model=List[dict])
async def get_in_progress_sessions(current_user: User = Depends(get_current_user)):
    """
    Returns all active and paused (incomplete) sessions for the user.
    Used to display in-progress interviews in the History page.
    """
    sessions = await interview_service.get_all_sessions(str(current_user.id))
    return sessions


@router.get("/history", response_model=List[dict])
async def get_interview_history(current_user: User = Depends(get_current_user)):
    """
    All completed interview performances for the user.
    """
    history = (
        await InterviewPerformance
        .find(InterviewPerformance.user_id == str(current_user.id))
        .sort("-session_date")
        .to_list()
    )
    return [
        {
            "id":           str(h.id),
            "role":         h.role,
            "score":        h.overall_score,
            "date":         h.session_date.isoformat(),
            "strong_areas": h.strong_areas,
            "weak_areas":   h.weak_areas,
        }
        for h in history
    ]


@router.get("/history/{performance_id}")
async def get_performance_details(
    performance_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Detailed results for a specific completed interview.
    """
    perf = await InterviewPerformance.get(performance_id)
    if not perf or perf.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Performance record not found.")
    return perf
