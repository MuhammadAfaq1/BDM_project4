"""Postgres helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from pgvector.psycopg import register_vector

from rico_pipeline.config import POSTGRES_DSN


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(POSTGRES_DSN) as conn:
        register_vector(conn)
        yield conn


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> Any:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[tuple]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()
