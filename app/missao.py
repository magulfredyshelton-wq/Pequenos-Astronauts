from random import Random
from secrets import randbits
from time import time

from . import eva, nasa, superficie
from .catalogo import CARGA, LINHAS, MONTAGEM, PERFIS, carga_minima
from .neural import estado_inicial, reagir

LIMITE_EXPOSICAO = 6
LIMITE_ADIAMENTOS = 2
ESSENCIAIS = ("agua", "comida", "oxigenio", "propulsante", "energia")
CONSUMOS_DIARIOS = {"agua": 6, "comida": 3, "oxigenio": 3}
MARCOS_VARIAVEIS = (0.15, 0.32, 0.49, 0.65, 0.79, 0.90, 0.97)
MARCOS_EXPEDICAO = (0.33, 0.72)
# x é a posição na superfície em unidades de presença (metros / superficie.ESCALA); z já não é usado.
LOCAIS = {
    "amostra": (superficie.POS["rocha"] / superficie.ESCALA, 0, "Analisaste uma amostra de rocha da superfície."),
    "baliza": (superficie.POS["baliza"] / superficie.ESCALA, 0, "Ligaste a baliza e confirmaste a posição da base."),
    "cratera": (superficie.POS["cratera"] / superficie.ESCALA, 0, "Registaste as marcas do terreno sem entrar na depressão."),
}
VIAGEM = {"lua": (0.15, 0.36, 0.54, 0.70, 0.84, 0.96, 0.97, 0.98, 0.99),
          "marte": (0.12, 0.29, 0.48, 0.64, 0.81, 0.96, 0.97, 0.98, 0.99)}
PERDAS = {
    "desvio": ("propulsante", 18), "impacto": ("energia", 28),
    "oxigenio": ("oxigenio", 6), "co2": ("oxigenio", 4),
    "radiacao": ("exposicao", 4), "atraso": ("margem", 1),
    "rochas": ("propulsante", 18), "sombra": ("energia", 25),
    "relevo": ("margem", 1), "rover_lua": ("mobilidade", 20),
    "junta": ("mobilidade", 16), "gelo_lua": ("energia", 18),
    "pouso_marte": ("energia", 12), "tempestade": ("energia", 26),
    "frio": ("energia", 15), "conjuncao": ("margem", 1),
    "gelo_marte": ("agua", 6), "roda_marte": ("mobilidade", 20),
    "sensor_estrelas": ("propulsante", 10), "refrigeracao": ("energia", 18),
    "reciclagem_agua": ("agua", 8), "poeira_antecamara": ("mobilidade", 12),
    "oscilacao_termica": ("energia", 16), "retransmissor": ("margem", 1),
    "painel_marte": ("energia", 20), "amostra_marte": ("margem", 1),
    "abrigo_marte": ("exposicao", 3),
}
USOS = {"co2": "filtro", "impacto": "bateria", "junta": "pecas", "roda_marte": "pecas", "rover_lua": "pecas"}
CONCEITOS = {
    "desvio": "Pequenos ajustes cedo ajudam a preservar propulsante.",
    "impacto": "Quando a produção diminui, poupar energia prolonga a autonomia da bateria.",
    "oxigenio": "Conter uma fuga permite proteger a reserva que ainda está intacta.",
    "co2": "Remover CO₂ e fornecer oxigénio são duas tarefas distintas.",
    "radiacao": "O abrigo blindado ajuda a reduzir a exposição durante o alerta.",
    "atraso": "O sinal leva tempo a chegar à Terra e a resposta também leva tempo a voltar.",
    "rochas": "Uma zona de pouso precisa de terreno seguro e de uma margem de manobra.",
    "sombra": "O relevo pode tirar luz aos painéis enquanto o consumo continua.",
    "relevo": "Uma elevação pode bloquear a ligação de rádio.",
    "rover_lua": "Uma peça pequena pode proteger o veículo da poeira levantada pelas rodas.",
    "junta": "A poeira interfere nas ligações e pode agravar o desgaste.",
    "gelo_lua": "Prospectar gelo exige reservar energia para o regresso.",
    "pouso_marte": "Um pouso seguro só resolve parte da missão: a carga precisa de ficar acessível.",
    "tempestade": "A poeira pode reduzir a luz nos painéis. Diminuir o consumo protege a reserva.",
    "frio": "O aquecimento é uma carga prioritária durante a noite fria.",
    "conjuncao": "Procedimentos locais permitem continuar quando a ligação fica limitada.",
    "gelo_marte": "Uma indicação de gelo só vira água útil depois de confirmar, extrair e tratar.",
    "roda_marte": "Uma rota segura pode preservar as rodas mesmo quando é mais longa.",
    "sensor_estrelas": "Comparar estrelas conhecidas ajuda a determinar para onde a nave aponta.",
    "refrigeracao": "O controlo térmico mantém os sistemas dentro dos seus limites.",
    "reciclagem_agua": "A água recuperada passa por tratamento e verificação antes de ser usada.",
    "poeira_antecamara": "O regolito lunar é abrasivo. A limpeza antes da entrada reduz o desgaste.",
    "oscilacao_termica": "A iluminação local muda as condições térmicas e a disponibilidade de energia.",
    "retransmissor": "Um retransmissor permite manter contacto em zonas que ficam fora da linha de visão.",
    "painel_marte": "A poeira depositada num painel reduz a luz que chega às células solares.",
    "amostra_marte": "Isolar as amostras e registar a origem ajuda a evitar contaminação cruzada.",
    "abrigo_marte": "O tempo de exposição importa. Um abrigo com blindagem ajuda a reduzi-lo.",
}


