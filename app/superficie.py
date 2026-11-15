"""Exploração da superfície definida no servidor: traje, oxigénio, rover, escavação e laboratório.

Tudo o que o cliente 2D mostra sobre a saída extraveicular (EVA) vive no estado da partida, em
estado["superficie"], para os dois jogadores verem o mesmo e para contar no relatório:

    {"rover": {"m": -9.0, "condutor": None},
     "cavados": [3, 4],                                  # índices de ESCAVAR já escavados
     "amostras": {"solo": 1, "gelo": 1},                 # amostras analisadas no laboratório
     "saidas": 2, "emergencias": 0,
     "astronautas": {id: {"local": "dentro"|"fora", "saida_em": epoch|None,
                          "leva": {"rocha": False, "solo": 0, "gelo": 0}}}}

Posição: o cliente envia a presença em x (−10,4 … 10,4). Na superfície, 1 unidade de x = ESCALA metros,
por isso o terreno vai de −520 m a +520 m e o servidor conhece a distância de cada astronauta à base.
"""
from time import time

ESCALA = 50                 # metros por unidade de x da presença
MUNDO = 520                 # metros para cada lado da nave
OXIGENIO_TRAJE = 300        # segundos de oxigénio do traje
V_ANDAR, V_ROVER = 4, 13    # metros por segundo
ALCANCE = 6                 # metros a que se pode usar um local
POS = {"nave": 0, "carga": 5, "energia": -16, "torre": 13, "habitat": 28, "rover": -9,
       "rocha": -95, "baliza": 210, "cratera": -292}
ESCAVAR = [{"m": -48, "tipo": "solo"}, {"m": 70, "tipo": "solo"}, {"m": 150, "tipo": "solo"},
           {"m": -200, "tipo": "solo"}, {"m": -336, "tipo": "gelo"}]
LOCAIS_M = {"baliza": POS["baliza"], "cratera": POS["cratera"]}
ACOES = {"sair_base", "entrar_base", "rover", "recolher", "analisar"}
BONUS_AMOSTRA, BONUS_MAXIMO, CUSTO_EMERGENCIA = 2, 10, 5
ANALISES = {
    ("lua", "solo"): "Solo lunar analisado: grãos afiados e vítreos, feitos por impactos de meteoritos.",
    ("marte", "solo"): "Solo de Marte analisado: o óxido de ferro dá a cor ao planeta e os percloratos são tóxicos.",
    ("lua", "gelo"): "Gelo de água confirmado na amostra da cratera em sombra.",
    ("marte", "gelo"): "Gelo de água confirmado na amostra do subsolo.",
}


class Recusa(Exception):
    """Regra da superfície violada (o motor converte em Regra)."""


def exigir(condicao, mensagem):
    if not condicao:
        raise Recusa(mensagem)


def catalogo():
    return {"escala": ESCALA, "mundo": MUNDO, "oxigenio_s": OXIGENIO_TRAJE, "v_andar": V_ANDAR,
            "v_rover": V_ROVER, "alcance": ALCANCE, "pos": POS, "escavar": ESCAVAR}


def dados(estado):
    return estado.setdefault("superficie", {"rover": {"m": POS["rover"], "condutor": None}, "cavados": [],
                                            "amostras": {"solo": 0, "gelo": 0}, "saidas": 0,
                                            "emergencias": 0, "astronautas": {}})


def astronauta(estado, id_):
    return dados(estado)["astronautas"].setdefault(
        id_, {"local": "dentro", "saida_em": None, "leva": {"rocha": False, "solo": 0, "gelo": 0}})


def porta(estado):
    return POS["habitat"] + 1.6 if "habitat" in estado["montados"] else POS["nave"] + 1.4


def oxigenio(astro, agora):
    if astro["local"] != "fora" or astro["saida_em"] is None:
        return OXIGENIO_TRAJE
    return max(0, round(OXIGENIO_TRAJE - (agora - astro["saida_em"]), 1))


def _recolher_astronauta(estado, id_):
    astro, sup = astronauta(estado, id_), dados(estado)
    astro.update(local="dentro", saida_em=None, leva={"rocha": False, "solo": 0, "gelo": 0})
    if sup["rover"]["condutor"] == id_:
        sup["rover"]["condutor"] = None


def acabou(estado, id_, agora=None):
    """True quando o astronauta está lá fora e o oxigénio do traje chegou a zero (não altera o estado)."""
    sup = estado.get("superficie")
    astro = sup["astronautas"].get(id_) if sup else None
    return bool(astro and astro["local"] == "fora" and not estado["desfecho"]
                and oxigenio(astro, time() if agora is None else agora) <= 0)


def expirar(estado, id_, agora=None):
    """Se o oxigénio do traje acabou, traz o astronauta de volta. Devolve True quando o estado mudou."""
    if not acabou(estado, id_, agora):
        return False
    _recolher_astronauta(estado, id_)
    estado["superficie"]["emergencias"] += 1
    return True


MENSAGEM_EMERGENCIA = ("O oxigénio do traje acabou. A reserva de emergência trouxe o astronauta de volta "
                       "e as amostras ficaram para trás.")


