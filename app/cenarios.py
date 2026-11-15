"""Pacote de cenários para o cliente 2D: incidentes do catálogo da campanha + uma EVA real da NASA.
Reutiliza catalogo.LINHAS, missao.PERDAS/USOS/plano_da_rota e eva.* (nada é inventado no cliente)."""
from statistics import median

from . import eva
from .catalogo import LINHAS
from .catalogo_en import CONCEITOS as CONCEITOS_EN, DESTINOS_EN, FALAS as FALAS_EN, INCIDENTES as INCIDENTES_EN, PAISES_EN, ROTULOS_EVA
from .cerebro.reaccoes import FALAS as FALAS_PT
from .erros import Erro
from .missao import CONCEITOS as CONCEITOS_PT, PERDAS, USOS, plano_da_rota

DESTINOS = ("lua", "marte")
IDIOMAS = ("en", "pt")


def incidente(id_, linha, lang):
    if lang == "en":
        titulo, sinal, segura, arriscada, consequencia, recuperacao = INCIDENTES_EN[id_]
        conceito = CONCEITOS_EN[id_]
    else:
        _, titulo, sinal, segura, arriscada, consequencia, recuperacao = linha
        conceito = CONCEITOS_PT[id_]
    recurso, valor = PERDAS[id_]
    return {"id": id_, "title": titulo, "signal": sinal, "safe": segura, "risky": arriscada,
            "consequence": consequencia, "recovery": recuperacao, "concept": conceito,
            "loss": {"resource": recurso, "amount": valor}, "uses": USOS.get(id_)}


def eva_real(semente, destino, lang):
    ref = eva.escolher(semente)
    if not ref:
        return None
    en = lang == "en"
    return {"number": ref["eva"], "country": PAISES_EN.get(ref["pais"], ref["pais"]) if en else ref["pais"],
            "crew": ref["tripulacao"], "vehicle": ref["veiculo"], "date": ref["data"], "duration_min": ref["duracao_min"],
            "purpose": ref["proposito"], "theme": ref["tema"], "theme_label": ROTULOS_EVA[ref["tema"]] if en else ref["tema_pt"],
            "source": ref["fonte"]}


def estatisticas():
    duracoes = [r["duracao_min"] for r in eva.carregar() if type(r.get("duracao_min")) is int]
    if not duracoes:
        return None
    return {"records": len(eva.carregar()), "with_duration": len(duracoes), "median_min": int(median(duracoes)), "longest_min": max(duracoes)}


def pacote(destino, semente, lang):
    if destino not in DESTINOS:
        raise Erro(400, "Invalid destination.")
    if lang not in IDIOMAS:
        raise Erro(400, "Invalid language.")
    semente = str(semente or "")[:64] or "demo"
    real = eva_real(semente, destino, lang)
    plano = plano_da_rota(destino, semente, real["theme"] if real else None)
    viagem = [incidente(l[0], l, lang) for l in LINHAS["viagem"]]
    superficie = [incidente(LINHAS[destino][i][0], LINHAS[destino][i], lang) for i in plano[destino][1:]]
    if real and superficie:
        real["inspired_incident"] = superficie[0]["id"]
    return {"destination": DESTINOS_EN[destino] if lang == "en" else destino.capitalize(), "destination_id": destino, "lang": lang,
            "travel_plan": [LINHAS["viagem"][i][0] for i in plano["viagem"]], "real_eva": real, "eva_stats": estatisticas(), "travel": viagem, "surface": superficie,
            "crew_lines": FALAS_EN if lang == "en" else FALAS_PT}
