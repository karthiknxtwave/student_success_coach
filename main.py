import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, datetime

import streamlit as st
from agents.conversation_agent import ConversationAgent
from sheets.client import (
    fetch_all_students,
    fetch_open_signals,
    fetch_daily_plans,
    append_daily_plans,
    update_plan_status,
)
from memory.memory_manager import load_memories, save_session
from coaching_plan.plan_generator import build_daily_plan
from coaching_plan.calendar_client import create_coaching_event, DEFAULT_COACH_ID
from signals.brief_generator import generate_brief
from memory.mem0_client import get_facts, get_summaries
from sheets.client import build_student_context

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
#  Coach View — Daily Coaching Plan (signals shown inline per student)
# --------------------------------------------------------------------------- #
else:
    st.subheader("🗓️ Daily Coaching Plan")

    today_str = date.today().isoformat()

    col_gen, col_status = st.columns([1, 3])
    with col_gen:
        if st.button("✨ Generate Daily Plan"):
            with st.spinner("Building today's plan from open signals..."):
                try:
                    open_signals = fetch_open_signals()
                    student_lookup = {
                        s["student_id"]: s["name"]
                        for s in fetch_all_students()
                    }
                    st.session_state.draft_plan = build_daily_plan(
                        open_signals, student_lookup
                    )
                    st.session_state.draft_plan_date = today_str
                except Exception as e:
                    st.error(f"Could not generate plan: {e}")

    draft = st.session_state.get("draft_plan")

    if not draft:
        st.info("Click **Generate Daily Plan** to build today's draft from open signals.")
    else:
        scheduled = draft["scheduled"]
        deferred = draft["deferred"]

        st.markdown(f"### Today's Sessions ({len(scheduled)} scheduled)")

        if not scheduled:
            st.info("No open signals — nothing to schedule today.")

        # Editable draft — coach can remove sessions and adjust start time
        removed_indices = set()
        start_times = {}

        for i, plan in enumerate(scheduled):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{plan['student_name']}** ({plan['student_id']})")
                    st.markdown(f"Session Type: **{plan['session_type']}**")
                    st.markdown(f"Signals: {', '.join(plan['signals'])}")
                    st.caption(plan["reason"])
                with col2:
                    st.markdown(f"Priority Score: **{plan['priority_score']}**")
                    st.markdown(f"Duration: **{plan['duration_minutes']} min**")
                    start_times[i] = st.time_input(
                        "Start time", key=f"start_{i}", label_visibility="collapsed"
                    )
                with col3:
                    if st.checkbox("Remove", key=f"remove_{i}"):
                        removed_indices.add(i)

        if deferred:
            st.markdown(f"### Deferred to Tomorrow ({len(deferred)})")
            for plan in deferred:
                with st.container(border=True):
                    st.markdown(f"**{plan['student_name']}** ({plan['student_id']})")
                    st.markdown(f"Signals: {', '.join(plan['signals'])}")
                    st.markdown(f"Priority Score: {plan['priority_score']}")
                    st.caption(plan["defer_reason"])

        st.divider()

        # Approve — writes to sheet + creates calendar events for kept sessions
        if scheduled and st.button("✅ Approve Plan & Create Calendar Events"):
            with st.spinner("Saving plan and creating calendar events..."):
                try:
                    approved = [
                        p for i, p in enumerate(scheduled)
                        if i not in removed_indices
                    ]

                    plan_rows = [
                        {**p, "status": "approved"} for p in approved
                    ] + [
                        {**p, "priority_score": p["priority_score"],
                         "session_type": "", "duration_minutes": 0,
                         "reason": p["defer_reason"], "status": "deferred"}
                        for p in deferred
                    ]

                    append_daily_plans(
                        plan_rows,
                        plan_date=st.session_state.draft_plan_date,
                        coach_id=DEFAULT_COACH_ID,
                    )

                    event_links = []
                    for i, plan in enumerate(approved):
                        start_dt = datetime.combine(
                            date.today(), start_times[scheduled.index(plan)]
                        ).isoformat()
                        link = create_coaching_event(
                            student_name=plan["student_name"],
                            student_id=plan["student_id"],
                            session_type=plan["session_type"],
                            signals=plan["signals"],
                            reason=plan["reason"],
                            start_time=start_dt,
                            duration_minutes=plan["duration_minutes"],
                            coach_id=DEFAULT_COACH_ID,
                        )
                        event_links.append(link)

                    st.session_state.draft_plan = None
                    st.success(
                        f"Plan approved! {len(approved)} calendar event(s) created."
                    )
                    for link in event_links:
                        st.markdown(f"- [View event]({link})")

                except Exception as e:
                    st.error(f"Could not approve plan: {e}")

    st.divider()

    st.divider()

    # --- Pre-Meeting Student Brief ---
    st.markdown("### 📋 Pre-Meeting Student Brief")

    # Student selector (independent of Daily Plan flow)
    brief_students = st.session_state.get("student_list") or fetch_all_students()
    brief_options = {f"{s['name']} ({s['student_id']})": s["student_id"] for s in brief_students}
    brief_display_names = ["— Select student —"] + list(brief_options.keys())
    brief_selected = st.selectbox("Select student for brief", brief_display_names, key="brief_student_select")

    if brief_selected != "— Select student —":
        brief_student_id = brief_options[brief_selected]

        if st.button("📋 Generate Brief", key="generate_brief_btn"):
            with st.spinner("Generating pre-meeting brief..."):
                try:
                    ctx       = build_student_context(brief_student_id)
                    signals   = fetch_open_signals(brief_student_id)
                    facts     = get_facts(brief_student_id)
                    summaries = get_summaries(brief_student_id)

                    result = generate_brief(
                        student_id=brief_student_id,
                        student_context=ctx,
                        open_signals=signals,
                        facts=facts,
                        summaries=summaries,
                    )
                    st.session_state.brief_result = result
                except Exception as e:
                    st.error(f"Could not generate brief: {e}")

    if st.session_state.get("brief_result"):
        result = st.session_state.brief_result
        with st.container(border=True):
            st.markdown(result["brief"])
            if result.get("questions"):
                st.markdown("**Conversation starters:**")
                for q in result["questions"]:
                    st.markdown(f"- {q}")

    # --- Today's approved sessions with Mark Done ---
    st.markdown("### Today's Approved Sessions")
    try:
        todays_plans = [
            p for p in fetch_daily_plans(plan_date=today_str)
            if p.get("status") in ("approved", "planned")
        ]
    except Exception as e:
        st.error(f"Could not load today's plans: {e}")
        todays_plans = []

    if not todays_plans:
        st.caption("No approved sessions yet today.")
    else:
        for plan in todays_plans:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f"**{plan['student_name']}** ({plan['student_id']}) "
                        f"— {plan['session_type']} ({plan['duration_minutes']} min)"
                    )
                    st.caption(plan["reason"])
                with col2:
                    if st.button("✔️ Mark Done", key=f"done_{plan['row_index']}"):
                        try:
                            update_plan_status(plan["row_index"], "completed")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not update status: {e}")