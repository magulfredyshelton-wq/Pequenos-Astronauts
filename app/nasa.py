"""Dados reais da NASA para a ciência da missão: APOD, DONKI, RadLab e OSDR.

Fontes:
- APOD .... fotografia astronómica do dia      https://api.nasa.gov/planetary/apod
- DONKI ... meteorologia espacial (CME, FLR)   https://api.nasa.gov/DONKI/notifications
- RadLab .. dose absorvida real na ISS         https://visualization.osdr.nasa.gov/radlab/api/
- OSDR .... estudos de biologia espacial       https://osdr.nasa.gov/osdr/data/search

Regras (as mesmas de app/eva.py):
- O jogo NUNCA faz pedidos de rede durante um comando de jogador: esse código corre dentro
  de uma transacção com a partida bloqueada. A rede só é usada em `sincronizar()`, chamada
  no arranque do servidor (em segundo plano) ou à mão com `python -m app.nasa sync`.
- Cada fonte falha de forma independente e mantém o último valor bom da cache. Sem cache e
  sem rede o jogo arranca e joga exactamente como antes.
- Os textos vêm de fontes externas: são limpos e limitados antes de entrarem no estado.
- O modificador de exposição só entra em jogo com ASTRO_NASA_JOGO=1, para manter as partidas
  determinísticas e os testes independentes da rede.

Uso na linha de comandos (a partir de backend/):
    python -m app.nasa sync      descarrega as quatro fontes e grava a cache
    python -m app.nasa estado    mostra o que está em cache e de quando é
    python -m app.nasa amostra   mostra o briefing de uma missão de exemplo
"""
import json
import logging
import math
import os
import re
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone
from random import Random
from statistics import median
from urllib.parse import quote, quote_plus
from urllib.request import Request, urlopen

from .config import NASA_ACTIVO, NASA_CACHE, NASA_CHAVE, NASA_JOGO, NASA_TTL_HORAS
from .eva import limpar

log = logging.getLogger(__name__)

FONTE_APOD = "NASA APOD"
FONTE_DONKI = "NASA DONKI (CCMC)"
FONTE_RADLAB = "NASA OSDR RadLab · DosTel/ISS"
FONTE_OSDR = "NASA OSDR (ALSDA/GeneLab)"
MAX_BYTES = 2_000_000
TIMEOUT = 10
DIAS_DONKI = 7

APOD = "https://api.nasa.gov/planetary/apod"
DONKI = "https://api.nasa.gov/DONKI/notifications"
RADLAB = "https://visualization.osdr.nasa.gov/radlab/api/"
OSDR = "https://osdr.nasa.gov/osdr/data/search"

# Dias com leituras públicas do DosTel na ISS. O RadLab não tem telemetria de hoje em dia;
# a cache guarda a data real das leituras para a interface poder dizê-lo.
DIAS_RADLAB = ("2022-04-01", "2022-04-02", "2022-03-01")
TERMOS_OSDR = ("spaceflight bone loss", "space radiation immune response", "lunar dust astronaut")

ROTULOS = {0: "calmo", 1: "baixo", 2: "elevado", 3: "severo"}
FATORES = (1.0, 1.25, 1.5, 2.0)  # nível de meteorologia espacial -> custo em exposição

_SECAO = re.compile(r"##\s*Summary:\s*(.*?)(?:\n\s*##|\Z)", re.S)
_ATIVIDADE = re.compile(r"Activity ID:.*", re.S)


class ErroNasa(RuntimeError):
    pass


