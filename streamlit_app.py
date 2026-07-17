"""Streamlit dashboard for person ReID presence records."""
from __future__ import annotations

import os
import re
from html import escape
from pathlib import Path
from uuid import uuid4

import pymysql
import streamlit as st
from dotenv import dotenv_values

from app.config.config import Settings
from app.utils.utils import IMAGE_SUFFIXES


st.set_page_config(page_title="Person ReID Dashboard", page_icon="👥", layout="wide")


def apply_theme() -> None:
    st.markdown("""
    <style>
        .stApp { background: radial-gradient(circle at 8% 0%, #17355d 0%, #0b1220 38%, #070b13 100%); color: #e8eef9; }
        #MainMenu, footer { visibility: hidden; }
        .block-container { max-width: 1360px; padding-top: 2rem; padding-bottom: 3rem; }
        .hero { padding: 2rem 2.2rem; border: 1px solid rgba(151, 193, 255, .24); border-radius: 22px;
                background: linear-gradient(125deg, rgba(24, 58, 99, .94), rgba(13, 25, 44, .9));
                box-shadow: 0 18px 46px rgba(0,0,0,.24); margin-bottom: 1.4rem; }
        .eyebrow { color: #75b8ff; font-size: .76rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
        .hero h1 { margin: .3rem 0; font-size: 2.2rem; letter-spacing: -.04em; color: #fff; }
        .hero p { margin: 0; color: #b8c8df; font-size: 1rem; }
        .status { display: inline-block; float: right; margin-top: -2.3rem; color: #a8f3c8; background: rgba(40, 180, 104, .14);
                  padding: .42rem .75rem; border-radius: 999px; font-size: .8rem; font-weight: 650; }
        .metric-card { min-height: 128px; padding: 1.15rem 1.2rem; border-radius: 16px;
                       background: rgba(18, 31, 52, .78); border: 1px solid rgba(167, 197, 232, .16);
                       box-shadow: 0 10px 26px rgba(0,0,0,.16); }
        .metric-name { color: #aebed4; font-size: .82rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
        .metric-value { color: #f7fbff; font-size: 1.8rem; font-weight: 740; margin-top: .5rem; letter-spacing: -.04em; }
        .metric-detail { color: #72d6a1; font-size: .84rem; margin-top: .3rem; }
        .section-title { color: #f2f7ff; font-size: 1.18rem; font-weight: 680; margin: 1.8rem 0 .65rem; }
        .stTabs [data-baseweb="tab-list"] { gap: .75rem; border-bottom: 1px solid rgba(167,197,232,.16); }
        .stTabs [data-baseweb="tab"] { height: 42px; background: transparent; color: #aebed4; border-radius: 9px 9px 0 0; }
        .stTabs [aria-selected="true"] { color: #82c3ff !important; border-bottom: 2px solid #4ca7ff !important; }
        .stButton > button { border-radius: 9px; border: 1px solid rgba(117,184,255,.46); background: #247fd2; color: white; font-weight: 650; }
        .stButton > button:hover { border-color: #8dcaff; background: #3592e9; }
        div[data-testid="stDataFrame"] { border: 1px solid rgba(167,197,232,.14); border-radius: 12px; overflow: hidden; }
        div[data-testid="stExpander"] { border-color: rgba(167,197,232,.15); border-radius: 12px; }
        [data-testid="stSidebar"] { background: #0b1422; }
    </style>
    """, unsafe_allow_html=True)


def metric_card(name: str, value: str, detail: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-name">{escape(name)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f'<div class="metric-detail">{escape(detail)}</div></div>',
        unsafe_allow_html=True,
    )


def connection():
    settings = Settings()
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        autocommit=True,
    )


@st.cache_data(ttl=3)
def load_runs() -> list[dict]:
    db = connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT id, source, started_at, completed_at
                   FROM reid_runs WHERE deleted_at IS NULL ORDER BY id DESC LIMIT 100"""
            )
            return list(cursor.fetchall())
    finally:
        db.close()


@st.cache_data(ttl=3)
def load_run_details(run_id: int) -> tuple[list[dict], list[dict]]:
    db = connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT person_name, total_seconds, entries_count, exits_count
                   FROM person_presence WHERE run_id = %s AND deleted_at IS NULL ORDER BY person_name""",
                (run_id,),
            )
            summary = list(cursor.fetchall())
            cursor.execute(
                """SELECT person_name, event_type, occurred_at
                   FROM person_presence_events WHERE run_id = %s AND deleted_at IS NULL
                   ORDER BY occurred_at""",
                (run_id,),
            )
            events = list(cursor.fetchall())
            return summary, events
    finally:
        db.close()


def delete_run(run_id: int) -> None:
    """Soft-delete a run and its records; database triggers archive each row."""
    db = connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("UPDATE person_presence_events SET deleted_at = NOW() WHERE run_id = %s AND deleted_at IS NULL", (run_id,))
            cursor.execute("UPDATE person_presence SET deleted_at = NOW() WHERE run_id = %s AND deleted_at IS NULL", (run_id,))
            cursor.execute("UPDATE reid_runs SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL", (run_id,))
        db.commit()
    finally:
        db.close()


def admin_authenticated() -> bool:
    # Read directly from the project file so a changed .env value is picked up
    # by Streamlit's reruns instead of depending on the server's old process env.
    dotenv_password = dotenv_values(Path(__file__).resolve().parent / ".env").get("REID_ADMIN_PASSWORD")
    password = dotenv_password or os.getenv("REID_ADMIN_PASSWORD", "")
    if not password:
        st.warning("Set `REID_ADMIN_PASSWORD` in `.env` to enable the admin panel.")
        return False
    if st.session_state.get("admin_authenticated"):
        return True
    entered_password = st.text_input("Admin password", type="password", key="admin_password")
    if st.button("Sign in", key="admin_sign_in"):
        if entered_password == password:
            st.session_state.admin_authenticated = True
            st.rerun()
        st.error("Incorrect admin password.")
    return False