class Regra(ValueError):
    pass


def exigir(condicao, mensagem):
    if not condicao:
        raise Regra(mensagem)


def inicial():
    return {"fase": "preparacao_na_terra", "destino": None, "carga": {}, "inventario": {},
            "horas": 0, "horas_rota": 0, "proximo": 0, "desafio": None, "recuperacao": False, "pouso": None,
            "montados": [], "descarregada": False, "prontos": [], "piloto": None, "ajuste_rota": 0, "recursos": {"energia": 100, "exposicao": 0, "margem": 6, "mobilidade": 100},
            "reservas_iniciais": {}, "votos": [], "votos_desafio": {}, "historico": [],
            "sinal": "", "mensagem": "Escolhe o destino e prepara os mantimentos.", "desfecho": None}


def novo_estado():
    estado = inicial()
    estado["neural"] = estado_inicial()
    return estado


def resumo_carga(estado):
    carga = estado["carga"]
    minimo = carga_minima(estado["destino"]) if estado["destino"] else {}
    return {
        "kg": sum(CARGA[k][1] * q for k, q in carga.items()),
        "litros": sum(CARGA[k][2] * q for k, q in carga.items()),
        "faltas": {k: q - carga.get(k, 0) for k, q in minimo.items() if carga.get(k, 0) < q},
    }


def desafio_do_tema(tema, destino):
    """Índice (>0) do desafio de superfície que corresponde ao tema de uma EVA real, ou None."""
    for id_ in eva.TEMAS.get(tema, {}).get(destino, ()):
        for indice, linha in enumerate(LINHAS[destino]):
            if indice and linha[0] == id_:
                return indice
    return None


def plano_da_rota(destino, semente, tema=None):
    sorteio = Random(semente)
    viagem = [sorteio.choice([0, 1, 6, 7]), sorteio.choice([2, 3, 4, 5, 8])]
    superficie = sorteio.sample(range(1, len(LINHAS[destino])), 6)
    indice = desafio_do_tema(tema, destino) if tema else None
    if indice is not None:  # a EVA real escolhe o primeiro incidente da superfície
        superficie = [indice] + [i for i in superficie if i != indice][:5]
    return {"viagem": viagem, destino: [0, *superficie]}


def nota_eva(estado, grupo, indice):
    """Frase que liga o incidente à EVA real que o inspirou (só no incidente escolhido por ela)."""
    referencia = estado.get("eva")
    ordem = estado.get("plano", {}).get(grupo, [])
    if (not referencia or grupo != estado["destino"] or len(ordem) < 2 or indice != ordem[1]
            or LINHAS[grupo][indice][0] != referencia.get("desafio")):
        return ""
    quando = f" ({referencia['data'][:4]})" if referencia.get("data") else ""
    return f" Inspirado numa saída extraveicular real da NASA{quando}: {referencia['tema_pt']}."