def _iso(marca):
    if not marca:
        return None
    try:
        return datetime.fromtimestamp(float(marca), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _url_https(valor, limite=500):
    """Só aceita ligações https: um URL externo nunca pode trazer javascript: ou data:."""
    texto = str(valor or "").strip()
    return texto[:limite] if texto.startswith("https://") else ""


def _percentil(ordenados, fracao):
    if not ordenados:
        return None
    posicao = max(0, min(len(ordenados) - 1, round((len(ordenados) - 1) * fracao)))
    return ordenados[posicao]


def _resumo(corpo):
    achado = _SECAO.search(str(corpo or ""))
    texto = _ATIVIDADE.sub("", achado.group(1) if achado else str(corpo or ""))
    return limpar(texto, 280)


def _nivel_evento(corpo, tipo):
    """Gravidade para o jogo: 0 nada, 1 baixo, 2 elevado, 3 severo (tempestade de partículas)."""
    texto = str(corpo or "").lower()
    if tipo == "SEP":
        return 3
    if tipo == "FLR":
        if re.search(r"\bx\d", texto):
            return 3
        if re.search(r"\bm\d", texto):
            return 2
        return 1
    if tipo == "CME":
        achado = re.search(r"estimated speed:\s*~?\s*(\d+)", texto)
        velocidade = int(achado.group(1)) if achado else 0
        if velocidade >= 1000:
            return 3
        if velocidade >= 500:
            return 2
        return 1
    if tipo == "GST":
        return 2
    if tipo in ("RBE", "IPS"):
        return 1
    return 0


def _destinos(corpo):
    """Destinos do jogo mencionados numa notificação de CME (impacto previsto)."""
    texto = re.sub(r"moon to mars[^.\n]*", " ", str(corpo or ""), flags=re.I)
    alvos = set()
    for frase in re.split(r"(?<=[.!?])\s+|\n+", texto):
        if not re.search(r"impact|reach|affect|arrival|glancing blow|near earth", frase, re.I):
            continue
        if re.search(r"\bmars\b", frase, re.I):
            alvos.add("marte")
        if re.search(r"\bmoon\b|\blunar\b|near earth", frase, re.I):
            alvos.add("lua")
    return alvos


def interpretar_apod(dados):
    if not isinstance(dados, dict):
        return None
    titulo = limpar(dados.get("title"), 120)
    if not titulo:
        return None
    return {"data": limpar(dados.get("date"), 10), "titulo": titulo,
            "explicacao": limpar(dados.get("explanation"), 500),
            "url": _url_https(dados.get("url")), "hdurl": _url_https(dados.get("hdurl")),
            "tipo": limpar(dados.get("media_type"), 12), "credito": limpar(dados.get("copyright"), 80),
            "fonte": FONTE_APOD}


def interpretar_donki(lista, agora=None):
    """Lista de notificações do DONKI -> resumo pequeno, já classificado para o jogo."""
    if not isinstance(lista, list):
        return None
    eventos, afeta = [], set()
    for notificacao in lista:
        if not isinstance(notificacao, dict):
            continue
        tipo = limpar(notificacao.get("messageType"), 12).upper()
        if not tipo or tipo == "REPORT":  # o relatório semanal repete eventos já contados
            continue
        corpo = str(notificacao.get("messageBody") or "")
        nivel = _nivel_evento(corpo, tipo)
        if tipo == "SEP":              # partículas solares atravessam o espaço interplanetário
            afeta |= {"lua", "marte"}
        elif tipo == "FLR" and nivel >= 2:  # a Lua não tem magnetosfera que proteja a tripulação
            afeta.add("lua")
        elif tipo == "CME":
            afeta |= _destinos(corpo)
        eventos.append({"tipo": tipo, "id": limpar(notificacao.get("messageID"), 24),
                        "quando": limpar(notificacao.get("messageIssueTime"), 20),
                        "nivel": nivel, "resumo": _resumo(corpo)})
    eventos = [e for e in eventos if e["resumo"]]
    eventos.sort(key=lambda e: (e["nivel"], e["quando"]), reverse=True)
    nivel = max((e["nivel"] for e in eventos), default=0)
    fim = agora.date() if isinstance(agora, datetime) else (agora or date.today())
    return {"nivel": nivel, "rotulo": ROTULOS[nivel], "eventos": eventos[:6],
            "afeta": {destino: destino in afeta for destino in ("lua", "marte")},
            "janela": {"inicio": (fim - timedelta(days=DIAS_DONKI)).isoformat(), "fim": fim.isoformat()},
            "fonte": FONTE_DONKI}


def interpretar_radlab(dados, dia=""):
    """Resposta do RadLab (colunas/data ou lista de objectos) -> estatísticas da dose real."""
    if isinstance(dados, dict):
        colunas = dados.get("columns") or []
        linhas = dados.get("data") or []
        if not isinstance(colunas, list) or not isinstance(linhas, list):
            return None
        posicao = {limpar(nome, 40): i for i, nome in enumerate(colunas)}
        indice = posicao.get("absorbed_dose_rate")
        if indice is None:
            return None
        pares = [(linha, indice) for linha in linhas if isinstance(linha, list)]
    elif isinstance(dados, list):
        pares = [(linha, "absorbed_dose_rate") for linha in dados if isinstance(linha, dict)]
        indice = "absorbed_dose_rate"
    else:
        return None
    valores = []
    for linha, chave in pares:
        try:
            valor = float(linha[chave] if isinstance(chave, int) else linha.get(chave))
        except (IndexError, TypeError, ValueError):
            continue
        if math.isfinite(valor) and 0 <= valor < 1e6:
            valores.append(valor)
    if not valores:
        return None
    valores.sort()
    return {"taxa_mediana": round(median(valores), 3), "taxa_p95": round(_percentil(valores, 0.95), 3),
            "taxa_maxima": round(valores[-1], 3), "amostras": len(valores), "unidade": "µGy/h",
            "dia": limpar(dia, 10), "instrumento": "DosTel (ISS)", "fonte": FONTE_RADLAB}


def interpretar_osdr(dados):
    """Resposta do /osdr/data/search -> lista pequena de estudos citáveis no relatório."""
    hits = (((dados or {}).get("hits") or {}).get("hits")) if isinstance(dados, dict) else None
    if not isinstance(hits, list):
        return []
    estudos = []
    for hit in hits:
        fonte = hit.get("_source") if isinstance(hit, dict) else None
        if not isinstance(fonte, dict):
            continue
        acesso = limpar(fonte.get("Accession") or fonte.get("Study Identifier"), 24)
        titulo = limpar(fonte.get("Study Title"), 220)
        if not acesso or not titulo:
            continue
        estudos.append({"acesso": acesso, "titulo": titulo,
                        "organismo": limpar(fonte.get("organism"), 80),
                        "resumo": limpar(fonte.get("Study Description"), 320),
                        "url": "https://osdr.nasa.gov/bio/repo/data/studies/" + quote(acesso)})
    return estudos


def _url_donki(inicio, fim):
    return (DONKI + "?startDate=" + inicio + "&endDate=" + fim + "&type=all&api_key="
            + quote(NASA_CHAVE))


def _url_radlab(dia):
    seguinte = (date.fromisoformat(dia) + timedelta(days=1)).isoformat()
    return (RADLAB + "?spacecraft=ISS&instrument=DosTel&timestamp%3E=" + dia + "T00%3A00"
            + "&timestamp%3C" + seguinte + "T00%3A00&absorbed_dose_rate&format=json")


def _url_osdr(termo):
    return OSDR + "?term=" + quote_plus(termo) + "&size=2"


def _abrir_json(url):
    if not str(url).startswith("https://"):
        raise ValueError("só são aceites URLs https")
    pedido = Request(url, headers={"User-Agent": "PequenosAstronautas/1.0 (NASA Space Apps)",
                                   "Accept": "application/json"})
    with urlopen(pedido, timeout=TIMEOUT) as resposta:
        corpo = resposta.read(MAX_BYTES + 1)
    if len(corpo) > MAX_BYTES:
        raise ValueError("resposta demasiado grande")
    return json.loads(corpo.decode("utf-8-sig", errors="replace"))


def _obter_apod():
    """APOD de hoje; se o serviço falhar para a data de hoje, tenta os dois dias anteriores."""
    hoje = date.today()
    falhas = []
    for dias in (0, 1, 2):
        dia = (hoje - timedelta(days=dias)).isoformat()
        try:
            dados = interpretar_apod(
                _abrir_json(APOD + "?api_key=" + quote(NASA_CHAVE) + "&date=" + dia))
        except (OSError, ValueError) as erro:
            falhas.append(f"{dia}: {erro}")
            continue
        if dados:
            return dados
        falhas.append(f"{dia}: resposta vazia")
    raise ValueError("APOD indisponível (" + "; ".join(falhas) + ")")


def _obter_donki():
    fim = date.today()
    inicio = fim - timedelta(days=DIAS_DONKI)
    return interpretar_donki(_abrir_json(_url_donki(inicio.isoformat(), fim.isoformat())), agora=fim)


def _obter_radlab():
    falhas = []
    for dia in DIAS_RADLAB:
        try:
            resultado = interpretar_radlab(_abrir_json(_url_radlab(dia)), dia)
        except (OSError, ValueError) as erro:
            falhas.append(f"{dia}: {erro}")
            continue
        if resultado:
            return resultado
        falhas.append(f"{dia}: sem leituras")
    raise ValueError("RadLab indisponível (" + "; ".join(falhas) + ")")


def _obter_estudos():
    estudos, vistos, falhas = [], set(), []
    for termo in TERMOS_OSDR:
        try:
            novos = interpretar_osdr(_abrir_json(_url_osdr(termo)))
        except (OSError, ValueError) as erro:
            falhas.append(f"{termo}: {erro}")
            continue
        for estudo in novos:
            if estudo["acesso"] not in vistos:
                vistos.add(estudo["acesso"])
                estudos.append(estudo)
    if not estudos:
        raise ValueError("OSDR sem estudos (" + "; ".join(falhas) + ")")
    return estudos[:6]


_LOCK = threading.Lock()
_MEM = {"dados": None, "marca": None}


def _gravar(dados):
    agora = time.time()
    dados = {**dados, "versao": 1, "obtido_em": agora, "origem": "NASA Open APIs"}
    with _LOCK:
        _MEM["dados"] = dados
    try:
        NASA_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=NASA_CACHE.parent,
                                         delete=False, suffix=".tmp") as tmp:
            json.dump(dados, tmp, ensure_ascii=False)
        os.replace(tmp.name, NASA_CACHE)
        with _LOCK:
            _MEM["marca"] = NASA_CACHE.stat().st_mtime_ns
    except OSError as erro:  # a memória já tem os dados; só se perde a persistência
        log.warning("Não foi possível gravar a cache NASA: %s", erro)