apply_theme()
st.markdown("""
<div class="hero">
  <div class="eyebrow">Presence intelligence</div>
  <div class="status">● DATABASE CONNECTED</div>
  <h1>Person ReID Control Center</h1>
  <p>Monitor recognized visitors, review access movement, and manage enrollment data.</p>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([5, 1])
with left:
    st.caption("Live dashboard view of completed camera-processing runs")
with right:
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

dashboard_tab, admin_tab = st.tabs(["Dashboard", "Admin"])
with dashboard_tab:
    st.markdown('<div class="section-title">Run analytics</div>', unsafe_allow_html=True)
    st.caption("Known-person presence summaries and camera IN/OUT history.")
    try:
        runs = load_runs()
    except pymysql.MySQLError as error:
        st.error(f"Could not connect to MySQL: {error}")
        runs = []

    if not runs:
        st.info("No completed camera runs have been saved yet.")
    else:
        run_by_label = {
            f"Run #{run['id']} · {run['source']} · {run['started_at']}": run
            for run in runs
        }
        selected_label = st.selectbox("Camera run", list(run_by_label))
        selected_run = run_by_label[selected_label]
        st.markdown(f'<div class="section-title">Run #{selected_run["id"]}</div>', unsafe_allow_html=True)
        st.caption(f"Source: {selected_run['source']}  ·  {selected_run['started_at']} → {selected_run['completed_at']}")
        summary, events = load_run_details(selected_run["id"])
        if not summary:
            st.info("No known identities were detected in this run.")
        else:
            total_time = sum(float(person["total_seconds"]) for person in summary)
            total_entries = sum(int(person["entries_count"]) for person in summary)
            total_exits = sum(int(person["exits_count"]) for person in summary)
            overview = st.columns(3)
            with overview[0]: metric_card("Recognized people", str(len(summary)), "Distinct known identities")
            with overview[1]: metric_card("Combined presence", f"{total_time:.1f}s", f"{total_entries} total IN event(s)")
            with overview[2]: metric_card("Movement", f"{total_exits} OUT", "Confirmed leave events")
            st.markdown('<div class="section-title">Identity overview</div>', unsafe_allow_html=True)
            for start in range(0, len(summary), 4):
                columns = st.columns(min(len(summary) - start, 4))
                for column, person in zip(columns, summary[start:start + 4]):
                    with column:
                        metric_card(person["person_name"], f"{float(person['total_seconds']):.1f}s", f"IN {person['entries_count']}  ·  OUT {person['exits_count']}")
            st.markdown('<div class="section-title">Presence summary</div>', unsafe_allow_html=True)
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.markdown('<div class="section-title">IN / OUT event timeline</div>', unsafe_allow_html=True)
            if events:
                st.dataframe(events, use_container_width=True, hide_index=True)
            else:
                st.info("No completed IN/OUT transitions were recorded for this run.")

with admin_tab:
    st.markdown('<div class="section-title">Administrative workspace</div>', unsafe_allow_html=True)
    st.caption("Manage enrolled identities and stored run data.")
    if admin_authenticated():
        logout_column, _ = st.columns([1, 5])
        with logout_column:
            if st.button("Log out", key="admin_logout", use_container_width=True):
                st.session_state.pop("admin_authenticated", None)
                st.session_state.pop("admin_password", None)
                st.rerun()
        settings = Settings()
        st.markdown('<div class="section-title">Enroll known person</div>', unsafe_allow_html=True)
        identity_name = st.text_input("Identity name", placeholder="e.g. Shubham")
        images = st.file_uploader("Reference images", type=[suffix[1:] for suffix in IMAGE_SUFFIXES], accept_multiple_files=True)
        if st.button("Save enrollment images"):
            normalized_name = identity_name.strip()
            if not re.fullmatch(r"[A-Za-z0-9 _-]{1,80}", normalized_name):
                st.error("Use 1–80 letters, numbers, spaces, underscores, or hyphens for the identity name.")
            elif not images:
                st.error("Select at least one image.")
            else:
                destination = settings.gallery_dir / normalized_name
                destination.mkdir(parents=True, exist_ok=True)
                for image in images:
                    suffix = os.path.splitext(image.name)[1].lower()
                    (destination / f"{uuid4().hex}{suffix}").write_bytes(image.getvalue())
                st.success(f"Saved {len(images)} image(s) for {normalized_name}. They will be used on the next camera run.")

        st.markdown('<div class="section-title">Archive stored run</div>', unsafe_allow_html=True)
        try:
            runs = load_runs()
        except pymysql.MySQLError as error:
            st.error(f"Could not load runs: {error}")
            runs = []
        if runs:
            run_labels = {f"Run #{run['id']} · {run['source']} · {run['started_at']}": run for run in runs}
            selected_label = st.selectbox("Run to delete", list(run_labels), key="admin_run_to_delete")
            selected_run = run_labels[selected_label]
            confirmed = st.checkbox(f"I understand this hides Run #{selected_run['id']} and archives its records in deletion logs.")
            if st.button("Delete selected run", type="primary"):
                if not confirmed:
                    st.error("Confirm the deletion first.")
                else:
                    delete_run(selected_run["id"])
                    st.cache_data.clear()
                    st.success(f"Soft-deleted Run #{selected_run['id']} and archived its records.")
                    st.rerun()
