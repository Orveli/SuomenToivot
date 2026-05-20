"""Tietokantakerros: yhteys, skeeman alustus, apufunktiot."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from . import config


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Luo skeema (idempotentti)."""
    sql = config.SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


@contextmanager
def session(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        init_db(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_ingest_state(conn, job: str, *, last_pk=None, last_page=None,
                     status=None, n_items=None, note=None) -> None:
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    row = conn.execute("SELECT * FROM ingest_state WHERE job=?", (job,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO ingest_state(job,last_pk,last_page,status,n_items,updated_at,note)"
            " VALUES(?,?,?,?,?,?,?)",
            (job, last_pk, last_page, status or "running", n_items or 0, now, note),
        )
    else:
        conn.execute(
            "UPDATE ingest_state SET last_pk=COALESCE(?,last_pk),"
            " last_page=COALESCE(?,last_page), status=COALESCE(?,status),"
            " n_items=COALESCE(?,n_items), updated_at=?, note=COALESCE(?,note) WHERE job=?",
            (last_pk, last_page, status, n_items, now, note, job),
        )
    conn.commit()


def get_ingest_state(conn, job: str):
    return conn.execute("SELECT * FROM ingest_state WHERE job=?", (job,)).fetchone()


def add_coverage(conn, metric: str, dimension: str, value) -> None:
    import datetime as _dt
    conn.execute(
        "INSERT INTO coverage_stat(metric,dimension,value,computed_at) VALUES(?,?,?,?)",
        (metric, dimension, str(value), _dt.datetime.now(_dt.timezone.utc).isoformat()),
    )


def executemany(conn, sql: str, rows: Iterable[tuple]) -> int:
    cur = conn.executemany(sql, list(rows))
    return cur.rowcount