def nota_espacial(estado, grupo, indice):
    """Aviso quando um alerta solar real do DONKI agrava este incidente (só com ASTRO_NASA_JOGO=1)."""
    ciencia = estado.get("ciencia") or {}
    tempo = ciencia.get("tempo_espacial") or {}
    if ciencia.get("fator_exposicao", 1) <= 1 or LINHAS[grupo][indice][0] not in ("radiacao", "abrigo_marte"):
        return ""
    evento = next((e for e in tempo.get("eventos") or [] if isinstance(e, dict) and e.get("resumo")), {})
    detalhe = " Regista-se meteorologia espacial " + str(tempo.get("rotulo") or "elevada") + "."
    if evento.get("resumo"):
        detalhe += " NASA DONKI: " + eva.limpar(evento["resumo"], 140)
    return detalhe


def perda(estado, id_):
    """Perda de um incidente; um alerta solar real só aumenta o custo em exposição."""
    recurso, quantidade = PERDAS[id_]
    if recurso == "exposicao":
        quantidade = max(1, round(quantidade * (estado.get("ciencia") or {}).get("fator_exposicao", 1)))
    return recurso, quantidade


def ordem_de_desafios(estado, grupo):
    return estado.get("plano", {}).get(grupo, list(range(len(LINHAS[grupo]))))


def estatisticas(estado):
    return estado.setdefault("estatisticas", {"seguras": 0, "riscos": 0, "recuperadas": 0, "adiamentos": 0})


def fechar_missao(estado, desfecho, mensagem):
    estado.update(fase="retirada" if desfecho == "retirada_segura" else "concluida",
                  desfecho=desfecho, desafio=None, recuperacao=False, piloto=None,
                  votos=[], votos_desafio={}, espera_equipa=None, motivo_desfecho=mensagem)
    registar(estado, mensagem, "sucesso" if desfecho == "base_estabilizada" else "alerta")


def relatorio(estado):
    if not estado["desfecho"]:
        return None
    dados = estado.get("estatisticas")
    pontos = None
    estrelas = None
    if dados is not None:
        total = len(ordem_de_desafios(estado, "viagem")) + len(ordem_de_desafios(estado, estado["destino"]))
        pontos = max(0, round(100 * (dados["seguras"] + 0.5 * dados["recuperadas"]) / total)
                     - 5 * dados["adiamentos"])
        extra, _ = superficie.bonus(estado)  # amostras analisadas somam, emergências de oxigénio descontam
        if extra:
            pontos = max(0, min(100, pontos + extra))
        if estado["desfecho"] == "base_estabilizada":
            estrelas = 3 if pontos >= 90 else 2 if pontos >= 70 else 1
        else:
            pontos, estrelas = min(pontos, 49), 0
    return {"pontos": pontos, "estrelas": estrelas, "decisoes": dados,
            "motivo": estado.get("motivo_desfecho", estado["mensagem"]),
            "eva": estado.get("eva"), "ciencia": estado.get("ciencia"), "horas_missao": estado["horas"],
            "exploracao": superficie.bonus(estado)[1]}


def actualizar_recurso(estado, nome, delta):
    recursos = estado["recursos"]
    recursos[nome] = max(0, recursos[nome] + delta)
    if nome in (*CONSUMOS_DIARIOS, "propulsante"):
        estado["inventario"][nome] = recursos[nome]


def verificar_seguranca(estado):
    recursos = estado["recursos"]
    motivos = {
        "agua": "A reserva de água potável acabou.",
        "comida": "A reserva de comida acabou.",
        "oxigenio": "A reserva de oxigénio acabou.",
        "propulsante": "A reserva de propulsante acabou.",
        "energia": "Os sistemas essenciais ficaram sem energia.",
        "margem": "A equipa ficou sem margem para reagir a tempo.",
    }
    criticos = (*ESSENCIAIS, "margem")
    motivo = next((motivos[nome] for nome in criticos if recursos.get(nome) == 0), None)
    if recursos["exposicao"] >= LIMITE_EXPOSICAO:
        motivo = "A exposição acumulada atingiu o limite de segurança do jogo."
    if motivo:
        fechar_missao(estado, "missao_falhada", motivo + " O controlo de missão activou o plano de emergência.")
        return False
    return True


