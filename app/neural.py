import math
import random

from . import neural_r1

PAPEIS = {
    "comando": ("Comandante", 0.85, 11),
    "engenharia": ("Engenheira", 1.00, 23),
    "cadete": ("Cadete", 1.22, 37),
}
SENSORES = ("energia_baixa", "o2_baixo", "incidente", "risco", "sucesso", "estavel")
INTER = ("alerta", "stress", "calma", "confianca", "desanimo")
MOTORES = ("SERENO", "PANICO", "PROTESTO", "ALIVIO", "TRISTEZA")
NEURONIOS_GRUPO = 5
TOTAL = (len(INTER) + len(MOTORES)) * NEURONIOS_GRUPO
DECAY = math.exp(-0.18)

# As linhas são os grupos de origem; as colunas são os grupos de destino.
SENSOR_INTER = (
    (.28, .45, -.21, 0, .16),
    (.55, .21, -.30, 0, .16),
    (.31, .52, -.43, -.12, .11),
    (.51, .45, -.50, -.25, .53),
    (-.10, -.28, .28, .82, -.29),
    (0, -.19, .72, 0, -.15),
)
INTER_MOTOR = (
    (-.14, .39, .11, -.14, 0),
    (-.19, .11, .57, -.21, .07),
    (.56, -.28, -.27, .04, -.20),
    (.10, -.19, -.25, .68, -.28),
    (-.15, .06, .04, -.18, .48),
)
INTER_REDE = (
    (0, .12, -.10, 0, 0),
    (0, 0, -.18, -.12, .10),
    (-.10, -.16, 0, .07, -.08),
    (0, -.08, .13, 0, -.19),
    (0, 0, -.06, -.12, 0),
)


def limitar(valor):
    return max(0.0, min(1.0, valor))


def codificar(estado):
    recursos = estado["recursos"]
    energia = recursos.get("energia", 100)
    oxigenio = recursos.get("oxigenio", 0)
    retorno = {
        "energia_baixa": limitar((60 - energia) / 60),
        "o2_baixo": limitar((7 - oxigenio) / 7) if "oxigenio" in recursos else 0,
        "incidente": float(bool(estado["desafio"])),
        "risco": float(bool(estado["recuperacao"])),
        "sucesso": float(estado["sinal"] == "sucesso"),
    }
    retorno["estavel"] = limitar(1 - max(retorno.values()))
    return retorno


def estado_inicial():
    return {id_: {"tick": 0, "v": [0.0] * TOTAL, "refractario": [0] * TOTAL,
                  "ultimos": [0.0] * (len(INTER) + len(MOTORES)), "taxas": [0.0] * len(MOTORES),
                  "emocao": "SERENO", "intensidade": 0.0, "permanencia": 0} for id_ in PAPEIS}


def somar(pulsos, pesos, destino):
    return sum(taxa * linha[destino] for taxa, linha in zip(pulsos, pesos))


def simular(rede, entradas, temperamento, semente):
    rng = random.Random(semente + rede["tick"] * 104729)
    contagem = [0] * len(MOTORES)
    for _ in range(60):
        pulsos = [float(rng.random() < limitar(entradas[k] * 0.85)) for k in SENSORES]
        antes = rede["ultimos"]
        inter = antes[:len(INTER)]
        motores = antes[len(INTER):]
        novos = []
        for grupo in range(len(INTER) + len(MOTORES)):
            if grupo < len(INTER):
                ganho = temperamento if grupo in (0, 1, 4) else 1
                corrente = somar(pulsos, SENSOR_INTER, grupo) * ganho + somar(inter, INTER_REDE, grupo)
            else:
                indice = grupo - len(INTER)
                corrente = somar(inter, INTER_MOTOR, indice) - .13 * (sum(motores) - motores[indice])

            disparos = 0
            for i in range(grupo * NEURONIOS_GRUPO, (grupo + 1) * NEURONIOS_GRUPO):
                if rede["refractario"][i]:
                    rede["refractario"][i] -= 1
                    continue
                v = max(-.22, rede["v"][i] * DECAY + corrente + rng.uniform(-.055, .065))
                if v >= .86:
                    disparos += 1
                    v = .09
                    rede["refractario"][i] = 2
                rede["v"][i] = v
            novos.append(disparos / NEURONIOS_GRUPO)
            if grupo >= len(INTER):
                contagem[grupo - len(INTER)] += disparos
        rede["ultimos"] = novos

    rede["taxas"] = [round(.32 * anterior + .68 * n / 3, 4)
                     for anterior, n in zip(rede["taxas"], contagem)]
    actual = MOTORES.index(rede["emocao"])
    candidato = max(range(len(MOTORES)), key=rede["taxas"].__getitem__)
    if (rede["taxas"][candidato] - rede["taxas"][actual] >= 1.4
            and (rede["permanencia"] >= 1 or rede["taxas"][candidato] >= 8)):
        rede["emocao"] = MOTORES[candidato]
        rede["permanencia"] = 0
        actual = candidato
    else:
        rede["permanencia"] += 1
    rede["intensidade"] = round(limitar(rede["taxas"][actual] / 16), 2)
    rede["tick"] += 1


def reagir(estado):
    entradas = codificar(estado)
    for id_, (_, temperamento, semente) in PAPEIS.items():
        simular(estado["neural"][id_], entradas, temperamento, semente)
    if neural_r1.R1_ACTIVO:
        neural_r1.reagir(estado)


TAREFAS = {
    "comando": "Eu acompanho a decisão da equipa.",
    "engenharia": "Eu verifico os sistemas e as reservas.",
    "cadete": "Eu acompanho a tarefa no terminal.",
}
FALAS = {
    "SERENO": "Vamos confirmar as leituras.",
    "PANICO": "Os recursos críticos estão a cair. Vamos proteger a tripulação.",
    "PROTESTO": "Temos um alerta. Verifica o terminal.",
    "ALIVIO": "A situação estabilizou. Podemos continuar.",
    "TRISTEZA": "Perdemos margem. Ainda podemos recuperar.",
}


def apresentar(estado):
    resultado = []
    for id_, (nome, _, _) in PAPEIS.items():
        reaccao = neural_r1.reaccao(estado, id_) if neural_r1.R1_ACTIVO else None
        if reaccao is None:
            rede = estado["neural"][id_]
            reaccao = {"emocao": rede["emocao"], "intensidade": rede["intensidade"],
                       "fala": FALAS[rede["emocao"]]}
        resultado.append({"id": id_, "nome": nome, "emocao": reaccao["emocao"],
                          "intensidade": reaccao["intensidade"], "fala": reaccao["fala"],
                          "papel": TAREFAS[id_]})
    return resultado

