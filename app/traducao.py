"""Tradução para inglês feita no servidor.

O jogo guarda e calcula tudo em português. Quando o cliente envia o cabeçalho «X-Lang: en», a resposta
(estado, incidentes, catálogo, diário, relatório e erros) é traduzida à saída, em main.py.
test_traducao.py garante que cada mensagem do servidor tem tradução, para não aparecer português por engano.
"""
import re

from . import catalogo_en
from .catalogo import CARGA, FRASES_PT as _FRASES_PT, LINHAS, MONTAGEM, PERFIS
from .cerebro.reaccoes import FALAS
from .eva import ROTULOS
from .missao import CONCEITOS, LOCAIS
from .neural import FALAS as FALAS_LEVES, TAREFAS
from .superficie import ANALISES, MENSAGEM_EMERGENCIA

FIXAS = {
    # ── missão ──
    "Escolhe o destino e prepara os mantimentos.": "Choose the destination and prepare the supplies.",
    "Manifesto de carga actualizado.": "Cargo manifest updated.",
    "Lançamento confirmado. Avança até ao primeiro marco da viagem.": "Launch confirmed. Advance to the first waypoint of the trip.",
    "Chegaste ao destino. Compara as zonas e escolhe onde pousar.": "You have arrived. Compare the zones and choose where to land.",
    "Carga descarregada. Confirma o inventário e prepara a instalação.": "Cargo unloaded. Check the inventory and prepare the installation.",
    "Missão concluída. A base está operacional.": "Mission complete. The base is operational.",
    "Retirada em segurança confirmada. A tripulação está protegida.": "Safe withdrawal confirmed. The crew is protected.",
    "Posto de pilotagem assumido. Usa a consola para praticar uma correcção.": "You have the pilot seat. Use the console to practise a correction.",
    "Controlo devolvido à navegação automática.": "Control handed back to the autopilot.",
    "Ajuste de trajectória registado. A manobra consumiu 4 unidades de propulsante.": "Trajectory adjustment logged. The manoeuvre used 4 units of propellant.",
    "Ganhar tempo para avaliar, consumindo reservas": "Buy time to assess, using up reserves",
    "A espera terminou. Recupera ou pede retirada.": "The wait is over. Recover or ask for withdrawal.",
    "A energia está baixa. Preserva os sistemas essenciais.": "Power is low. Protect the essential systems.",
    "A exposição está perto do limite. Prioriza o abrigo.": "Exposure is near the limit. Make the shelter your priority.",
    "A margem de resposta está baixa. Evita atrasos.": "The response margin is low. Avoid delays.",
    "A reserva de propulsante está baixa. Evita manobras adicionais.": "Propellant is low. Avoid extra manoeuvres.",
    "A equipa ficou sem margem para reagir a tempo.": "The team ran out of margin to react in time.",
    "A exposição acumulada atingiu o limite de segurança do jogo.": "Accumulated exposure reached the safety limit of the game.",
    "O controlo de missão activou o plano de emergência.": "Mission control activated the emergency plan.",
    "A reserva de comida acabou.": "The food reserve ran out.",
    "A reserva de oxigénio acabou.": "The oxygen reserve ran out.",
    "A reserva de propulsante acabou.": "The propellant reserve ran out.",
    "A reserva de água potável acabou.": "The drinking water reserve ran out.",
    "Os sistemas essenciais ficaram sem energia.": "The essential systems lost power.",
    "Aplicaste o procedimento de contingência com capacidade reduzida.": "You applied the contingency procedure with reduced capacity.",
    "A equipa recuperou energia ao estabilizar a alimentação.": "The team recovered power by stabilising the supply.",
    "A missão já terminou.": "The mission has already ended.",
    "O anfitrião escolhe Lua ou Marte no hangar.": "The host chooses Moon or Mars in the lobby.",
    "O anfitrião deve escolher o destino antes de editar a carga.": "The host must choose the destination before editing the cargo.",
    "Completa o plano antes de confirmar prontidão.": "Complete the plan before confirming you are ready.",
    "O anfitrião só pode lançar após escolher o destino.": "The host can only launch after choosing the destination.",
    "Ainda faltam recursos essenciais no manifesto.": "Essential supplies are still missing from the manifest.",
    "Todos os astronautas devem estar ligados e confirmar este plano.": "Every astronaut must be connected and confirm this plan.",
    "A pilotagem está disponível entre incidentes da viagem.": "Piloting is available between incidents of the trip.",
    "Outro astronauta está a pilotar.": "Another astronaut is piloting.",
    "Apenas o piloto pode libertar o seu posto.": "Only the pilot can leave the pilot seat.",
    "Assume o posto livre entre incidentes antes de manobrar.": "Take the free pilot seat between incidents before manoeuvring.",
    "Escolhe o sentido da correcção.": "Choose the direction of the correction.",
    "Propulsante insuficiente para a manobra.": "Not enough propellant for the manoeuvre.",
    "O ajuste já está no limite de treino.": "The adjustment is already at the training limit.",
    "Resolve o desafio em curso antes de avançar.": "Solve the current challenge before advancing.",
    "O piloto deve devolver o controlo à navegação automática.": "The pilot must hand control back to the autopilot.",
    "O anfitrião deve seleccionar uma zona de pouso disponível.": "The host must select an available landing zone.",
    "Escolhe a zona que exige menos propulsante.": "Choose the zone that needs less propellant.",
    "Escolhe uma opção do desafio activo.": "Choose one of the options of the active challenge.",
    "Escolhe uma opção válida do desafio.": "Choose a valid option of the challenge.",
    "Não existe um desafio activo.": "There is no active challenge.",
    "Chega à superfície para registar uma descoberta.": "Reach the surface to record a discovery.",
    "Este local já foi registado no diário.": "This place is already in the logbook.",
    "A carga já foi descarregada ou ainda não chegou.": "The cargo was already unloaded or has not arrived yet.",
    "Instala energia, comunicações e habitat por essa ordem.": "Install power, communications and habitat, in that order.",
    "O módulo necessário não está no inventário entregue.": "The module you need is not in the delivered inventory.",
    "A retirada está disponível durante uma recuperação.": "Withdrawal is available during a recovery.",
    "Comando desconhecido.": "Unknown command.",
    "A carga requer quantidades inteiras válidas.": "The cargo needs valid whole quantities.",
    "A carga ultrapassa a massa ou o volume da nave.": "The cargo is over the mass or volume limit of the ship.",
    # ── superfície ──
    "Chega à superfície antes de usar o traje.": "Reach the surface before using the suit.",
    "Já estás lá fora.": "You are already outside.",
    "Resolve o incidente antes de sair.": "Solve the incident before going out.",
    "Já estás dentro da base.": "You are already inside the base.",
    "Sai do rover antes de entrar.": "Get off the rover before going in.",
    "Aproxima-te da porta para entrar.": "Get closer to the door to go in.",
    "Usa o rover lá fora, de traje vestido.": "Use the rover outside, with the suit on.",
    "Esta missão não trouxe um rover.": "This mission did not bring a rover.",
    "O rover já tem condutor.": "The rover already has a driver.",
    "Aproxima-te do rover.": "Get closer to the rover.",
    "Não estás a conduzir o rover.": "You are not driving the rover.",
    "Veste o traje e sai para recolher amostras.": "Put on the suit and go out to collect samples.",
    "Sai do rover para recolher a amostra.": "Get off the rover to collect the sample.",
    "A rocha já foi amostrada.": "The rock has already been sampled.",
    "Aproxima-te da rocha para usar a picareta.": "Get closer to the rock to use the pick.",
    "Escolhe um local de escavação.": "Choose a place to dig.",
    "Este local já foi escavado.": "This place has already been dug.",
    "Aproxima-te do local para cavar.": "Get closer to the place to dig.",
    "As amostras analisam-se dentro da base.": "Samples are analysed inside the base.",
    "Escolhe a amostra a analisar.": "Choose the sample to analyse.",
    "Não trouxeste uma amostra de rocha.": "You did not bring a rock sample.",
    "Não trouxeste amostras desse tipo.": "You did not bring samples of that kind.",
    "Recolhe a rocha com a picareta e analisa-a no laboratório.": "Collect the rock with the pick and analyse it in the lab.",
    "Veste o traje e sai para usar o scanner.": "Put on the suit and go out to use the scanner.",
    "Aproxima-te do local para usar o scanner.": "Get closer to the place to use the scanner.",
    MENSAGEM_EMERGENCIA: "The suit oxygen ran out. The emergency reserve brought the astronaut back and the samples were left behind.",
    ANALISES[("lua", "solo")]: "Moon soil analysed: sharp, glassy grains made by meteorite impacts.",
    ANALISES[("marte", "solo")]: "Mars soil analysed: iron oxide gives the planet its colour and perchlorates are toxic.",
    ANALISES[("lua", "gelo")]: "Water ice confirmed in the sample from the shadowed crater.",
    ANALISES[("marte", "gelo")]: "Water ice confirmed in the sample from under the ground.",
    LOCAIS["amostra"][2]: "You analysed a rock sample from the surface.",
    LOCAIS["baliza"][2]: "You switched on the beacon and confirmed the position of the base.",
    LOCAIS["cratera"][2]: "You recorded the ground marks without entering the depression.",
    # ── contas ──
    "Usa 3 a 20 letras, números ou _, começando por uma letra ou número.": "Use 3 to 20 letters, numbers or _, starting with a letter or number.",
    "Aguarda antes de tentar novamente.": "Wait before trying again.",
    "Muitas tentativas. Tenta novamente mais tarde.": "Too many attempts. Try again later.",
    "Indica um nome de astronauta com 1 a 24 caracteres.": "Enter an astronaut name with 1 to 24 characters.",
    "Indica uma idade entre 8 e 120 anos.": "Enter an age between 8 and 120.",
    "Indica o teu nome e a idade para continuar.": "Enter your name and age to continue.",
    "Este nickname já está em uso. Escolhe outro.": "That nickname is taken. Choose another one.",
    "A tua conta já tem um nickname.": "Your account already has a nickname.",
    # ── pedidos ──
    "Operação desconhecida.": "Unknown operation.",
    "O pedido veio de outra origem.": "The request came from another origin.",
    "Envia um pedido em JSON.": "Send a JSON request.",
    "Identificador de mensagem inválido.": "Invalid message identifier.",
    "Endereço desconhecido.": "Unknown address.",
    "Pedido demasiado grande.": "Request too large.",
    "O pedido deve conter um objecto JSON.": "The request must contain a JSON object.",
    "O código de partida é inválido.": "The mission code is invalid.",
    "O pedido deve conter JSON válido.": "The request must contain valid JSON.",
    "Escolhe um único cursor de mensagens.": "Choose a single message cursor.",
    "Usa um código privado de convite.": "Use a private invite code.",
    "A base de dados está temporariamente indisponível.": "The database is temporarily unavailable.",
    "Os valores do pedido são inválidos.": "The values of the request are invalid.",
    "A chave da missão é inválida.": "The mission key is invalid.",
    "O destino é inválido.": "The destination is invalid.",
    "O resultado é inválido.": "The result is invalid.",
    "As estrelas não correspondem ao resultado.": "The stars do not match the result.",
    "Os recursos são inválidos.": "The resources are invalid.",
    "As EVAs são inválidas.": "The EVAs are invalid.",
    # ── partidas ──
    "Só os membros da equipa têm acesso a esta partida.": "Only team members can open this mission.",
    "Escreve um nome de astronauta com 1 a 24 caracteres.": "Write an astronaut name with 1 to 24 characters.",
    "Escolhe Cadete, Piloto ou Comandante.": "Choose Cadet, Pilot or Commander.",
    "Só o anfitrião pode convidar no hangar.": "Only the host can invite, in the lobby.",
    "O lançamento já aconteceu.": "The launch has already happened.",
    "A equipa já está completa.": "The team is already full.",
    "Indica um código válido.": "Enter a valid code.",
    "O convite é obrigatório.": "The invite is required.",
    "A chave da partida anterior é inválida.": "The key of the earlier mission is invalid.",
    "A partida não foi encontrada.": "Mission not found.",
    "Identificador da mensagem inválido.": "Invalid message identifier.",
    "Tipo de mensagem desconhecido.": "Unknown message type.",
    "Formato de áudio inválido.": "Invalid audio format.",
    "A gravação é demasiado grande.": "The recording is too large.",
    "A gravação é inválida.": "The recording is invalid.",
    "Escreve uma resposta com até 500 caracteres.": "Write an answer of up to 500 characters.",
    "O desafio mudou. Consulta a partida actualizada.": "The challenge changed. Check the updated mission.",
    "Usa as opções disponíveis para o teu nível.": "Use the options available for your level.",
    "Retira contactos pessoais e links antes de interpretar o plano.": "Remove personal contacts and links before sending the plan.",
    "Comando ou revisão inválidos.": "Invalid command or revision.",
    "Entra numa partida primeiro.": "Join a mission first.",
    "O código expirou ou já foi utilizado.": "The code expired or was already used.",
    "Esta equipa não está disponível.": "This team is not available.",
    "Partilha o código com o teu colega.": "Share the code with your crewmate.",
    "Convite inválido, usado ou expirado.": "Invalid, used or expired invite.",
    "Esta conta já pertence a esta equipa.": "This account already belongs to this team.",
    "Não há um colega nesta partida.": "There is no crewmate in this mission.",
    "Escolhe um motivo válido.": "Choose a valid reason.",
    "Usa as opções de conversa autorizadas para a equipa.": "Use the chat options allowed for the team.",
    "Espera um pouco antes de enviares outra mensagem.": "Wait a little before sending another message.",
    "Escolhe uma frase disponível.": "Choose an available phrase.",
    "Escreve uma mensagem com até 500 caracteres.": "Write a message of up to 500 characters.",
    "Retira contactos pessoais e links da mensagem.": "Remove personal contacts and links from the message.",
    "A equipa não tem acesso à voz.": "The team has no access to voice.",
    "A gravação não foi encontrada.": "The recording was not found.",
    "A partida mudou. Confirma o estado antes de repetir a acção.": "The mission changed. Check the state before repeating the action.",
    "A posição está fora do hangar.": "The position is outside the playing area.",
    "A mensagem já não está disponível.": "The message is no longer available.",
    "Este identificador já foi usado para outra mensagem.": "This identifier was already used for another message.",
    "Esta partida atingiu o limite de gravações. Podes continuar por texto.": "This mission reached the recording limit. You can carry on by text.",
    "Este identificador já foi usado para outro comando.": "This identifier was already used for another command.",
}
PERFIS_EN = {
    "lua": {"nome": "Moon", "nave": "Lunar module", "pouso": ["Plain next to the ridge", "Low area near the cargo"],
            "rota": "The ship changes trajectory, enters lunar orbit and brakes with its engines to land.",
            "referencia": "Apollo 11, a historic mission. The game profile is simplified."},
    "marte": {"nome": "Mars", "nave": "Transit habitat", "pouso": ["Landing plain", "Plain far from the cargo"],
              "rota": "The ship leaves in a launch window to meet Mars where the planet will be when it arrives.",
              "referencia": "203 days on the robotic Perseverance mission, used as a teaching reference."},
}
CARGA_EN = {"agua": "Water", "comida": "Food", "oxigenio": "Oxygen", "propulsante": "Propellant", "ferramentas": "Tools",
            "pecas": "Spare parts", "filtro": "CO₂ filter", "bateria": "Spare battery", "energia": "Power module",
            "radio": "Communications module", "habitat": "Pressurised habitat", "rover": "Rover"}