def avisos_seguranca(estado):
    if estado["fase"] == "preparacao_na_terra" or estado["desfecho"]:
        return []
    recursos = estado["recursos"]
    avisos = []
    if recursos["exposicao"] >= LIMITE_EXPOSICAO - 2:
        avisos.append("A exposição está perto do limite. Prioriza o abrigo.")
    if recursos["margem"] <= 2:
        avisos.append("A margem de resposta está baixa. Evita atrasos.")
    if recursos["energia"] <= 25:
        avisos.append("A energia está baixa. Preserva os sistemas essenciais.")
    if estado["destino"]:
        restante = PERFIS[estado["destino"]]["horas"] - estado["horas_rota"]
        for nome, diaria in CONSUMOS_DIARIOS.items():
            if recursos.get(nome, 0) <= (restante * diaria + 23) // 24 + 4:
                rotulo = CARGA[nome][0].lower()
                avisos.append(f"A reserva de {rotulo} está perto do consumo previsto.")
    if recursos.get("propulsante", 0) <= 20:
        avisos.append("A reserva de propulsante está baixa. Evita manobras adicionais.")
    return avisos


def passar_tempo(estado, horas):
    anterior = estado["horas"]
    estado["horas"] += horas
    for nome, diaria in CONSUMOS_DIARIOS.items():
        gasto = estado["horas"] * diaria // 24 - anterior * diaria // 24
        actualizar_recurso(estado, nome, -gasto)


def dados_desafio(estado, nivel):
    activo = estado["desafio"]
    if not activo:
        return None
    id_, titulo, sinal, segura, risco, _, recuperar = LINHAS[activo["grupo"]][activo["indice"]]
    recuperacao = estado["recuperacao"]
    opcoes = {"segura": segura, "risco": risco}
    if recuperacao:
        opcoes = {"recuperar": recuperar}
        if estado.get("adiamentos", 0) < LIMITE_ADIAMENTOS:
            opcoes["adiar"] = "Ganhar tempo para avaliar, consumindo reservas"
        sinal = estado["mensagem"]
    ordem = list(opcoes)
    Random(f"{estado.get('semente', 0)}:{id_}:{recuperacao}").shuffle(ordem)
    return {"id": id_, "titulo": titulo, "sinal": sinal,
            "modo": {"cadete": "multipla_escolha", "piloto": "comparacao",
                     "comandante": "resposta_aberta"}[nivel],
            "opcoes": opcoes, "ordem": ordem, "recuperacao": recuperacao,
            "adiamentos_restantes": LIMITE_ADIAMENTOS - estado.get("adiamentos", 0)}


def registar(estado, mensagem, sinal=""):
    estado["mensagem"] = mensagem
    estado["sinal"] = sinal
    estado["historico"].append({"horas": estado["horas"], "fase": estado["fase"], "mensagem": mensagem, "sinal": sinal})
    estado["historico"] = estado["historico"][-40:]
    reagir(estado)


def definir_carga(estado, carga):
    exigir(isinstance(carga, dict) and all(k in CARGA and type(q) is int and 0 <= q <= 10000
                                          for k, q in carga.items()), "A carga requer quantidades inteiras válidas.")
    anterior = estado["carga"]
    estado["carga"] = {k: q for k, q in carga.items() if q}
    medidas = resumo_carga(estado)
    perfil = PERFIS[estado["destino"]]
    if medidas["kg"] > perfil["limite_kg"] or medidas["litros"] > perfil["limite_l"]:
        estado["carga"] = anterior
        raise Regra("A carga ultrapassa a massa ou o volume da nave.")


def abrir_desafio(estado, grupo, indice):
    estado["votos_desafio"] = {}
    estado["desafio"] = {"grupo": grupo, "indice": indice}
    estado["recuperacao"] = False
    estado["adiamentos"] = 0
    registar(estado, LINHAS[grupo][indice][2] + nota_eva(estado, grupo, indice)
             + nota_espacial(estado, grupo, indice), "alerta")


