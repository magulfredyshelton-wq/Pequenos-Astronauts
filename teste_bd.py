import os
import unittest
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.db import ligacao


def esquema_temporario(caso):
    dsn = os.getenv("ASTRO_TEST_DATABASE_URL")
    if not dsn:
        raise unittest.SkipTest("Define ASTRO_TEST_DATABASE_URL para testar com PostgreSQL.")
    nome = "teste_" + uuid4().hex
    esquema = sql.Identifier(nome)
    with ligacao(dsn) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(esquema))

    def limpar():
        with ligacao(dsn) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(esquema))

    caso.addCleanup(limpar)
    opcoes = conninfo_to_dict(dsn).get("options", "")
    return make_conninfo(dsn, options=f"{opcoes} -c search_path={nome}".strip())
