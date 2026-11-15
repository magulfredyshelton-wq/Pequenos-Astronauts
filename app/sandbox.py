"""Resultados do cliente 2D sandbox: guardar missões terminadas, listar as da conta e um ranking por nickname."""
import json
import re

from psycopg.types.json import Jsonb

from .db import ligacao
from .erros import Erro

DESTINOS = ("lua", "marte")
RESULTADOS = ("ok", "traje", "rad", "ar", "agua", "comida")
PLANOS = ("curta", "media", "longa")
CHAVE = re.compile(r"[A-Za-z0-9_-]{8,64}")


def inteiro(valor, minimo, maximo, nome):
    if type(valor) is not int or not minimo <= valor <= maximo:
        raise Erro(400, f"O campo {nome} é inválido.")
    return valor


def numero(valor, minimo, maximo, nome):
    if type(valor) not in (int, float) or isinstance(valor, bool) or not minimo <= valor <= maximo:
        raise Erro(400, f"O campo {nome} é inválido.")
    return float(valor)


def frases(valor, maximo, comprimento, nome):
    if not isinstance(valor, list) or len(valor) > maximo or not all(isinstance(t, str) and len(t) <= comprimento for t in valor):
        raise Erro(400, f"O campo {nome} é inválido.")
    return valor


def validar(corpo):
    chave = corpo.get("chave")
    if not isinstance(chave, str) or not CHAVE.fullmatch(chave):
        raise Erro(400, "A chave da missão é inválida.")
    destino = corpo.get("destino")
    destino = destino.lower() if isinstance(destino, str) else ""
    if destino not in DESTINOS:
        raise Erro(400, "O destino é inválido.")
    resultado = corpo.get("resultado")
    if resultado not in RESULTADOS:
        raise Erro(400, "O resultado é inválido.")
    estrelas = inteiro(corpo.get("estrelas"), 0, 3, "estrelas")
    if (resultado == "ok") == (estrelas == 0):
        raise Erro(400, "As estrelas não correspondem ao resultado.")
    recursos = corpo.get("recursos")
    if not isinstance(recursos, dict) or set(recursos) - {"ar", "agua", "comida", "energia", "rad"}:
        raise Erro(400, "Os recursos são inválidos.")
    recursos = {k: round(numero(v, 0, 150, "recursos"), 1) for k, v in recursos.items()}
    evas = corpo.get("evas")
    if not isinstance(evas, list) or len(evas) > 30:
        raise Erro(400, "As EVAs são inválidas.")
    lista = []
    for e in evas:
        if not isinstance(e, dict) or e.get("plano") not in PLANOS:
            raise Erro(400, "As EVAs são inválidas.")
        lista.append({"plano": e["plano"], "maxDist": inteiro(e.get("maxDist"), 0, 5000, "evas"),
                      "suitMin": inteiro(e.get("suitMin"), 0, 5000, "evas")})
    return {
        "chave": chave, "destino": destino, "resultado": resultado, "estrelas": estrelas,
        "hora": numero(corpo.get("hora"), 0, 100, "hora"),
        "base_nivel": inteiro(corpo.get("baseNivel", 0), 0, 3, "baseNivel"),
        "amostras": inteiro(corpo.get("amostrasAnalisadas", 0), 0, 500, "amostrasAnalisadas"),
        "comida": numero(corpo.get("comidaProduzida", 0), 0, 100000, "comidaProduzida"),
        "dados": {"recursos": recursos, "evas": lista,
                  "causas": frases(corpo.get("causas", []), 8, 300, "causas"),
                  "diario": frases(corpo.get("diario", [])[-40:] if isinstance(corpo.get("diario"), list) else [], 40, 200, "diario")},
    }


class Sandbox:
    def __init__(self, bd):
        self.bd = bd

    def guardar(self, conta, corpo):
        r = validar(corpo)
        with ligacao(self.bd) as conn:
            nova = conn.execute(
                "INSERT INTO sandbox_resultados(conta_id, chave, destino, resultado, estrelas, hora, base_nivel, amostras, comida_produzida, dados) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (conta_id, chave) DO NOTHING RETURNING id",
                (conta["id"], r["chave"], r["destino"], r["resultado"], r["estrelas"], r["hora"], r["base_nivel"],
                 r["amostras"], r["comida"], Jsonb(r["dados"])),
            ).fetchone()
        return {"guardado": nova is not None, "repetido": nova is None}

    def listar(self, conta):
        with ligacao(self.bd) as conn:
            linhas = conn.execute(
                "SELECT id, destino, resultado, estrelas, hora, base_nivel, amostras, criada_em FROM sandbox_resultados "
                "WHERE conta_id = %s ORDER BY criada_em DESC, id DESC LIMIT 20", (conta["id"],)).fetchall()
            tot = conn.execute(
                "SELECT count(*) AS missoes, count(*) FILTER (WHERE resultado='ok') AS cumpridas, "
                "coalesce(max(estrelas),0) AS melhor, coalesce(sum(amostras),0) AS amostras "
                "FROM sandbox_resultados WHERE conta_id = %s", (conta["id"],)).fetchone()
        return {"resumo": {k: int(v) for k, v in tot.items()},
                "missoes": [{**l, "hora": float(l["hora"]), "criada_em": l["criada_em"].isoformat()} for l in linhas]}

    def ranking(self):
        """Só contas com nickname escolhido aparecem, e só pelo nickname."""
        with ligacao(self.bd) as conn:
            linhas = conn.execute(
                "SELECT c.nickname, max(r.estrelas) AS estrelas, max(r.base_nivel) AS base_nivel, "
                "sum(r.amostras)::int AS amostras, count(*)::int AS missoes "
                "FROM sandbox_resultados r JOIN contas c ON c.id = r.conta_id "
                "WHERE r.resultado = 'ok' AND c.nickname IS NOT NULL "
                "GROUP BY c.id ORDER BY estrelas DESC, base_nivel DESC, amostras DESC, c.nickname LIMIT 10").fetchall()
        return {"ranking": linhas}