def avancar(estado):
    destino = estado["destino"]
    grupo = "viagem" if estado["fase"] == "viagem" else destino
    ordem = ordem_de_desafios(estado, grupo)
    indice = estado["proximo"]
    if grupo == "viagem":
        total = PERFIS[destino]["horas"]
        marcos = MARCOS_EXPEDICAO if estado.get("expedicao") else (
            MARCOS_VARIAVEIS if "plano" in estado else VIAGEM[destino]
        )
        horas_rota = round(total * marcos[indice]) if indice < len(ordem) else total
        passar_tempo(estado, horas_rota - estado["horas_rota"])
        estado["horas_rota"] = horas_rota
        actualizar_recurso(estado, "propulsante", -2)
        if not verificar_seguranca(estado):
            return
        if indice == len(ordem):
            estado["fase"] = "aproximacao"
            estado["proximo"] = 0
            registar(estado, "Chegaste ao destino. Compara as zonas e escolhe onde pousar.")
            return
    elif indice < len(ordem):
        passar_tempo(estado, 2)
        actualizar_recurso(estado, "energia", -2)
        if not verificar_seguranca(estado):
            return
    else:
        if verificar_seguranca(estado):
            fechar_missao(estado, "base_estabilizada", "Missão concluída. A base está operacional.")
        return
    abrir_desafio(estado, grupo, ordem[indice])


def responder(estado, escolha):
    activo = estado["desafio"]
    exigir(activo is not None, "Não existe um desafio activo.")
    id_, _, _, _, _, consequencia, _ = LINHAS[activo["grupo"]][activo["indice"]]
    dados = estatisticas(estado)
    em_recuperacao = estado["recuperacao"]
    if em_recuperacao and escolha == "adiar":
        adiamentos = estado.get("adiamentos", 0)
        exigir(adiamentos < LIMITE_ADIAMENTOS, "A espera terminou. Recupera ou pede retirada.")
        estado["adiamentos"] = adiamentos + 1
        dados["adiamentos"] += 1
        passar_tempo(estado, 2 + adiamentos)
        actualizar_recurso(estado, "energia", -(8 + 4 * adiamentos))
        actualizar_recurso(estado, "margem", -1)
        if perda(estado, id_)[0] in ("agua", "oxigenio", "exposicao"):
            recurso = perda(estado, id_)[0]
            actualizar_recurso(estado, recurso, 2 if recurso == "exposicao" else -2)
        if verificar_seguranca(estado):
            restantes = LIMITE_ADIAMENTOS - estado["adiamentos"]
            mensagem = "Adiaste a intervenção. Restam " + str(restantes) + " adiamentos neste incidente."
            registar(estado, mensagem, "alerta")
        return

    if not em_recuperacao and escolha == "risco":
        recurso, quantidade = perda(estado, id_)
        dados["riscos"] += 1
        if estado.get("expedicao") and dados["riscos"] > 2 and recurso != "margem":
            actualizar_recurso(estado, "margem", -1)
        actualizar_recurso(estado, recurso, quantidade if recurso == "exposicao" else -quantidade)
        if verificar_seguranca(estado):
            estado["recuperacao"] = True
            estado["votos"] = []
            registar(estado, consequencia, "alerta")
        return

    exigir(escolha == ("recuperar" if em_recuperacao else "segura"), "Escolhe uma opção válida do desafio.")
    detalhe = ""
    item = USOS.get(id_)
    if item and estado["inventario"].get(item, 0):
        estado["inventario"][item] -= 1
        detalhe = f" Usaste {CARGA[item][0].lower()} da carga."
        if item == "bateria":
            estado["recursos"]["energia"] = min(100, estado["recursos"]["energia"] + 20)
    elif item:
        detalhe = " Aplicaste o procedimento de contingência com capacidade reduzida."
        passar_tempo(estado, 1)

    if em_recuperacao:
        passar_tempo(estado, 2)
        recurso = perda(estado, id_)[0]
        if recurso == "energia" and 0 < estado["recursos"]["energia"] < 36:
            passar_tempo(estado, 2)
            estado["recursos"]["energia"] = 36
            detalhe += " A equipa recuperou energia ao estabilizar a alimentação."
    if not verificar_seguranca(estado):
        return
    dados["recuperadas" if em_recuperacao else "seguras"] += 1
    estado["desafio"] = None
    estado["recuperacao"] = False
    estado["adiamentos"] = 0
    estado["proximo"] = estado["proximo"] + 1 if "plano" in estado else activo["indice"] + 1
    if estado["fase"] == "aproximacao":
        estado["fase"] = "instalacao"
    registar(estado, CONCEITOS[id_] + detalhe, "sucesso")


