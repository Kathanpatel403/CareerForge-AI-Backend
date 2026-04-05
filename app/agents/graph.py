from typing import Literal
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents import nodes


# --- Routing Logic ---
def router(state: AgentState) -> Literal["resume_node", "skill_gap_node", "interview_node", "general_node", "end"]:
    intent = state.get("intent")
    if intent == "resume_analysis":
        return "resume_node"
    elif intent == "roadmap_generation":
        return "skill_gap_node"
    elif intent == "interview_preparation":
        return "interview_node"
    elif intent == "general_query":
        return "general_node"
    else:
        return "end"


def build_career_graph():
    """
    Assembles the full LangGraph workflow for Career Copilot chat.
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("intent_classifier", nodes.classify_intent_node)
    workflow.add_node("resume_node",       nodes.resume_analyzer_node)
    workflow.add_node("skill_gap_node",    nodes.skill_gap_node)
    workflow.add_node("roadmap_node",      nodes.roadmap_generator_node)
    workflow.add_node("interview_node",    nodes.interview_placeholder_node)
    workflow.add_node("general_node",      nodes.general_query_node)

    # Edges
    workflow.set_entry_point("intent_classifier")
    workflow.add_conditional_edges(
        "intent_classifier",
        router,
        {
            "resume_node":    "resume_node",
            "skill_gap_node": "skill_gap_node",
            "interview_node": "interview_node",
            "general_node":   "general_node",
            "end":            END,
        },
    )
    workflow.add_edge("resume_node",    "skill_gap_node")
    workflow.add_edge("skill_gap_node", "roadmap_node")
    workflow.add_edge("roadmap_node",   END)
    workflow.add_edge("interview_node", END)
    workflow.add_edge("general_node",   END)

    return workflow.compile()