MONTAGEM_EN = {"energia": "Install power and test the battery", "radio": "Install communications and test the radio",
               "habitat": "Assemble the habitat and check the seal and life support"}
FRASES_EN = {"leituras": "Let's check the readings.", "plano": "Explain your plan.", "recursos": "Let's check the reserves.",
             "concordo": "I agree with your choice.", "duvida": "I have a doubt about that choice.",
             "espera": "I need a moment.", "ajuda": "I need help.", "obrigado": "Thanks for the help!"}
LEVES_EN = {"SERENO": "Let's confirm the readings.", "PANICO": "Critical resources are dropping. Let's protect the crew.",
            "PROTESTO": "We have an alert. Check the terminal.", "ALIVIO": "The situation is stable. We can carry on.",
            "TRISTEZA": "We lost margin. We can still recover."}
TAREFAS_EN = {"comando": "I follow the decision of the team.", "engenharia": "I check the systems and the reserves.",
              "cadete": "I follow the task on the terminal."}


def _tabela():
    t = dict(FIXAS)
    for linhas in LINHAS.values():
        for linha in linhas:
            en = catalogo_en.INCIDENTES.get(linha[0])
            if en:
                t.update(zip(linha[1:], en))
            if linha[0] in CONCEITOS and linha[0] in catalogo_en.CONCEITOS:
                t[CONCEITOS[linha[0]]] = catalogo_en.CONCEITOS[linha[0]]
    for papel, falas in FALAS.items():
        for emocao, fala in falas.items():
            t[fala] = catalogo_en.FALAS.get(papel, {}).get(emocao, fala)
    for d, p in PERFIS.items():
        for campo in ("nome", "nave", "rota", "referencia"):
            t[p[campo]] = PERFIS_EN[d][campo]
        t.update(zip(p["pouso"], PERFIS_EN[d]["pouso"]))
    t.update({CARGA[k][0]: v for k, v in CARGA_EN.items()})
    t.update({pt: MONTAGEM_EN[k] for k, pt in MONTAGEM})
    t.update({pt: FRASES_EN[k] for k, pt in _FRASES_PT.items() if k in FRASES_EN})
    t.update({pt: LEVES_EN[k] for k, pt in FALAS_LEVES.items() if k in LEVES_EN})
    t.update({pt: TAREFAS_EN[k] for k, pt in TAREFAS.items()})
    return t


