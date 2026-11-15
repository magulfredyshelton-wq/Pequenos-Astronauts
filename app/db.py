from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import BACKEND, BD

TRAVA_MIGRACOES = 741205318


@contextmanager
def ligacao(dsn=BD):
    if not dsn:
        raise RuntimeError("Configura ASTRO_DATABASE_URL com a ligação ao PostgreSQL.")
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
        yield conn


def transaccao(conn):
    return conn.transaction()


def migrar(dsn=BD):
    aplicadas = []
    ficheiros = sorted((BACKEND / "migrations").glob("*.sql"))
    with ligacao(dsn) as conn, transaccao(conn):
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (TRAVA_MIGRACOES,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS migracoes ("
            "versao TEXT PRIMARY KEY, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        for ficheiro in ficheiros:
            if conn.execute("SELECT 1 FROM migracoes WHERE versao = %s", (ficheiro.name,)).fetchone():
                continue
            conn.execute(ficheiro.read_text(encoding="utf-8"), prepare=False)
            conn.execute("INSERT INTO migracoes(versao) VALUES (%s)", (ficheiro.name,))
            aplicadas.append(ficheiro.name)
    return aplicadas
