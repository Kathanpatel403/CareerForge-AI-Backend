from typing import Dict, Any, Optional
from app.agents.graph import build_career_graph
from app.agents.state import AgentState, IntentResponse
from app.agents.nodes import get_llm
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from app.services.file_service import extract_text_from_file

# Initialize graph
graph = build_career_graph()

async def classify_intent(user_input: str) -> str:
    """
    Exposed service function to classify intent.
    """
    llm = get_llm()
    parser = PydanticOutputParser(pydantic_object=IntentResponse)
    
    prompt = f"""
    Classify the intent of the following user input:
    - resume_analysis
    - roadmap_generation
    - interview_preparation
    - general_query
    
    User input: {user_input}
    
    {parser.get_format_instructions()}
    """
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        parsed_res = parser.parse(response.content)
        return parsed_res.intent
    except:
        return "general_query"

async def run_copilot_graph(user_input: str, file_content: Optional[bytes] = None, filename: Optional[str] = None):
    """
    Orchestrates the LangGraph execution for the career assistant.
    """
    # 1. Extract text from file if provided
    text = ""
    if file_content and filename:
        text = await extract_text_from_file(file_content, filename)
    
    # 2. Initial State
    initial_state: AgentState = {
        "user_input": user_input,
        "intent": None,
        "resume_data": None,
        "skill_gap": None,
        "roadmap": None,
        "file_content": text,
        "session_id": None,
        "error": None
    }
    
    # 3. Execute Graph
    final_state = await graph.ainvoke(initial_state)
    return final_state
