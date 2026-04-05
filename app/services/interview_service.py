import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser

from app.agents.nodes import get_llm
from app.agents.state import (
    InterviewEvaluation,
    InterviewQuestion,
    InterviewSummary,
)
from app.models.interview import InterviewPerformance, InterviewSession

logger = logging.getLogger(__name__)


class InterviewService:

    # ------------------------------------------------------------------ #
    #  Start a new interview — creates a MongoDB session and questions Q1 #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def start_interview(
        user_id: str, role: str, difficulty: str, mode: str, max_questions: int = 5
    ) -> Dict[str, Any]:
        # Close any prior ACTIVE session for this user (but keep paused ones)
        old = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "active",
        )
        if old:
            await old.delete()

        # Also close any paused session for this user (replace with fresh start)
        paused = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "paused",
        )
        if paused:
            await paused.delete()

        # Generate question 1
        question = await InterviewService._generate_question(
            role=role,
            difficulty=difficulty,
            mode=mode,
            history=[],
        )

        session = InterviewSession(
            user_id=user_id,
            role=role,
            difficulty=difficulty,
            interview_mode=mode,
            max_questions=max_questions,
            question_count=1,
            current_question=question,
            last_evaluation=None,
            question_history=[],
            is_completed=False,
            status="active",
        )
        await session.insert()

        return InterviewService._build_response(session)

    # ------------------------------------------------------------------ #
    #  Submit an answer — evaluate, adapt, generate next Q or summarise  #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def submit_answer(user_id: str, answer: str) -> Dict[str, Any]:
        session = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.is_completed == False,
            InterviewSession.status != "completed",
        )
        if not session:
            raise ValueError("No active interview session found. Please start a new interview.")

        if not session.current_question:
            raise ValueError("Session state corrupted — no current question. Please start a new interview.")

        # 1. Evaluate the answer
        evaluation = await InterviewService._evaluate_answer(
            question=session.current_question,
            answer=answer,
            role=session.role,
        )

        # 2. Record in history
        history_entry = {
            "question": session.current_question["question"],
            "topic": session.current_question.get("topic", ""),
            "answer": answer,
            "evaluation": evaluation,
        }
        session.question_history.append(history_entry)
        session.last_evaluation = evaluation

        # 3. Adapt difficulty
        score = evaluation.get("score", 5)
        levels = ["beginner", "intermediate", "advanced"]
        idx = levels.index(session.difficulty) if session.difficulty in levels else 1
        if score >= 8:
            session.difficulty = levels[min(idx + 1, 2)]
        elif score <= 3:
            session.difficulty = levels[max(idx - 1, 0)]

        # 4. Decide: more questions or summary?
        if session.question_count >= session.max_questions:
            # Generate summary
            summary = await InterviewService._generate_summary(
                role=session.role,
                history=session.question_history,
            )
            # Persist performance
            await InterviewService._persist_performance(session, summary)
            session.is_completed = True
            session.status = "completed"
            session.current_question = None
            session.updated_at = datetime.utcnow()
            await session.save()
            return InterviewService._build_response(session, summary=summary)

        # 5. Generate the next question
        next_q = await InterviewService._generate_question(
            role=session.role,
            difficulty=session.difficulty,
            mode=session.interview_mode,
            history=session.question_history,
        )
        session.question_count += 1
        session.current_question = next_q
        session.status = "active"
        session.updated_at = datetime.utcnow()
        await session.save()

        return InterviewService._build_response(session)

    # ------------------------------------------------------------------ #
    #  Get current state of an ongoing session                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def get_current_state(user_id: str) -> Optional[Dict[str, Any]]:
        """Returns the active or paused (resumable) session."""
        session = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.is_completed == False,
            InterviewSession.status != "completed",
        )
        if not session:
            return None
        return InterviewService._build_response(session)

    @staticmethod
    async def pause_session(user_id: str) -> Optional[Dict[str, Any]]:
        """Marks the active session as paused so user can resume later."""
        session = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "active",
        )
        if not session:
            return None
        session.status = "paused"
        session.paused_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        await session.save()
        return InterviewService._build_response(session)

    @staticmethod
    async def resume_session(user_id: str) -> Optional[Dict[str, Any]]:
        """Marks a paused session as active again."""
        session = await InterviewSession.find_one(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "paused",
        )
        if not session:
            return None
        session.status = "active"
        session.paused_at = None
        session.updated_at = datetime.utcnow()
        await session.save()
        return InterviewService._build_response(session)

    @staticmethod
    async def get_all_sessions(user_id: str) -> list:
        """Returns all non-completed sessions (active + paused) for history."""
        sessions = await InterviewSession.find(
            InterviewSession.user_id == user_id,
            InterviewSession.is_completed == False,
        ).sort("-updated_at").to_list()
        return [
            {
                "id": str(s.id),
                "role": s.role,
                "difficulty": s.difficulty,
                "mode": s.interview_mode,
                "status": s.status,
                "question_count": s.question_count,
                "max_questions": s.max_questions,
                "questions_done": len(s.question_history),
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "paused_at": s.paused_at.isoformat() if s.paused_at else None,
                "question_history": s.question_history,
            }
            for s in sessions
        ]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    @staticmethod
    async def _generate_question(
        role: str, difficulty: str, mode: str, history: List[Dict]
    ) -> Dict[str, Any]:
        llm = get_llm()
        parser = PydanticOutputParser(pydantic_object=InterviewQuestion)

        past = "\n".join([f"- {h['question']}" for h in history]) or "None yet."

        prompt = f"""You are an expert technical interviewer for the role of {role}.
Interview mode: {mode} | Difficulty: {difficulty}

Previous questions asked (DO NOT repeat):
{past}

Generate ONE new, challenging, real-world interview question.
It must be {mode}-style and {difficulty} level.
Do not repeat any past question.

{parser.get_format_instructions()}"""

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            parsed = parser.parse(response.content)
            return parsed.dict()
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return {
                "question": f"Explain a core concept of {role} and how you have applied it in a project.",
                "topic": "Core Concepts",
                "difficulty": difficulty,
            }

    @staticmethod
    async def _evaluate_answer(
        question: Dict[str, Any], answer: str, role: str
    ) -> Dict[str, Any]:
        llm = get_llm()
        parser = PydanticOutputParser(pydantic_object=InterviewEvaluation)

        prompt = f"""You are a strict technical interviewer. Evaluate this answer:

Role: {role}
Question: {question.get('question', 'N/A')}
Topic: {question.get('topic', 'General')}
Candidate's Answer: {answer}

Evaluate for correctness, depth, and clarity. Give a score 0–10. Provide an ideal answer.

{parser.get_format_instructions()}"""

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            parsed = parser.parse(response.content)
            return parsed.dict()
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {
                "score": 5,
                "correctness": "Could not evaluate automatically.",
                "depth": "N/A",
                "clarity": "N/A",
                "strengths": [],
                "weaknesses": [],
                "ideal_answer": "Manual review required.",
            }

    @staticmethod
    async def _generate_summary(
        role: str, history: List[Dict]
    ) -> Dict[str, Any]:
        llm = get_llm()
        parser = PydanticOutputParser(pydantic_object=InterviewSummary)

        prompt = f"""Analyze this complete interview for a {role} candidate.

Interview History:
{json.dumps(history, indent=2)}

1. Calculate average score and final grade.
2. Find top strong areas and weak areas.
3. Give 3–5 actionable improvement steps.

{parser.get_format_instructions()}"""

        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            parsed = parser.parse(response.content)
            return parsed.dict()
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            scores = [h["evaluation"].get("score", 5) for h in history]
            avg = sum(scores) / len(scores) if scores else 5
            return {
                "final_score": f"{round(avg * 10)}%",
                "average_score": avg,
                "strong_areas": [],
                "weak_areas": [],
                "improvement_plan": ["Review the topics covered in this session."],
            }

    @staticmethod
    async def _persist_performance(
        session: InterviewSession, summary: Dict[str, Any]
    ):
        try:
            perf = InterviewPerformance(
                user_id=session.user_id,
                role=session.role,
                overall_score=summary.get("average_score", 0) * 10,
                average_score=summary.get("average_score", 0),
                strong_areas=summary.get("strong_areas", []),
                weak_areas=summary.get("weak_areas", []),
                improvement_plan=summary.get("improvement_plan", []),
                question_history=session.question_history,
                frequently_failed_topics=summary.get("weak_areas", []),
            )
            await perf.insert()
        except Exception as e:
            logger.error(f"Failed to persist interview performance: {e}")

    @staticmethod
    def _build_response(
        session: InterviewSession, summary: Optional[Dict] = None
    ) -> Dict[str, Any]:
        return {
            "current_question": session.current_question,
            "evaluation": session.last_evaluation,
            "score": session.last_evaluation.get("score") if session.last_evaluation else None,
            "question_count": session.question_count,
            "max_questions": session.max_questions,
            "is_completed": session.is_completed,
            "performance_summary": summary,
            "question_history": session.question_history,
        }


interview_service = InterviewService()