def sincronizar():
    """Descarrega as quatro fontes (rede!). Uma fonte em baixo não apaga as outras."""
    anterior = carregar()
    novo, falhas = {}, []

    for chave, obter in (("apod", _obter_apod), ("tempo_espacial", _obter_donki),
                         ("radiacao", _obter_radlab), ("estudos", _obter_estudos)):
        try:
            valor = obter()
        except (OSError, ValueError, KeyError, TypeError) as erro:
            falhas.append(f"{chave}: {erro}")
            valor = anterior.get(chave)  # mantém o último valor bom
        if valor:
            novo[chave] = valor

    if not novo:
        raise ErroNasa("Não foi possível obter dados da NASA. " + "; ".join(falhas))
    _gravar(novo)
    if falhas:
        log.warning("Sincronização NASA parcial: %s", "; ".join(falhas))
    return estado_fonte()


def carregar():
    """Dados em memória, relidos do ficheiro se ele mudou. Nunca usa a rede."""
    with _LOCK:
        try:
            marca = NASA_CACHE.stat().st_mtime_ns
        except OSError:
            return dict(_MEM["dados"] or {})
        if marca != _MEM["marca"]:
            try:
                dados = json.loads(NASA_CACHE.read_text(encoding="utf-8"))
                if not isinstance(dados, dict):
                    raise ValueError("formato desconhecido")
                _MEM.update(dados=dados, marca=marca)
            except (OSError, ValueError, KeyError, TypeError) as erro:
                log.warning("Cache NASA ilegível: %s", erro)
                _MEM["marca"] = marca
        return dict(_MEM["dados"] or {})