TABELA = _tabela()
_ITENS = {CARGA[k][0].lower(): v.lower() for k, v in CARGA_EN.items()}
_TEMAS = {pt: catalogo_en.ROTULOS_EVA.get(k, pt) for k, pt in ROTULOS.items()}
REGRAS = [
    (re.compile(r"^Destino seleccionado: (.+)\.$"), lambda m: f"Destination selected: {TABELA.get(m[1], m[1])}."),
    (re.compile(r"^Adiaste a intervenção\. Restam (\d+) adiamentos neste incidente\.$"),
     lambda m: f"You postponed the intervention. Postponements left in this incident: {m[1]}."),
    (re.compile(r"^Avanço aprovado por (\d+) de (\d+) jogadores ligados\.$"),
     lambda m: f"Advance approved by {m[1]} of {m[2]} connected players."),
    (re.compile(r"^A reserva de (.+) está perto do consumo previsto\.$"),
     lambda m: f"The reserve of {_ITENS.get(m[1], m[1])} is close to the planned consumption."),
    (re.compile(r"^Usaste (.+) da carga\.$"), lambda m: f"You used the {_ITENS.get(m[1], m[1])} from the cargo."),
    (re.compile(r"^(.+): concluído\.$"), lambda m: f"{TABELA.get(m[1], m[1])}: done."),
    (re.compile(r"^Inspirado numa saída extraveicular real da NASA( \(\d{4}\))?: (.+)\.$"),
     lambda m: f"Inspired by a real NASA spacewalk{m[1] or ''}: {_TEMAS.get(m[2], m[2])}."),
    (re.compile(r"^O campo (.+) é inválido\.$"), lambda m: f"The field {m[1]} is invalid."),
]
_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕ])")


