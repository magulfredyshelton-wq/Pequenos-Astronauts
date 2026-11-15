"""Importação única das demos anteriores para uma base PostgreSQL nova."""

from argparse import ArgumentParser
from contextlib import closing
from datetime import datetime, timezone
from itertools import islice
import json
from pathlib import Path
import sqlite3

from psycopg import OperationalError, sql
from psycopg.types.json import Jsonb

from app.config import BD
from app.db import ligacao, migrar, transaccao

TABELAS = {
    "contas": ("id", "nome", "idade", "confirmada_em", "nickname"),
    "partidas": ("codigo", "revisao", "estado", "criada_em"),
    "jogadores": ("id", "partida", "nome", "nivel", "segredo_hash", "anfitriao", "conta_id"),
    "presencas": ("jogador", "vista_em", "x", "z"),
    "comandos": ("partida", "jogador", "id", "pedido", "resposta"),
    "mensagens": ("id", "partida", "jogador", "chave", "enviada_em", "texto", "formato", "audio"),
}
OPCIONAIS = {"contas": {"nickname"}, "jogadores": {"conta_id"}}


def converter(tabela, coluna, valor):
    if coluna in {"estado", "resposta"}:
        return Jsonb(json.loads(valor))
    if tabela == "partidas" and coluna == "criada_em":
        data = datetime.fromisoformat(valor)
        return data.replace(tzinfo=timezone.utc) if data.tzinfo is None else data
    if tabela == "presencas" and coluna == "vista_em":
        return 0
    return valor


def copiar(origem, destino, tabela, colunas):
    disponiveis = {coluna[1] for coluna in origem.execute(f"PRAGMA table_info({tabela})")}
    if not disponiveis and tabela == "mensagens":
        return 0
    if set(colunas) - disponiveis - OPCIONAIS.get(tabela, set()):
        raise ValueError(f"A tabela {tabela} tem uma estrutura antiga ou inválida.")
    linhas = origem.execute(f"SELECT * FROM {tabela}")
    consulta = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(tabela),
        sql.SQL(", ").join(map(sql.Identifier, colunas)),
        sql.SQL(", ").join(sql.Placeholder() for _ in colunas),
    )
    total = 0
    with destino.cursor() as cursor:
        while lote := list(islice(linhas, 250)):
            cursor.executemany(consulta, [
                tuple(converter(tabela, coluna, linha[coluna]) if coluna in disponiveis else None
                      for coluna in colunas)
                for linha in lote
            ])
            total += len(lote)
    return total


def importar(caminho, dsn=BD):
    caminho = Path(caminho).resolve(strict=True)
    with closing(sqlite3.connect(caminho.as_uri() + "?mode=ro", uri=True)) as origem:
        origem.row_factory = sqlite3.Row
        origem.execute("BEGIN")
        if not origem.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'partidas'").fetchone():
            raise ValueError("O ficheiro não contém uma base da demo.")
        migrar(dsn)

        with ligacao(dsn) as destino, transaccao(destino):
            tabelas = tuple(TABELAS) + ("sessoes_conta", "convites", "convites_conta")
            destino.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
                sql.SQL(", ").join(map(sql.Identifier, tabelas))
            ))
            for tabela in tabelas:
                if destino.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(tabela))).fetchone():
                    raise ValueError("A base PostgreSQL já contém dados. Usa uma base vazia para a importação.")

            totais = {tabela: copiar(origem, destino, tabela, colunas) for tabela, colunas in TABELAS.items()}
            proximo = destino.execute("SELECT coalesce(max(id), 0) + 1 AS id FROM mensagens").fetchone()["id"]
            destino.execute(sql.SQL("ALTER TABLE mensagens ALTER COLUMN id RESTART WITH {}").format(
                sql.Literal(proximo)
            ))
            return totais


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("ficheiro", type=Path, help="Cópia da base .sqlite3 da demo anterior")
    args = parser.parse_args()
    try:
        totais = importar(args.ficheiro)
    except OperationalError:
        parser.exit(1, "Não foi possível ligar ao PostgreSQL. Confirma o serviço e ASTRO_DATABASE_URL.\n")
    except (OSError, ValueError, sqlite3.Error) as erro:
        parser.exit(1, f"Importação interrompida: {erro}\n")
    for tabela, total in totais.items():
        print(f"{tabela}: {total}")