def _tempo_publico(tempo, destino):
    if not isinstance(tempo, dict):
        return None
    eventos = [{"tipo": e.get("tipo"), "quando": e.get("quando"), "resumo": e.get("resumo")}
               for e in (tempo.get("eventos") or [])[:3] if isinstance(e, dict)]
    return {"nivel": tempo.get("nivel", 0), "rotulo": tempo.get("rotulo"),
            "afeta": bool((tempo.get("afeta") or {}).get(destino)), "eventos": eventos,
            "fonte": tempo.get("fonte")}


def fator_exposicao(tempo, destino):
    """Multiplicador do custo em exposição. 1.0 quando não há alerta que atinja o destino."""
    if not isinstance(tempo, dict) or not (tempo.get("afeta") or {}).get(destino):
        return 1.0
    nivel = tempo.get("nivel")
    return FATORES[nivel] if type(nivel) is int and 0 <= nivel < len(FATORES) else 1.0


def referencia(destino, semente):
    """Briefing pequeno e determinístico para uma missão. None se não houver cache."""
    if not NASA_ACTIVO:
        return None
    dados = carregar()
    if not dados:
        return None
    ciencia = {}
    if dados.get("apod"):
        ciencia["apod"] = dados["apod"]
    tempo = _tempo_publico(dados.get("tempo_espacial"), destino)
    if tempo:
        ciencia["tempo_espacial"] = tempo
    if dados.get("radiacao"):
        ciencia["radiacao"] = dados["radiacao"]
    estudos = [e for e in dados.get("estudos") or [] if isinstance(e, dict)]
    if estudos:
        ciencia["estudo"] = Random(f"nasa:{destino}:{semente}").choice(estudos)
    if NASA_JOGO:
        ciencia["fator_exposicao"] = fator_exposicao(dados.get("tempo_espacial"), destino)
    if not ciencia:
        return None
    ciencia["obtido_em"] = _iso(dados.get("obtido_em"))
    return ciencia