def frase(s):
    if s in TABELA:
        return TABELA[s]
    for padrao, f in REGRAS:
        m = padrao.match(s)
        if m:
            return f(m)
    return None


def texto(s):
    """Traduz um texto do servidor. Devolve o original quando não o reconhece (nomes, códigos, etc.)."""
    if not isinstance(s, str) or len(s) < 3:
        return s
    directo = frase(s)
    if directo is not None:
        return directo
    partes = _FRASE.split(s.strip())
    if len(partes) > 1:
        traduzidas = [frase(p) for p in partes]
        if all(p is not None for p in traduzidas):
            return " ".join(traduzidas)
    return s


# Campos que pertencem ao jogador ou a dados reais (NASA): nunca se traduzem.
INTOCAVEIS = {"nickname", "codigo", "texto", "convite", "email", "eu", "id", "jogador",
              "tripulacao_real", "proposito", "veiculo", "pais", "fonte", "chave"}


def resposta(obj, chave=None):
    """Percorre a resposta JSON e traduz todos os textos reconhecidos."""
    if isinstance(obj, dict):
        if chave == "eva" or ("proposito" in obj and "veiculo" in obj):  # registo real da NASA
            return {k: (_TEMAS.get(v, v) if k == "tema_pt" else v) for k, v in obj.items()}
        # jogador ou conta: dados pessoais. A vista da partida também tem «anfitriao», mas traz o estado.
        if "estado" not in obj and obj.keys() & {"nickname", "anfitriao", "ligado", "idade"}:
            return obj
        return {k: (v if k in INTOCAVEIS else resposta(v, k)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [resposta(v, chave) for v in obj]
    return texto(obj) if isinstance(obj, str) else obj
