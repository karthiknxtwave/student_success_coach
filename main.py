import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from agents.conversation_agent import ConversationAgent
from sheets.client import fetch_all_students, fetch_signals, update_signal_actioned
from memory.memory_manager import load_memories, save_session

st.set_page_config(
    page_title="Success Coach AI",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 Success Coach AI")
st.caption("Your personal academic assistant.")

# --------------------------------------------------------------------------- #
#  Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:

    # --- View Toggle ---
    view = st.radio("View", ["Student", "Coach"], horizontal=True)
    st.divider()

    if view == "Student":
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
            options = {
                f"{s['name']} ({s['student_id']})": s["student_id"]
                for s in students
            }
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

        # Clear Chat
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        # End Session
        if (
            st.session_state.get("selected_student_id")
            and st.session_state.get("messages")
        ):
            if st.button("🔚 End Session"):
                with st.spinner("Saving session and detecting signals..."):
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

    else:
        st.header("🔔 Coach Filters")

        severity_filter = st.selectbox(
            "Severity", ["all", "high", "medium", "low"]
        )
        urgency_filter = st.selectbox(
            "Urgency", ["all", "today", "tomorrow", "this_week"]
        )
        actioned_filter = st.selectbox(
            "Status", ["open only", "all"]
        )

        if st.button("🔄 Refresh Signals"):
            st.session_state.pop("signals_cache", None)
            st.rerun()


# --------------------------------------------------------------------------- #
#  Student View
# --------------------------------------------------------------------------- #
if view == "Student":

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

    if not st.session_state.selected_student_id:
        st.info("👈 Please select your name from the sidebar to get started.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

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


# --------------------------------------------------------------------------- #
#  Coach View
# --------------------------------------------------------------------------- #
else:
    st.subheader("🔔 Open Signals")

    # Load and cache signals until refresh is clicked
    if "signals_cache" not in st.session_state:
        with st.spinner("Loading signals..."):
            try:
                st.session_state.signals_cache = fetch_signals()
            except Exception as e:
                st.error(f"Could not load signals: {e}")
                st.session_state.signals_cache = []

    signals = st.session_state.signals_cache

    # --- Apply filters ---
    filtered = signals

    if severity_filter != "all":
        filtered = [s for s in filtered if s.get("severity") == severity_filter]

    if urgency_filter != "all":
        filtered = [s for s in filtered if s.get("urgency") == urgency_filter]

    if actioned_filter == "open only":
        filtered = [
            s for s in filtered
            if str(s.get("actioned", "false")).lower() == "false"
        ]

    if not filtered:
        st.info("No signals match the current filters.")
    else:
        # Severity badge colours
        severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        for signal in filtered:
            icon = severity_color.get(signal.get("severity", "low"), "⚪")
            actioned = str(signal.get("actioned", "false")).lower() == "true"

            with st.expander(
                f"{icon} {signal.get('signal_type', '').replace('_', ' ').title()} "
                f"— {signal.get('student_id')} "
                f"{'✅ Actioned' if actioned else ''}",
                expanded=not actioned,
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Severity:** {signal.get('severity', '—')}")
                    st.markdown(f"**Urgency:** {signal.get('urgency', '—')}")
                with col2:
                    st.markdown(f"**Student ID:** {signal.get('student_id', '—')}")
                    st.markdown(f"**Timestamp:** {signal.get('timestamp', '—')}")

                st.markdown(f"**Reason:** {signal.get('reason', '—')}")

                if not actioned:
                    if st.button("✅ Mark as Actioned", key=f"action_{signal['row_index']}"):
                        try:
                            update_signal_actioned(signal["row_index"])
                            st.session_state.pop("signals_cache", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not update signal: {e}")