def estado_fonte():
    dados = carregar()
    tempo = dados.get("tempo_espacial") if isinstance(dados.get("tempo_espacial"), dict) else {}
    return {"activo": NASA_ACTIVO and bool(dados), "obtido_em": _iso(dados.get("obtido_em")),
            "origem": dados.get("origem"), "fonte": "NASA Open APIs",
            "fontes": {"apod": bool(dados.get("apod")), "donki": bool(tempo),
                       "radlab": bool(dados.get("radiacao")), "osdr": bool(dados.get("estudos"))},
            "tempo_espacial": {"nivel": tempo.get("nivel", 0), "rotulo": tempo.get("rotulo"),
                               "eventos": tempo.get("eventos", [])[:3], "afeta": tempo.get("afeta", {})},
            "radiacao": dados.get("radiacao"), "estudos": len(dados.get("estudos") or []),
            "amostra_estudos": [e for e in (dados.get("estudos") or [])[:3] if isinstance(e, dict)],
            "apod": dados.get("apod"), "jogo_activo": NASA_JOGO}


def sincronizar_se_preciso():
    """Para o arranque do servidor: só vai à rede se não houver cache ou se ela for velha."""
    dados = carregar()
    if dados and time.time() - float(dados.get("obtido_em") or 0) < NASA_TTL_HORAS * 3600:
        return False
    try:
        sincronizar()
        return True
    except ErroNasa as erro:
        log.warning("%s", erro)
        return False


def _cli(argv):
    comando = argv[0] if argv else "estado"
    if comando == "sync":
        try:
            print(json.dumps(sincronizar(), ensure_ascii=False, indent=2))
        except ErroNasa as erro:
            print(erro, file=sys.stderr)
            return 1
    elif comando == "estado":
        print(json.dumps(estado_fonte(), ensure_ascii=False, indent=2))
    elif comando == "amostra":
        ciencia = referencia("marte", "demo")
        if not ciencia:
            print("Sem dados. Corre primeiro: python -m app.nasa sync", file=sys.stderr)
            return 1
        print(json.dumps(ciencia, ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
