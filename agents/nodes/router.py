import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import AgentState
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# ROUTER PROMPT — edit this block to tune classification behaviour
# ---------------------------------------------------------------------------
_ROUTER_SYSTEM = """You are a query classifier for a Student Success Coach application.
Students are enrolled in Data Science or Full Stack Development programs.

Given a student's message, classify it into EXACTLY one of these four categories:

  general        — General advice, motivation, study tips, emotional support,
                   career guidance, or anything that does not require student
                   records or knowledge base retrieval.

  student_data   — Requires the student's personal academic records such as
                   grades, attendance, exam schedule, scores, progress, or
                   performance metrics.

  knowledge_base — Requires information from CCBP-specific documentation,
                   portal features, workflows, policies, certifications,
                   growth cycles, milestones, placements, exams, navigation,
                   or any platform-specific process.

  both           — Requires BOTH student academic data and knowledge base
                   information to answer effectively.

Respond with EXACTLY one word from:
general
student_data
knowledge_base
both

No punctuation.
No explanation.
One word only.

Classification examples:

"How do I stay motivated?"                               → general
"Give me study tips for exams"                           → general

"What is my attendance percentage?"                      → student_data
"How are my grades this month?"                          → student_data
"When is my next exam?"                                  → student_data

"How do Growth Cycles work?"                             → knowledge_base
"How do I get my certificate?"                           → knowledge_base
"What are Milestones?"                                   → knowledge_base
"How do placements work?"                                → knowledge_base
"Where can I find Bonus Courses?"                        → knowledge_base

"Based on my attendance, what should I focus on next?"   → both
"I failed an exam, what is the next process?"            → both
"Which Growth Cycle am I in and what unlocks next?"      → both
"""
# ---------------------------------------------------------------------------


def route_message(state: AgentState) -> AgentState:
    """
    Node 1: Classify the student's message into one of four routes.
    Sets state['route'] to: general | student_data | knowledge_base | both
    """
    print("inside router")
    llm = ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )

    messages = [
        SystemMessage(content=_ROUTER_SYSTEM),
        HumanMessage(content=state["user_message"]),
    ]

    result = llm.invoke(messages)
    raw = result.content.strip().lower()

    # Fallback to "general" if the model returns something unexpected
    valid_routes = {"general", "student_data", "knowledge_base", "both"}
    route = raw if raw in valid_routes else "general"
    print(f"routed to {state['route']}")
    return {**state, "route": route}