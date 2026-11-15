"""Saídas extraveiculares (EVA) reais da NASA, EUA e Rússia.

Fonte: NASA Open Data Portal, "Extra-vehicular Activity (EVA) - US and Russia"
(identificador 9kcy-zwvn). Colunas: EVA, Country, Crew, Vehicle, Date, Duration, Purpose.

Regras deste módulo:
- O jogo NUNCA faz pedidos de rede durante um comando de jogador: esse código corre dentro
  de uma transacção com a partida bloqueada. A rede só é usada em `sincronizar()`, chamada
  no arranque do servidor (em segundo plano) ou à mão com `python -m app.eva sync`.
- Os dados ficam numa cache em ficheiro (ASTRO_EVA_CACHE). Sem cache e sem rede, o jogo
  continua a funcionar, só que sem missão de referência real.
- Os textos vêm de uma fonte externa: são limpos e limitados antes de entrarem no estado.

Uso na linha de comandos (a partir de backend/):
    python -m app.eva sync      descarrega os dados da NASA e grava a cache
    python -m app.eva estado    mostra quantos registos há e de quando são
    python -m app.eva amostra   mostra 3 EVA ao acaso, já classificadas
"""
import csv
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from random import Random
from urllib.request import Request, urlopen

from .config import EVA_ACTIVO, EVA_CACHE, EVA_TTL_DIAS, EVA_URLS

log = logging.getLogger(__name__)

FONTE = "NASA Open Data · EVA US and Russia (9kcy-zwvn)"
MAX_BYTES = 4_000_000
TIMEOUT = 10
MIN_REGISTOS = 20  # a tabela real tem centenas de linhas; menos que isto é uma resposta errada


class ErroEva(RuntimeError):
    pass


ROTULOS = {
    "reparo": "reparação",
    "montagem": "montagem de estruturas",
    "instalacao": "instalação de equipamento",
    "teste": "teste de equipamento",
    "ciencia": "ciência e experiências",
    "inspecao": "inspecção",
    "geral": "trabalho geral no exterior",
}

# Tema da EVA -> destino -> ids de desafios de LINHAS (catalogo.py), por ordem de preferência.
# O primeiro que existir no destino passa a ser o primeiro incidente da superfície.
TEMAS = {
    "reparo": {"lua": ("junta", "rover_lua"), "marte": ("roda_marte", "painel_marte")},
    "montagem": {"lua": ("sombra", "poeira_antecamara"), "marte": ("painel_marte", "tempestade")},
    "instalacao": {"lua": ("poeira_antecamara", "sombra"), "marte": ("painel_marte", "frio")},
    "teste": {"lua": ("junta", "retransmissor"), "marte": ("frio", "conjuncao")},
    "ciencia": {"lua": ("gelo_lua", "oscilacao_termica"), "marte": ("amostra_marte", "gelo_marte")},
    "inspecao": {"lua": ("rover_lua", "relevo"), "marte": ("roda_marte", "painel_marte")},
    "geral": {"lua": ("poeira_antecamara",), "marte": ("abrigo_marte",)},
}

# O campo Purpose da NASA está em inglês; ordem = prioridade.
PALAVRAS = (
    ("reparo", ("repair", "replac", "fix", "maintenance", "swap", "mend")),
    ("montagem", ("assembl", "construct", "truss", "build")),
    ("instalacao", ("install", "deploy", "attach", "mount", "connect", "cable", "relocat", "outfit")),
    ("teste", ("test", "evaluat", "checkout", "check out", "demonstrat")),
    ("ciencia", ("experiment", "sample", "science", "scientific", "photograph", "observ", "exposure")),
    ("inspecao", ("inspect", "survey", "examin")),
)
PAISES = {"usa": "EUA", "us": "EUA", "u.s.": "EUA", "united states": "EUA",
          "russia": "Rússia", "ussr": "URSS"}

_CONTROLO = re.compile(r"[\x00-\x1f\x7f<>]")
_DURACAO = re.compile(r"^\s*(\d{1,3}):(\d{1,2})(?::(\d{1,2}))?\s*$")


def limpar(valor, limite=200):
    """Texto externo -> texto simples, sem controlos nem sinais < >, com tamanho limitado."""
    if valor is None:
        return ""
    return " ".join(_CONTROLO.sub(" ", str(valor)).split())[:limite]


