"""Streamlit dashboard for person ReID presence records."""
from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pymysql
import streamlit as st
from dotenv import dotenv_values

from app.config.config import Settings
from app.utils.utils import IMAGE_SUFFIXES


st.set_page_config(page_title="Person ReID Dashboard", page_icon="👥", layout="wide")


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


st.title("Person ReID Dashboard")
if st.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

dashboard_tab, admin_tab = st.tabs(["Dashboard", "Admin"])
with dashboard_tab:
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
        st.subheader(f"Run #{selected_run['id']}")
        st.caption(f"Source: {selected_run['source']} · {selected_run['started_at']} → {selected_run['completed_at']}")
        summary, events = load_run_details(selected_run["id"])
        if not summary:
            st.info("No known identities were detected in this run.")
        else:
            columns = st.columns(len(summary))
            for column, person in zip(columns, summary):
                with column:
                    st.metric(person["person_name"], f"{float(person['total_seconds']):.1f}s")
                    st.caption(f"IN: {person['entries_count']} · OUT: {person['exits_count']}")
            st.subheader("Presence summary")
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.subheader("IN / OUT event timeline")
            if events:
                st.dataframe(events, use_container_width=True, hide_index=True)
            else:
                st.info("No completed IN/OUT transitions were recorded for this run.")

with admin_tab:
    st.caption("Manage enrolled identities and stored run data.")
    if admin_authenticated():
        settings = Settings()
        st.subheader("Enroll known person")
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

        st.subheader("Delete stored run")
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