def aplicar(estado, acao, valor, jogador, ligados, total=1, cooperativa=False, posicao=None, agora=None):
    fase = estado["fase"]
    anfitriao = bool(jogador["anfitriao"])
    exigir(not estado["desfecho"], "A missão já terminou.")
    if acao == "destino":
        exigir(fase == "preparacao_na_terra" and anfitriao and isinstance(valor, str) and valor in PERFIS,
               "O anfitrião escolhe Lua ou Marte no hangar.")
        if estado["destino"] != valor:
            estado["destino"] = valor
            estado["carga"] = {}
            estado["prontos"] = []
        registar(estado, "Destino seleccionado: " + PERFIS[valor]["nome"] + ".")
    elif acao == "carga":
        exigir(fase == "preparacao_na_terra" and anfitriao and estado["destino"],
               "O anfitrião deve escolher o destino antes de editar a carga.")
        anterior = estado["carga"]
        definir_carga(estado, valor)
        if estado["carga"] != anterior:
            estado["prontos"] = []
        registar(estado, "Manifesto de carga actualizado.")
    elif acao == "pronto":
        exigir(fase == "preparacao_na_terra" and estado["destino"] and not resumo_carga(estado)["faltas"],
               "Completa o plano antes de confirmar prontidão.")
        prontos = set(estado["prontos"])
        prontos.add(jogador["id"])
        estado["prontos"] = sorted(prontos)
    elif acao == "lancar":
        exigir(fase == "preparacao_na_terra" and anfitriao and estado["destino"],
               "O anfitrião só pode lançar após escolher o destino.")
        exigir(not resumo_carga(estado)["faltas"], "Ainda faltam recursos essenciais no manifesto.")
        exigir(total == 1 or (len(ligados) == total and ligados <= set(estado["prontos"])),
               "Todos os astronautas devem estar ligados e confirmar este plano.")
        estado["reservas_iniciais"] = dict(estado["carga"])
        estado["inventario"] = dict(estado["carga"])
        estado["recursos"].update({k: estado["carga"][k] for k in ("agua", "comida", "oxigenio", "propulsante")})
        if cooperativa:
            estado["semente"] = randbits(63)
        referencia = eva.escolher(estado.get("semente") or randbits(63))
        if referencia:  # EVA real da NASA que serve de referência a esta missão
            indice = desafio_do_tema(referencia["tema"], estado["destino"])
            referencia["desafio"] = LINHAS[estado["destino"]][indice][0] if indice else None
            estado["eva"] = referencia
        ciencia = nasa.referencia(estado["destino"], estado.get("semente") or randbits(63))
        if ciencia:  # APOD, DONKI, RadLab e OSDR reais desta missão (nunca usa a rede)
            estado["ciencia"] = ciencia
        if cooperativa:
            estado["plano"] = plano_da_rota(estado["destino"], estado["semente"],
                                            referencia["tema"] if referencia else None)
            estado["expedicao"] = 1
            estado["descobertas"] = []
        estatisticas(estado)
        estado["fase"] = "viagem"
        registar(estado, "Lançamento confirmado. Avança até ao primeiro marco da viagem.", "sucesso")
    elif acao == "assumir_posto":
        exigir(fase == "viagem" and not estado["desafio"], "A pilotagem está disponível entre incidentes da viagem.")
        exigir(estado["piloto"] not in ligados or estado["piloto"] == jogador["id"],
               "Outro astronauta está a pilotar.")
        estado["piloto"] = jogador["id"]
        estado["votos"] = []
        registar(estado, "Posto de pilotagem assumido. Usa a consola para praticar uma correcção.")
    elif acao == "libertar_posto":
        exigir(estado["piloto"] == jogador["id"], "Apenas o piloto pode libertar o seu posto.")
        estado["piloto"] = None
        registar(estado, "Controlo devolvido à navegação automática.")
    elif acao == "ajustar_rota":
        exigir(fase == "viagem" and not estado["desafio"] and estado["piloto"] == jogador["id"],
               "Assume o posto livre entre incidentes antes de manobrar.")
        exigir(type(valor) is int and valor in (-1, 1), "Escolhe o sentido da correcção.")
        exigir(estado["recursos"]["propulsante"] >= 4, "Propulsante insuficiente para a manobra.")
        novo = estado["ajuste_rota"] + valor
        exigir(-2 <= novo <= 2, "O ajuste já está no limite de treino.")
        estado["ajuste_rota"] = novo
        estado["recursos"]["propulsante"] -= 4
        estado["inventario"]["propulsante"] = estado["recursos"]["propulsante"]
        if not verificar_seguranca(estado):
            return
        registar(estado, "Ajuste de trajectória registado. A manobra consumiu 4 unidades de propulsante.")
    elif acao == "avancar":
        exigir(fase in ("viagem", "operacao") and not estado["desafio"],
               "Resolve o desafio em curso antes de avançar.")
        exigir(estado["piloto"] not in ligados, "O piloto deve devolver o controlo à navegação automática.")
        estado["piloto"] = None
        votantes = set(estado["votos"]) & ligados
        votantes.add(jogador["id"])
        if ligados <= votantes:
            estado["votos"] = []
            avancar(estado)
        else:
            estado["votos"] = sorted(votantes)
            registar(estado, f"Avanço aprovado por {len(votantes)} de {len(ligados)} jogadores ligados.")
    elif acao == "pousar":
        exigir(fase == "aproximacao" and anfitriao and not estado["desafio"] and type(valor) is int and valor in (0, 1),
               "O anfitrião deve seleccionar uma zona de pouso disponível.")
        custo = 12 if valor == 0 else 18
        exigir(valor == 0 or estado["recursos"]["propulsante"] > custo,
               "Escolhe a zona que exige menos propulsante.")
        estado["pouso"] = valor
        actualizar_recurso(estado, "propulsante", -custo)
        if not verificar_seguranca(estado):
            estado["pouso"] = None
            return
        abrir_desafio(estado, estado["destino"], 0)
    elif acao == "responder":
        opcoes = dados_desafio(estado, jogador["nivel"])
        exigir(opcoes and isinstance(valor, str) and valor in opcoes["opcoes"], "Escolhe uma opção do desafio activo.")
        if cooperativa and len(ligados) > 1:
            votos = {id_: escolha for id_, escolha in estado.get("votos_desafio", {}).items() if id_ in ligados}
            votos[jogador["id"]] = valor
            estado["votos_desafio"] = votos
            if votos.keys() != ligados or len(set(votos.values())) > 1:
                estado["espera_equipa"] = "divergencia" if len(set(votos.values())) > 1 else "aguarda"
                return
        estado["espera_equipa"] = None
        estado["votos_desafio"] = {}
        responder(estado, valor)
    elif acao == "explorar":
        exigir(fase in ("instalacao", "operacao") and isinstance(valor, str) and valor in LOCAIS,
               "Chega à superfície para registar uma descoberta.")
        descobertas = estado.setdefault("descobertas", [])
        exigir(valor not in descobertas, "Este local já foi registado no diário.")
        try:
            superficie.exigir_exploracao(estado, valor, jogador, posicao, agora)
        except superficie.Recusa as recusa:
            raise Regra(str(recusa)) from recusa
        descobertas.append(valor)
        registar(estado, LOCAIS[valor][2])
    elif acao == "descarregar":
        exigir(fase == "instalacao" and not estado["descarregada"], "A carga já foi descarregada ou ainda não chegou.")
        estado["descarregada"] = True
        if estado["pouso"] == 1:
            passar_tempo(estado, 2)
            actualizar_recurso(estado, "energia", -8)
        if not verificar_seguranca(estado):
            return
        registar(estado, "Carga descarregada. Confirma o inventário e prepara a instalação.", "sucesso")
    elif acao == "instalar":
        i = len(estado["montados"])
        exigir(fase == "instalacao" and estado["descarregada"] and i < len(MONTAGEM) and valor == MONTAGEM[i][0],
               "Instala energia, comunicações e habitat por essa ordem.")
        exigir(estado["inventario"].get(valor, 0) > 0, "O módulo necessário não está no inventário entregue.")
        estado["inventario"][valor] -= 1
        estado["montados"].append(valor)
        if len(estado["montados"]) == len(MONTAGEM):
            estado["fase"] = "operacao"
        registar(estado, MONTAGEM[i][1] + ": concluído.", "sucesso")
    elif acao in superficie.ACOES:
        try:
            superficie.aplicar(estado, acao, valor, jogador, posicao, time() if agora is None else agora,
                               ligados, registar)
        except superficie.Recusa as recusa:
            raise Regra(str(recusa)) from recusa
    elif acao == "retirada":
        exigir(anfitriao and estado["recuperacao"], "A retirada está disponível durante uma recuperação.")
        fechar_missao(estado, "retirada_segura", "Retirada em segurança confirmada. A tripulação está protegida.")
    else:
        raise Regra("Comando desconhecido.")