def minutos(valor):
    """'7:00' ou '0:12:30' -> minutos inteiros; None se o formato não for reconhecido."""
    achado = _DURACAO.match(str(valor or ""))
    if not achado:
        return None
    horas, mins, segs = int(achado[1]), int(achado[2]), int(achado[3] or 0)
    if mins > 59 or segs > 59:
        return None
    total = round(horas * 60 + mins + segs / 60)
    return total if 0 < total <= 24 * 60 else None


def data_iso(valor):
    texto = str(valor or "").strip()
    achado = re.match(r"^(\d{4})-(\d{2})-(\d{2})", texto)
    if achado:
        ano, mes, dia = (int(x) for x in achado.groups())
    else:
        achado = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", texto)
        if not achado:
            return ""
        mes, dia, ano = (int(x) for x in achado.groups())
    try:
        return datetime(ano, mes, dia).date().isoformat()
    except ValueError:
        return ""


def classificar(proposito):
    texto = str(proposito or "").lower()
    for tema, palavras in PALAVRAS:
        if any(p in texto for p in palavras):
            return tema
    return "geral"


def _normalizar(linha):
    chaves = {re.sub(r"[^a-z]", "", str(k).lower()): v for k, v in linha.items()}
    proposito = limpar(chaves.get("purpose"), 220)
    if not proposito:
        return None
    pais = limpar(chaves.get("country"), 40)
    return {
        "eva": limpar(chaves.get("eva"), 12),
        "pais": PAISES.get(pais.lower(), pais),
        "tripulacao": limpar(chaves.get("crew"), 120),
        "veiculo": limpar(chaves.get("vehicle"), 60),
        "data": data_iso(chaves.get("date")),
        "duracao_min": minutos(chaves.get("duration")),
        "proposito": proposito,
        "tema": classificar(proposito),
    }


def _linhas_json(dados):
    if isinstance(dados, list):
        return [x for x in dados if isinstance(x, dict)]
    if isinstance(dados, dict):
        colunas = (dados.get("meta") or {}).get("view", {}).get("columns")
        linhas = dados.get("data")
        if isinstance(colunas, list) and isinstance(linhas, list):  # exportação Socrata clássica
            nomes = [c.get("fieldName") or c.get("name") or "" for c in colunas]
            return [dict(zip(nomes, l)) for l in linhas if isinstance(l, list)]
        for chave in ("rows", "records", "data", "results"):
            if isinstance(dados.get(chave), list):
                return [x for x in dados[chave] if isinstance(x, dict)]
    raise ValueError("Formato JSON desconhecido.")


def interpretar(corpo):
    """Bytes de CSV ou JSON (lista de objectos, ou exportação Socrata) -> registos normalizados."""
    texto = corpo.decode("utf-8-sig", errors="replace")
    if texto.lstrip()[:1] in ("[", "{"):
        linhas = _linhas_json(json.loads(texto))
    else:
        linhas = list(csv.DictReader(io.StringIO(texto)))
    return [registo for registo in map(_normalizar, linhas) if registo]


_LOCK = threading.Lock()
_MEM = {"registos": None, "marca": None, "obtido_em": 0.0, "origem": ""}


def _abrir(url):
    pedido = Request(url, headers={"User-Agent": "PequenosAstronautas/1.0 (NASA Space Apps)",
                                   "Accept": "text/csv, application/json"})
    with urlopen(pedido, timeout=TIMEOUT) as resposta:
        corpo = resposta.read(MAX_BYTES + 1)
    if len(corpo) > MAX_BYTES:
        raise ValueError("Resposta demasiado grande.")
    return corpo


def _gravar(registos, origem):
    agora = time.time()
    with _LOCK:
        _MEM.update(registos=registos, obtido_em=agora, origem=origem)
    try:
        EVA_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=EVA_CACHE.parent,
                                         delete=False, suffix=".tmp") as tmp:
            json.dump({"versao": 1, "obtido_em": agora, "origem": origem, "registos": registos},
                      tmp, ensure_ascii=False)
        os.replace(tmp.name, EVA_CACHE)
        with _LOCK:
            _MEM["marca"] = EVA_CACHE.stat().st_mtime_ns
    except OSError as erro:  # a memória já tem os dados; só se perde a persistência
        log.warning("Não foi possível gravar a cache EVA: %s", erro)