def aplicar(estado, acao, valor, jogador, posicao, agora, ligados, registar):
    """Comandos da superfície. posicao é a distância à nave em metros (ou None em testes unitários)."""
    exigir(estado["pouso"] is not None and estado["fase"] in ("aproximacao", "instalacao", "operacao"),
           "Chega à superfície antes de usar o traje.")
    sup, id_ = dados(estado), jogador["id"]
    astro = astronauta(estado, id_)
    perto = lambda m: posicao is None or abs(posicao - m) <= ALCANCE
    fora = astro["local"] == "fora"
    if acao == "sair_base":
        exigir(not fora, "Já estás lá fora.")
        exigir(not estado["desafio"], "Resolve o incidente antes de sair.")
        astro.update(local="fora", saida_em=agora)
        sup["saidas"] += 1
    elif acao == "entrar_base":
        exigir(fora, "Já estás dentro da base.")
        exigir(sup["rover"]["condutor"] != id_, "Sai do rover antes de entrar.")
        exigir(perto(porta(estado)), "Aproxima-te da porta para entrar.")
        astro.update(local="dentro", saida_em=None)
    elif acao == "rover":
        rover = sup["rover"]
        exigir(fora and valor in ("entrar", "sair"), "Usa o rover lá fora, de traje vestido.")
        if valor == "entrar":
            exigir(estado["descarregada"] and estado["carga"].get("rover", 0) > 0, "Esta missão não trouxe um rover.")
            exigir(rover["condutor"] is None or rover["condutor"] not in ligados, "O rover já tem condutor.")
            exigir(perto(rover["m"]), "Aproxima-te do rover.")
            rover["condutor"] = id_
        else:
            exigir(rover["condutor"] == id_, "Não estás a conduzir o rover.")
            rover["condutor"] = None
            if posicao is not None:
                rover["m"] = round(max(-MUNDO, min(MUNDO, posicao)), 1)
    elif acao == "recolher":
        exigir(fora, "Veste o traje e sai para recolher amostras.")
        exigir(sup["rover"]["condutor"] != id_, "Sai do rover para recolher a amostra.")
        if valor == "rocha":
            exigir("amostra" not in estado.get("descobertas", []) and not astro["leva"]["rocha"],
                   "A rocha já foi amostrada.")
            exigir(perto(POS["rocha"]), "Aproxima-te da rocha para usar a picareta.")
            astro["leva"]["rocha"] = True
        else:
            exigir(type(valor) is int and 0 <= valor < len(ESCAVAR), "Escolhe um local de escavação.")
            exigir(valor not in sup["cavados"], "Este local já foi escavado.")
            exigir(perto(ESCAVAR[valor]["m"]), "Aproxima-te do local para cavar.")
            sup["cavados"].append(valor)
            astro["leva"][ESCAVAR[valor]["tipo"]] += 1
    elif acao == "analisar":
        exigir(not fora, "As amostras analisam-se dentro da base.")
        exigir(valor in ("rocha", "solo", "gelo"), "Escolhe a amostra a analisar.")
        if valor == "rocha":
            exigir(astro["leva"]["rocha"], "Não trouxeste uma amostra de rocha.")
            astro["leva"]["rocha"] = False
            estado.setdefault("descobertas", []).append("amostra")
            registar(estado, "Analisaste uma amostra de rocha da superfície.")
        else:
            exigir(astro["leva"][valor] > 0, "Não trouxeste amostras desse tipo.")
            sup["amostras"][valor] += astro["leva"][valor]
            astro["leva"][valor] = 0
            registar(estado, ANALISES[(estado["destino"], valor)])


def exigir_exploracao(estado, valor, jogador, posicao, agora):
    """Regras da EVA para o scanner (baliza e depressão) quando o servidor conhece a posição."""
    if posicao is None:
        return
    exigir(valor != "amostra", "Recolhe a rocha com a picareta e analisa-a no laboratório.")
    astro = astronauta(estado, jogador["id"])
    exigir(astro["local"] == "fora", "Veste o traje e sai para usar o scanner.")
    exigir(abs(posicao - LOCAIS_M[valor]) <= ALCANCE, "Aproxima-te do local para usar o scanner.")


def publico(estado, agora=None):
    """Vista para os clientes: igual ao estado, com o oxigénio que resta a cada astronauta."""
    sup = estado.get("superficie")
    if not sup:
        return None
    agora = time() if agora is None else agora
    return {**sup, "oxigenio_max": OXIGENIO_TRAJE,
            "astronautas": {id_: {"local": a["local"], "leva": a["leva"], "oxigenio": oxigenio(a, agora)}
                            for id_, a in sup["astronautas"].items()}}


def bonus(estado):
    sup = estado.get("superficie")
    if not sup:
        return 0, None
    amostras = sum(sup["amostras"].values())
    pontos = min(BONUS_MAXIMO, BONUS_AMOSTRA * amostras) - CUSTO_EMERGENCIA * sup["emergencias"]
    return pontos, {"amostras": amostras, "escavacoes": len(sup["cavados"]), "saidas": sup["saidas"],
                    "emergencias": sup["emergencias"]}
