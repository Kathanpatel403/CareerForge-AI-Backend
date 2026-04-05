import json
import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from app.core.config import settings
from app.models.interview import InterviewPerformance
from app.agents.state import (
    AgentState, InterviewState, IntentResponse, ResumeAnalysis, 
    SkillGap, Roadmap, RoadmapStep, InterviewQuestion, InterviewEvaluation, 
    DifficultyResponse, InterviewSummary
)

# Helper to get the default LLM
def get_llm(temperature=0, streaming=False):
    if settings.GOOGLE_API_KEY:
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
            streaming=streaming
        )
    return ChatOpenAI(
        model="gpt-4o",
        openai_api_key=settings.OPENAI_API_KEY,
        temperature=temperature,
        streaming=streaming
    )

# --- Role Maps ---
ROLE_SKILLS_MAP = {
    "GenAI Engineer": ["Python", "LangChain", "RAG", "LLMs", "Vector Databases", "Prompt Engineering", "Fine-tuning", "FastAPI"],
    "Frontend Developer": ["React", "TypeScript", "Tailwind CSS", "Redux", "HTML/CSS", "JavaScript", "Responsive Design"],
    "Backend Developer": ["Python", "FastAPI", "Node.js", "SQL", "NoSQL", "Docker", "API Design", "Distributed Systems"],
    "Data Scientist": ["Python", "SQL", "Pandas", "Scikit-Learn", "Deep Learning", "Statistics", "Machine Learning", "PyTorch"]
}

# --- Intent Classification Node ---
async def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=IntentResponse)
    
    prompt = f"""
    You are an AI Career Assistant. Classify the user's input into one of the following intents:
    - resume_analysis: If the user provides a resume or asks to analyze their profile.
    - roadmap_generation: If the user asks for a learning path or how to achieve a career goal.
    - interview_preparation: If the user asks for interview questions or practice.
    - general_query: Anything else.
    
    User input: {state['user_input']}
    
    {parser.get_format_instructions()}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        parsed_res = parser.parse(response.content)
        return {**state, "intent": parsed_res.intent}
    except Exception:
        # Fallback
        if "resume" in state['user_input'].lower() or state.get('file_content'):
            return {**state, "intent": "resume_analysis"}
        return {**state, "intent": "general_query"}

# --- Resume Analysis Node ---
async def resume_analyzer_node(state: AgentState) -> Dict[str, Any]:
    if not state.get('file_content'):
        return {**state, "error": "No resume text found."}
    
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=ResumeAnalysis)
    
    prompt = f"""
    Extract key information from the following resume text:
    - Current skills (technical and soft)
    - Key projects (summarize)
    - Experience level (beginner, intermediate, or advanced)
    
    Resume Text:
    {state['file_content']}
    
    {parser.get_format_instructions()}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        parsed_res = parser.parse(response.content)
        return {**state, "resume_data": parsed_res.dict()}
    except Exception as e:
        return {**state, "error": f"Failed to analyze resume: {e}"}

# --- Skill Gap Node ---
async def skill_gap_node(state: AgentState) -> Dict[str, Any]:
    # Determine target role - default to 'GenAI Engineer' if not specified
    target_role = "GenAI Engineer" 
    # (Future refinement: extract target role from input if available)
    
    resume_data = state.get('resume_data') or {}
    skills_list = resume_data.get('skills') or []
    user_skills = [s.lower() for s in skills_list]
    required_skills = ROLE_SKILLS_MAP.get(target_role, [])
    
    matched = []
    missing = []
    
    for skill in required_skills:
        if any(skill.lower() in s for s in user_skills):
            matched.append(skill)
        else:
            missing.append(skill)
            
    gap_data = {
        "missing_skills": missing,
        "matched_skills": matched,
        "target_role": target_role
    }
    
    return {**state, "skill_gap": gap_data}

# --- Roadmap Generator Node ---
async def roadmap_generator_node(state: AgentState) -> Dict[str, Any]:
    gap_data = state.get('skill_gap') or {}
    missing_skills = gap_data.get('missing_skills') or []
    resume_data = state.get('resume_data') or {}
    exp_level = resume_data.get('experience_level', 'beginner')
    
    if not missing_skills:
        return {**state, "roadmap": {"weeks": [], "project_suggestions": ["Keep practicing existing skills."]}}
        
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=Roadmap)
    
    prompt = f"""
    Create a practical learning roadmap for a {exp_level} level candidate looking to fill these skill gaps: {missing_skills}.
    Target Role: {gap_data.get('target_role')}
    
    The roadmap should include weekly topics and specific tasks. Also suggest 2 project ideas.
    
    {parser.get_format_instructions()}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        parsed_res = parser.parse(response.content)
        return {**state, "roadmap": parsed_res.dict()}
    except Exception as e:
        return {**state, "error": f"Failed to generate roadmap: {e}"}

# --- Interview Placeholder ---
async def interview_placeholder_node(state: AgentState) -> Dict[str, Any]:
    return {**state, "roadmap": {"message": "Interview preparation is coming soon!"}}

# --- General Query Node (Greetings and off-topic) ---
async def general_query_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm(temperature=0.7) # Slightly higher temperature for more natural conversational flow
    
    prompt = f"""
    You are the 'Career Forge AI Copilot', a helpful, professional, and encouraging career assistant.
    The user sent a message that doesn't fit into a specific task like resume analysis or roadmap generation.
    
    User message: "{state['user_input']}"
    
    Goal:
    1. If it's a greeting (like 'hello'), respond warmly and briefly explain how you can help (resume analysis, career roadmaps, skill gaps).
    2. If it's a general career question, answer it professionally.
    3. If it's completely off-topic, politely redirect them back to career-related topics.
    
    Tone: Premium, modern, helpful, NOT robotic.
    
    Response:
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {**state, "response": response.content}