def sincronizar(urls=None):
    """Descarrega os dados da NASA (rede!). Experimenta cada URL até uma devolver dados válidos."""
    falhas = []
    for url in (urls or EVA_URLS):
        if not url.startswith("https://"):
            falhas.append(f"{url}: só são aceites URLs https")
            continue
        try:
            registos = interpretar(_abrir(url))
        except (OSError, ValueError, csv.Error) as erro:
            falhas.append(f"{url}: {erro}")
            continue
        if len(registos) < MIN_REGISTOS:
            falhas.append(f"{url}: só {len(registos)} registos válidos")
            continue
        _gravar(registos, url)
        return estado_fonte()
    raise ErroEva("Não foi possível obter os dados EVA da NASA. " + "; ".join(falhas))


def carregar():
    """Registos em memória, relidos do ficheiro se ele mudou. Nunca usa a rede."""
    with _LOCK:
        try:
            marca = EVA_CACHE.stat().st_mtime_ns
        except OSError:
            return list(_MEM["registos"] or [])
        if marca != _MEM["marca"]:
            try:
                dados = json.loads(EVA_CACHE.read_text(encoding="utf-8"))
                registos = [r for r in dados["registos"] if isinstance(r, dict) and r.get("proposito")]
                _MEM.update(registos=registos, marca=marca, obtido_em=float(dados.get("obtido_em", 0)),
                            origem=str(dados.get("origem", "")))
            except (OSError, ValueError, KeyError, TypeError) as erro:
                log.warning("Cache EVA ilegível: %s", erro)
                _MEM["marca"] = marca
        return list(_MEM["registos"] or [])


def estado_fonte():
    registos = carregar()
    with _LOCK:
        obtido = _MEM["obtido_em"]
        origem = _MEM["origem"]
    return {"activo": EVA_ACTIVO and bool(registos), "total": len(registos),
            "obtido_em": datetime.fromtimestamp(obtido, timezone.utc).isoformat() if registos and obtido else None,
            "origem": origem or None, "fonte": FONTE}


def sincronizar_se_preciso():
    """Para o arranque do servidor: só vai à rede se não houver cache ou se ela for velha."""
    registos = carregar()
    with _LOCK:
        idade = time.time() - _MEM["obtido_em"]
    if registos and idade < EVA_TTL_DIAS * 86400:
        return False
    try:
        sincronizar()
        return True
    except ErroEva as erro:
        log.warning("%s", erro)
        return False


def referencia(registo):
    """Registo -> dicionário pequeno e seguro, guardado no estado da partida."""
    tema = registo.get("tema") if registo.get("tema") in TEMAS else "geral"
    duracao = registo.get("duracao_min")
    return {"eva": limpar(registo.get("eva"), 12), "pais": limpar(registo.get("pais"), 40),
            "tripulacao": limpar(registo.get("tripulacao"), 120), "veiculo": limpar(registo.get("veiculo"), 60),
            "data": limpar(registo.get("data"), 10),
            "duracao_min": duracao if type(duracao) is int and 0 < duracao <= 1440 else None,
            "proposito": limpar(registo.get("proposito"), 220), "tema": tema, "tema_pt": ROTULOS[tema],
            "fonte": FONTE}


def escolher(semente, registos=None):
    """Escolhe, de forma determinística para a mesma semente, uma EVA real. None se não houver dados."""
    if not EVA_ACTIVO:
        return None
    registos = carregar() if registos is None else registos
    lote = ([r for r in registos if r.get("proposito") and r.get("duracao_min")]
            or [r for r in registos if r.get("proposito")])
    if not lote:
        return None
    return referencia(Random(f"eva:{semente}").choice(lote))


def _cli(argv):
    comando = argv[0] if argv else "estado"
    if comando == "sync":
        try:
            print(json.dumps(sincronizar(), ensure_ascii=False, indent=2))
        except ErroEva as erro:
            print(erro, file=sys.stderr)
            return 1
    elif comando == "estado":
        print(json.dumps(estado_fonte(), ensure_ascii=False, indent=2))
    elif comando == "amostra":
        registos = carregar()
        if not registos:
            print("Sem dados. Corre primeiro: python -m app.eva sync", file=sys.stderr)
            return 1
        for registo in Random().sample(registos, min(3, len(registos))):
            print(json.dumps(referencia(registo), ensure_ascii=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
