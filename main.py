import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from agents.conversation_agent import ConversationAgent
from sheets.client import fetch_all_students
from memory.memory_manager import load_memories, save_session

st.set_page_config(
    page_title="Success Coach AI",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 Success Coach AI")
st.caption("Your personal academic assistant.")

# --------------------------------------------------------------------------- #
#  Sidebar — Student Selector + Session Controls
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("👤 Student")

    # Load student list once per session
    if "student_list" not in st.session_state:
        with st.spinner("Loading students..."):
            try:
                all_students = fetch_all_students()
                st.session_state.student_list = all_students
            except Exception as e:
                st.error(f"Could not load students: {e}")
                st.session_state.student_list = []

    students = st.session_state.student_list

    if students:
        options = {f"{s['name']} ({s['student_id']})": s["student_id"] for s in students}
        display_names = ["— Select student —"] + list(options.keys())

        selected_display = st.selectbox("Select your name", display_names)

        if selected_display == "— Select student —":
            st.session_state.selected_student_id = ""
            st.session_state.selected_student_name = ""
        else:
            new_id = options[selected_display]

            # New student selected — reset chat and load their memories
            if st.session_state.get("selected_student_id") != new_id:
                st.session_state.messages = []

                with st.spinner("Loading your history..."):
                    try:
                        mem = load_memories(new_id)
                        st.session_state.memories = mem["memories"]
                        st.session_state.recent_summaries = mem["recent_summaries"]
                    except Exception as e:
                        st.warning(f"Could not load memory: {e}")
                        st.session_state.memories = None
                        st.session_state.recent_summaries = None

            st.session_state.selected_student_id = new_id
            st.session_state.selected_student_name = selected_display.split(" (")[0]
    else:
        st.info("No students found in the roster.")
        st.session_state.selected_student_id = ""
        st.session_state.selected_student_name = ""

    st.divider()

    # Clear Chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    # End Session button — only shown when student is selected and chat is not empty
    if (
        st.session_state.get("selected_student_id")
        and st.session_state.get("messages")
    ):
        if st.button("🔚 End Session"):
            with st.spinner("Saving session..."):
                try:
                    save_session(
                        student_id=st.session_state.selected_student_id,
                        chat_history=st.session_state.messages,
                    )
                    st.session_state.messages = []
                    st.session_state.memories = None
                    st.session_state.recent_summaries = None
                    st.success("Session saved! See you next time. 👋")
                except Exception as e:
                    st.error(f"Could not save session: {e}")

    if st.session_state.get("selected_student_name"):
        st.success(f"Logged in as: **{st.session_state.selected_student_name}**")


# --------------------------------------------------------------------------- #
#  Main Chat Area
# --------------------------------------------------------------------------- #

# Initialise state
if "agent" not in st.session_state:
    st.session_state.agent = ConversationAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_student_id" not in st.session_state:
    st.session_state.selected_student_id = ""

if "memories" not in st.session_state:
    st.session_state.memories = None

if "recent_summaries" not in st.session_state:
    st.session_state.recent_summaries = None

# Show a prompt to select student if none chosen
if not st.session_state.selected_student_id:
    st.info("👈 Please select your name from the sidebar to get started.")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
prompt = st.chat_input(
    "Type your question...",
    disabled=not st.session_state.selected_student_id,
)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = st.session_state.agent.chat(
                message=prompt,
                student_id=st.session_state.selected_student_id,
                chat_history=st.session_state.messages[:-1],
                memories=st.session_state.memories,
                recent_summaries=st.session_state.recent_summaries,
            )
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})