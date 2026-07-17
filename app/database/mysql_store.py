"""MySQL persistence for completed person-presence runs."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from app.services.presence import Presence, PresenceEvent


class MySQLPresenceStore:
    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        try:
            import pymysql as mysql
        except ModuleNotFoundError as error:
            raise RuntimeError("Install pymysql to enable MySQL storage.") from error
        self._connector = mysql
        self._connection = mysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
        )
        try:
            self._create_tables()
        except Exception:
            self._connection.close()
            raise

    def _create_tables(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute("SHOW TABLES")
        existing_tables = {row[0] for row in cursor.fetchall()}
        if "reid_runs" not in existing_tables:
            cursor.execute("""
                CREATE TABLE reid_runs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                source VARCHAR(512) NOT NULL,
                started_at DATETIME NOT NULL,
                completed_at DATETIME NOT NULL
                )
            """)
        if "person_presence" not in existing_tables:
            cursor.execute("""
                CREATE TABLE person_presence (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id BIGINT NOT NULL,
                person_name VARCHAR(255) NOT NULL,
                total_seconds DECIMAL(12, 3) NOT NULL,
                entries_count INT NOT NULL,
                exits_count INT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES reid_runs(id)
                )
            """)
        if "person_presence_events" not in existing_tables:
            cursor.execute("""
                CREATE TABLE person_presence_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id BIGINT NOT NULL,
                person_name VARCHAR(255) NOT NULL,
                event_type ENUM('IN', 'OUT') NOT NULL,
                occurred_at DATETIME NOT NULL,
                INDEX idx_presence_events_run_time (run_id, occurred_at)
                )
            """)
        self._connection.commit()
        cursor.close()

    def save_run(
        self,
        source: str | int,
        started_at: datetime,
        completed_at: datetime,
        records: Mapping[str, Presence],
        events: list[PresenceEvent],
    ) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO reid_runs (source, started_at, completed_at) VALUES (%s, %s, %s)",
            (str(source), started_at, completed_at),
        )
        run_id = cursor.lastrowid
        cursor.executemany(
            """INSERT INTO person_presence
               (run_id, person_name, total_seconds, entries_count, exits_count)
               VALUES (%s, %s, %s, %s, %s)""",
            [(run_id, name, record.total_seconds, record.entries, record.exits)
             for name, record in records.items()],
        )
        if events:
            cursor.executemany(
                """INSERT INTO person_presence_events
                   (run_id, person_name, event_type, occurred_at)
                   VALUES (%s, %s, %s, %s)""",
                [(run_id, event.person_name, event.event_type, event.occurred_at)
                 for event in events],
            )
        self._connection.commit()
        cursor.close()

    def close(self) -> None:
        self._connection.close()