# --- Interview System Nodes ---

async def question_generator_node(state: InterviewState) -> Dict[str, Any]:
    """Generates the next interview question based on role, difficulty, and history."""
    logging.info(f"Question Generator Node: State keys: {list(state.keys())}")
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=InterviewQuestion)
    
    # Context matters: Resume data and Skill Gap can help tailor questions
    resume_context = f"Resume context: {json.dumps(state.get('resume_data', {}))}" if state.get('resume_data') else ""
    skill_gap_context = f"Skill gaps: {json.dumps(state.get('skill_gap', {}))}" if state.get('skill_gap') else ""
    past_performance = f"Past Performance (Memory): {json.dumps(state.get('past_performance', {}))}" if state.get('past_performance') else ""
    
    # Avoid repeating questions
    history = "\n".join([f"- {q['question']}" for q in state.get('question_history', [])])
    
    prompt = f"""
    You are an expert technical interviewer for the role of {state['role']}.
    The interview mode is {state['interview_mode']} and the current difficulty level is {state['difficulty']}.
    
    {resume_context}
    {skill_gap_context}
    {past_performance}
    
    Previous questions in this session:
    {history}
    
    Task:
    Generate a challenging, professional interview question for this candidate.
    Ensure it's a {state['interview_mode']} style question.
    Tailor it based on:
    - The candidate's weak skills OR role requirements.
    - Frequently failed topics or weak areas from past performance (if available).
    - Gradually increasing or decreasing technical depth based on past performance.
    
    Avoid duplicates.
    
    {parser.get_format_instructions()}
    """
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        parsed_res = parser.parse(response.content)
        question_data = parsed_res.dict()
        return {**state, "current_question": question_data, "question_count": state.get("question_count", 0) + 1}
    except Exception as e:
        # Generic fallback
        fallback = {
            "question": f"Explain the core principles of {state['role']} and how they relate to modern industry practices.",
            "topic": "General Fundamentals",
            "difficulty": state["difficulty"]
        }
        return {**state, "current_question": fallback, "question_count": state.get("question_count", 0) + 1}

async def answer_evaluation_node(state: InterviewState) -> Dict[str, Any]:
    """Evaluates the user's answer to the current question."""
    logging.info(f"Answer Evaluation Node: State keys: {list(state.keys())}")
    if not state.get('user_answer'):
        return {**state, "feedback": "No answer provided"}
        
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=InterviewEvaluation)
    
    prompt = f"""
    You are a strict technical interviewer. Evaluate the candidate's answer to the following question:
    
    Question: {state['current_question']['question']}
    Topic: {state['current_question']['topic']}
    Role: {state['role']}
    Candidate's Answer: {state['user_answer']}
    
    Requirements:
    1. Be strict and objective.
    2. Provide a score from 0 to 10.
    3. Evaluate technical correctness, depth, and communication clarity.
    4. List specific strengths and weaknesses.
    5. Provide an ideal version of this answer.
    
    {parser.get_format_instructions()}
    """
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        evaluation = parser.parse(response.content)
        
        # Update history
        history_entry = {
            "question": state['current_question']['question'],
            "answer": state['user_answer'],
            "evaluation": evaluation.dict()
        }
        new_history = state.get('question_history', []) + [history_entry]
        
        return {
            **state,
            "evaluation": evaluation.dict(),
            "score": evaluation.score,
            "question_history": new_history,
            "user_answer": None # Clear for next turn
        }
    except Exception:
        # Simple fallback
        return {**state, "score": 5, "feedback": "Manual evaluation needed due to error."}

async def adaptive_difficulty_node(state: InterviewState) -> Dict[str, Any]:
    """Adjusts the difficulty level based on the last evaluation score."""
    score = state.get('score', 5)
    current_diff = state.get('difficulty', 'intermediate')
    
    levels = ["beginner", "intermediate", "advanced"]
    current_idx = levels.index(current_diff)
    
    new_diff = current_diff
    if score >= 8:
        # Increase difficulty
        new_diff = levels[min(current_idx + 1, 2)]
    elif score <= 4:
        # Decrease difficulty
        new_diff = levels[max(current_idx - 1, 0)]
        
    return {**state, "difficulty": new_diff}

async def feedback_aggregator_node(state: InterviewState) -> Dict[str, Any]:
    """Summarizes the entire interview session and provides a final analysis."""
    history = state.get('question_history', [])
    if not history:
        return {**state, "performance_summary": {"message": "No data available."}}
        
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=InterviewSummary)
    
    prompt = f"""
    Analyze the full interview history for a candidate applying for the {state['role']} position.
    
    Interview History:
    {json.dumps(history)}
    
    Task:
    1. Calculate the final score and average.
    2. Identify strong areas and weak areas.
    3. Provide a personalized improvement plan with 3-5 actionable steps.
    
    {parser.get_format_instructions()}
    """
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = parser.parse(response.content)
        
        # Persist to DB for memory integration (Step 8)
        if state.get('user_id'):
            try:
                perf = InterviewPerformance(
                    user_id=state['user_id'],
                    role=state['role'],
                    overall_score=float(summary.average_score * 10), # scale to 100 or just keep as is
                    average_score=summary.average_score,
                    strong_areas=summary.strong_areas,
                    weak_areas=summary.weak_areas,
                    improvement_plan=summary.improvement_plan,
                    frequently_failed_topics=summary.weak_areas # using weak areas as topics to focus on
                )
                await perf.insert()
            except Exception as db_err:
                logging.error(f"Failed to store interview performance: {db_err}")

        return {**state, "performance_summary": summary.dict()}
    except Exception:
        # Basic summary fallback
        return {**state, "performance_summary": {"final_score": "N/A", "message": "Failed to aggregate summary."}}
