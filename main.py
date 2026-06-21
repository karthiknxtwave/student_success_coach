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
    update_plan_event_id,
)
from memory.memory_manager import load_memories, save_session
from coaching_plan.plan_generator import build_daily_plan
from coaching_plan.calendar_client import (
    create_coaching_event,
    cancel_coaching_event,
    DEFAULT_COACH_ID,
)
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

        if st.session_state.get("selected_student_name"):
            st.success(f"Logged in as: **{st.session_state.selected_student_name}**")

        # End Session button is rendered AFTER chat handling further down in
        # this script (see bottom of Student View block) — NOT here. Streamlit
        # runs top-to-bottom in a single pass, so if it were rendered here it
        # would always reflect messages from BEFORE the current message was
        # sent, making the button appear to "lag" by one interaction.


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

    # --- End Session (rendered after chat handling so it reflects the
    #     up-to-date message count from THIS run, not the previous one) ---
    with st.sidebar:
        if (
            st.session_state.get("selected_student_id")
            and st.session_state.get("messages")
        ):
            st.divider()
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


# --------------------------------------------------------------------------- #
#  Coach View
# --------------------------------------------------------------------------- #
else:
    st.subheader("🗓️ Daily Coaching Plan")

    today_str = date.today().isoformat()

    def _todays_approved_rows() -> list[dict]:
        """Rows already locked in for today (status approved or completed)."""
        return [
            p for p in fetch_daily_plans(plan_date=today_str)
            if p.get("status") in ("approved", "completed")
        ]

    def _build_fresh_draft() -> dict:
        """Run the deterministic planner on the current open-signal pool."""
        open_signals = fetch_open_signals()
        student_lookup = {
            s["student_id"]: s["name"] for s in fetch_all_students()
        }
        return build_daily_plan(open_signals, student_lookup)

    approved_today = _todays_approved_rows()
    plan_exists_today = len(approved_today) > 0

    col_gen, col_refresh, col_status = st.columns([1, 1, 2])

    # --- First-time generation (no approved plan exists yet today) ---
    with col_gen:
        if not plan_exists_today:
            if st.button("✨ Generate Daily Plan"):
                with st.spinner("Building today's plan from open signals..."):
                    try:
                        st.session_state.draft_plan = _build_fresh_draft()
                        st.session_state.draft_plan_date = today_str
                        st.session_state.is_refresh = False
                    except Exception as e:
                        st.error(f"Could not generate plan: {e}")
        else:
            st.caption("✅ Plan generated for today")

    # --- Refresh: only meaningful once a plan has been approved today ---
    with col_refresh:
        if plan_exists_today:
            if st.button("🔄 Refresh Plan"):
                with st.spinner("Checking for urgent changes..."):
                    try:
                        new_draft = _build_fresh_draft()
                        new_ids = {p["student_id"] for p in new_draft["scheduled"]}
                        current_ids = {p["student_id"] for p in approved_today}

                        if new_ids == current_ids:
                            st.session_state.draft_plan = None
                            st.session_state.refresh_message = "Plan updated. No changes — today's schedule stays the same."
                        else:
                            st.session_state.draft_plan = new_draft
                            st.session_state.draft_plan_date = today_str
                            st.session_state.is_refresh = True
                            st.session_state.refresh_message = None
                    except Exception as e:
                        st.error(f"Could not refresh plan: {e}")

    if st.session_state.get("refresh_message"):
        st.success(st.session_state.refresh_message)
        st.session_state.refresh_message = None

    draft = st.session_state.get("draft_plan")

    # --- Show today's locked-in schedule when there's no pending draft ---
    if not draft and plan_exists_today:
        st.markdown("### Today's Scheduled Sessions")
        for plan in approved_today:
            with st.container(border=True):
                st.markdown(
                    f"**{plan['student_name']}** ({plan['student_id']}) "
                    f"— {plan['session_type']} ({plan['duration_minutes']} min) "
                    f"— *{plan['status']}*"
                )
                st.caption(plan["reason"])

    if not draft and not plan_exists_today:
        st.info("Click **Generate Daily Plan** to build today's draft from open signals.")

    # --- Draft review (first-time generation OR a refresh found changes) ---
    if draft:
        scheduled = draft["scheduled"]
        deferred = draft["deferred"]

        if st.session_state.get("is_refresh"):
            st.warning("⚠️ Urgent signals changed today's priorities. Review the updated plan below.")

        st.markdown(f"### Today's Sessions ({len(scheduled)} scheduled)")

        if not scheduled:
            st.info("No open signals — nothing to schedule today.")

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
            st.markdown(f"### Deferred ({len(deferred)})")
            st.caption("Their signals remain open and will be reconsidered next time a plan is generated or refreshed.")
            for plan in deferred:
                with st.container(border=True):
                    st.markdown(f"**{plan['student_name']}** ({plan['student_id']})")
                    st.markdown(f"Signals: {', '.join(plan['signals'])}")
                    st.markdown(f"Priority Score: {plan['priority_score']}")
                    st.caption(plan["defer_reason"])

        st.divider()

        approve_label = (
            "✅ Approve Updated Plan" if st.session_state.get("is_refresh")
            else "✅ Approve Plan & Create Calendar Events"
        )

        if scheduled and st.button(approve_label):
            with st.spinner("Saving plan and syncing calendar..."):
                try:
                    approved = [
                        p for i, p in enumerate(scheduled)
                        if i not in removed_indices
                    ]
                    approved_student_ids = {p["student_id"] for p in approved}

                    # --- Cancel events for students who were approved before
                    #     but are no longer in the new approved set ---
                    if st.session_state.get("is_refresh"):
                        for old_row in approved_today:
                            if old_row["student_id"] not in approved_student_ids:
                                event_id = old_row.get("event_id", "")
                                if event_id:
                                    cancel_coaching_event(event_id, coach_id=DEFAULT_COACH_ID)
                                update_plan_status(old_row["row_index"], "deferred")
                                update_plan_event_id(old_row["row_index"], "")

                    # --- Determine which approved students are genuinely new
                    #     (need a fresh calendar event) vs already-approved
                    #     today (keep their existing event, skip creation) ---
                    already_approved_ids = {r["student_id"] for r in approved_today}
                    new_plan_rows = []
                    event_links = []

                    for i, plan in enumerate(approved):
                        if plan["student_id"] in already_approved_ids:
                            # Already scheduled today — leave their row/event alone
                            continue

                        start_dt = datetime.combine(
                            date.today(), start_times[scheduled.index(plan)]
                        ).isoformat()
                        result = create_coaching_event(
                            student_name=plan["student_name"],
                            student_id=plan["student_id"],
                            session_type=plan["session_type"],
                            signals=plan["signals"],
                            reason=plan["reason"],
                            start_time=start_dt,
                            duration_minutes=plan["duration_minutes"],
                            coach_id=DEFAULT_COACH_ID,
                        )
                        event_links.append(result["link"])
                        new_plan_rows.append({
                            **plan,
                            "status": "approved",
                            "event_id": result["event_id"],
                        })

                    if new_plan_rows:
                        append_daily_plans(
                            new_plan_rows,
                            plan_date=st.session_state.draft_plan_date,
                            coach_id=DEFAULT_COACH_ID,
                        )

                    st.session_state.draft_plan = None
                    st.session_state.is_refresh = False
                    st.success(
                        f"Plan approved! {len(new_plan_rows)} new calendar event(s) created."
                    )
                    for link in event_links:
                        st.markdown(f"- [View event]({link})")

                except Exception as e:
                    st.error(f"Could not approve plan: {e}")

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

    st.divider()

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