import os
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agents.state import AgentState
from prompts.coach_prompt import build_general_prompt, build_data_prompt
from dotenv import load_dotenv

load_dotenv()


def generate_response(state: AgentState) -> AgentState:
    """
    Node 3: Generate the final LLM response.
    Uses enriched prompt if student_context is available, general prompt otherwise.
    """
    llm = ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0.5,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )

    student_context = state.get("student_context")

    # Pick the right system prompt
    if student_context:
        system_prompt = build_data_prompt(student_context)
    else:
        # General query or no student selected
        student_name = None
        if student_context:
            student_name = student_context.get("name")
        system_prompt = build_general_prompt(student_name)

    # Build message history for multi-turn context
    messages = [SystemMessage(content=system_prompt)]

    for turn in state.get("chat_history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))

    # Add current message
    messages.append(HumanMessage(content=state["user_message"]))

    result = llm.invoke(messages)
    return {**state, "response": result.content}