import os
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import AgentState
from dotenv import load_dotenv

load_dotenv()

_ROUTER_SYSTEM = """You are a query classifier for a Student Success Coach application.

Given a student's message, decide whether answering it requires fetching the student's 
personal academic data (grades, attendance, exam schedule).

Respond with EXACTLY one word:
- "yes" if the message is about the student's own performance, grades, scores, attendance, 
  exams, progress, study plan, or anything that would benefit from their academic data.
- "no" if it is a general question (concepts, definitions, how-to, motivation, general advice 
  unrelated to their personal data).

Examples:
  "What is overfitting?" → no
  "How are my grades?" → yes
  "Explain gradient descent" → no
  "Should I be worried about my attendance?" → yes
  "How can I improve my studies?" → yes
  "What is a neural network?" → no
  "I'm stressed about my upcoming exams" → yes
  "Give me a general study tip" → no
"""


def route_message(state: AgentState) -> AgentState:
    """
    Node 1: Classify whether the message needs student data.
    Sets state['needs_data'] to True or False.
    """
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
    answer = result.content.strip().lower()
    needs_data = answer.startswith("yes")

    return {**state, "needs_data": needs_data}