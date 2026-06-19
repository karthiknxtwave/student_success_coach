import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agents.state import AgentState
from prompts.coach_prompt import (
    build_general_prompt,
    build_data_prompt,
    build_knowledge_prompt,
    build_combined_prompt,
)
from dotenv import load_dotenv

load_dotenv()


def generate_response(state: AgentState) -> AgentState:
    """
    Final node: Generate the LLM response.

    Prompt is selected based on whichever context is available.
    Memory (facts + summaries) is appended to whichever prompt is chosen.

      student_context=None,  knowledge_context=None  → build_general_prompt
      student_context={...}, knowledge_context=None  → build_data_prompt
      student_context=None,  knowledge_context="..." → build_knowledge_prompt
      student_context={...}, knowledge_context="..." → build_combined_prompt
    """
    llm = ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0.5,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )

    student_context = state.get("student_context")
    knowledge_context = state.get("knowledge_context")
    memories = state.get("memories")
    recent_summaries = state.get("recent_summaries")

    # --- Select the right prompt based on available context ---
    if student_context and knowledge_context:
        system_prompt = build_combined_prompt(
            student_context, knowledge_context, memories, recent_summaries
        )

    elif student_context:
        system_prompt = build_data_prompt(
            student_context, memories, recent_summaries
        )

    elif knowledge_context:
        system_prompt = build_knowledge_prompt(
            knowledge_context, None, memories, recent_summaries
        )

    else:
        system_prompt = build_general_prompt(
            None, memories, recent_summaries
        )

    # --- Build message history for multi-turn memory ---
    messages = [SystemMessage(content=system_prompt)]

    for turn in state.get("chat_history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))

    messages.append(HumanMessage(content=state["user_message"]))
    print("generating final response")
    result = llm.invoke(messages)
    print("final response generated")
    return {**state, "response": result.content}