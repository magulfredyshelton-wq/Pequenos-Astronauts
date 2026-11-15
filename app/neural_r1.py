import logging
import math
from types import SimpleNamespace

from .cerebro.cerebro import CerebroLIF, Codificador
from .cerebro.reaccoes import para_estado
from .cerebro.tripulacao import PERFIS
from .catalogo import LINHAS
from .config import CEREBRO

log = logging.getLogger(__name__)
PAPEIS_R1 = {"comando": "COMANDO", "engenharia": "ENGENHARIA", "cadete": "OPERACOES"}
VERSAO = 1


def disponivel():
    if CEREBRO == "leve":
        return False
    try:
        from .cerebro.rede import LIFBrain
    except ImportError:
        if CEREBRO == "r1":
            raise RuntimeError("Instala requirements-neural.txt ou usa ASTRO_CEREBRO=leve.") from None
        return False
    return True


R1_ACTIVO = disponivel()


def canais(estado):
    recursos = estado["recursos"]
    valores = {"energia": SimpleNamespace(valor=recursos.get("energia", 100) / 100)}
    # As reservas mínimas referem-se ao momento da chegada, após o consumo previsto.
    for nome, referencia in (("oxigenio", 7), ("agua", 14)):
        if nome in recursos:
            valores[nome] = SimpleNamespace(valor=recursos[nome] / referencia)
    activo = estado.get("desafio")
    id_ = LINHAS[activo["grupo"]][activo["indice"]][0] if activo else None
    evento = id_ in {"tempestade", "sombra", "impacto", "refrigeracao", "painel_marte"}
    sucesso = estado["sinal"] == "sucesso"
    risco = estado["recuperacao"]
    accoes = [SimpleNamespace(boa=sucesso)] if sucesso or risco else []
    historico = estado["historico"][-3:]
    sucessos = sum(item.get("sinal") == "sucesso" for item in historico)
    return Codificador().codificar(
        SimpleNamespace(recursos=valores, evento=evento),
        accoes,
        sucesso_recente=sucesso and sucessos >= 2,
    )


def _guardar(cerebro):
    rede, decoder = cerebro._rede, cerebro._decoder
    return {
        "tempo_ms": rede.tempo_ms,
        "tempo_decoder": cerebro._tempo,
        "rng": rede.rng.bit_generator.state,
        "arrays": {nome: getattr(rede, nome).tolist() for nome in CAMPOS},
        "decoder": {"actual": decoder.actual, "candidato": decoder._candidato, "desde": decoder._desde},
    }


CAMPOS = ("_v", "_ath", "_ref", "_spikes", "_valor_canal", "_efic", "_taxas")


def _restaurar(cerebro, dados):
    import numpy as np

    rede, decoder = cerebro._rede, cerebro._decoder
    tempo = dados["tempo_ms"]
    if type(tempo) is not int or tempo < 0:
        raise ValueError("Tempo da rede inválido.")
    for nome in CAMPOS:
        actual = getattr(rede, nome)
        valores = np.asarray(dados["arrays"][nome], dtype=actual.dtype)
        if valores.shape != actual.shape or not np.isfinite(valores).all():
            raise ValueError(f"Dimensão ou valores inválidos em {nome}.")
        actual[:] = valores

    tempo_decoder = dados["tempo_decoder"]
    if not math.isfinite(tempo_decoder) or abs(tempo_decoder - tempo / 1000) > 1e-6:
        raise ValueError("Relógio do descodificador inválido.")
    dec = dados["decoder"]
    if (dec["actual"] not in (None, *rede.motores) or dec["candidato"] not in (None, *rede.motores)
            or not math.isfinite(dec["desde"]) or dec["desde"] < 0 or dec["desde"] > tempo / 1000 + 1e-6):
        raise ValueError("Descodificador inválido.")
    rede.tempo_ms = tempo
    rede.rng.bit_generator.state = dados["rng"]
    cerebro._tempo = tempo_decoder
    decoder.actual, decoder._candidato, decoder._desde = dec["actual"], dec["candidato"], dec["desde"]


def reagir(estado):
    anterior = estado.get("neural_r1", {})
    tick = estado["neural"]["comando"]["tick"]
    guardados = anterior.get("redes", {}) if (anterior.get("versao"), anterior.get("tick")) == (VERSAO, tick - 1) else {}
    estimulos = canais(estado)
    novos = {}
    for id_, papel in PAPEIS_R1.items():
        temperamento, semente = PERFIS[papel]
        cerebro = CerebroLIF(temperamento, semente)
        if id_ in guardados:
            try:
                _restaurar(cerebro, guardados[id_]["estado"])
            except (ValueError, KeyError, TypeError, OverflowError):
                log.warning("Estado R1 inválido para %s; a rede foi reiniciada.", id_)
                cerebro = CerebroLIF(temperamento, semente)

        try:
            reaccao = cerebro.pensar(estimulos)
            novos[id_] = {"estado": _guardar(cerebro), "reaccao": para_estado({papel: reaccao})[0]}
        except (ArithmeticError, ValueError):
            log.exception("Falha da rede R1 para %s; usada a rede leve.", id_)
    estado["neural_r1"] = {"versao": VERSAO, "tick": tick, "redes": novos}


def reaccao(estado, id_):
    dados = estado.get("neural_r1", {})
    if (dados.get("versao"), dados.get("tick")) != (VERSAO, estado["neural"][id_]["tick"]):
        return None
    return dados.get("redes", {}).get(id_, {}).get("reaccao")

