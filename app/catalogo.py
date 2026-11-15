PERFIS = {
    "lua": {"nome": "Lua", "horas": 103, "nave": "Módulo lunar", "limite_kg": 1550,
            "limite_l": 2500, "pouso": ["Planície junto à crista", "Zona baixa perto da carga"],
            "rota": "A nave muda de trajectória, entra em órbita lunar e trava com motores para pousar.",
            "referencia": "Apollo 11, missão histórica. O perfil do jogo é simplificado."},
    "marte": {"nome": "Marte", "horas": 4872, "nave": "Habitat de trânsito",
              "limite_kg": 7400, "limite_l": 11500, "pouso": ["Planície de pouso", "Planície afastada da carga"],
              "rota": "A nave sai numa janela de partida para encontrar Marte onde o planeta estará quando ela chegar.",
              "referencia": "203 dias na missão robótica Perseverance, usados como referência didáctica."},
}

CARGA = {
    "agua": ("Água", 1, 1),
    "comida": ("Comida", 1, 2),
    "oxigenio": ("Oxigénio", 2, 3),
    "propulsante": ("Propulsante", 1, 2),
    "ferramentas": ("Ferramentas", 30, 48),
    "pecas": ("Peças de reserva", 20, 28),
    "filtro": ("Filtro de CO₂", 10, 15),
    "bateria": ("Bateria de reserva", 55, 70),
    "energia": ("Módulo de energia", 165, 240),
    "radio": ("Módulo de comunicações", 95, 120),
    "habitat": ("Habitat pressurizado", 570, 940),
    "rover": ("Rover", 220, 320),
}

MONTAGEM = [
    ("energia", "Instalar energia e testar a bateria"),
    ("radio", "Instalar comunicações e testar o rádio"),
    ("habitat", "Montar o habitat e verificar a vedação e o suporte de vida"),
]

# id, título, sinal, acção segura, decisão arriscada, consequência e recuperação.
LINHAS = {
    "viagem": [
        ("desvio", "Desvio da trajectória", "A previsão de chegada saiu do corredor de navegação.", "Medir e corrigir a trajectória", "Concentrar a correcção numa única manobra perto da chegada", "O desvio aumentou e gastaste parte da margem de manobra.", "Recalcular a rota e executar a correcção"),
        ("impacto", "Impacto no painel", "Um painel fornece menos energia apesar da iluminação.", "Reduzir consumos e estabilizar a energia", "Usar a bateria para manter o programa de experiências", "A bateria perdeu carga e a nave entrou em modo de reserva.", "Desligar cargas secundárias e verificar a reserva"),
        ("oxigenio", "Perda de oxigénio", "A pressão da reserva está a cair.", "Isolar a fuga e activar a reserva", "Compensar a queda de pressão aumentando o fornecimento", "Perdeste parte do oxigénio de reserva.", "Isolar o compartimento e transferir a tripulação para o abrigo"),
        ("co2", "Subida de CO₂", "O dióxido de carbono sobe com pressão estável.", "Inspeccionar a remoção de CO₂", "Elevar o fluxo de oxigénio para diluir o dióxido de carbono", "A filtragem continuou degradada e gastaste oxigénio.", "Usar o filtro compatível ou isolar a zona e testar o sistema"),
        ("radiacao", "Alerta de radiação", "Os sensores detectam um evento de partículas solares.", "Levar a tripulação ao abrigo blindado", "Concluir a recolha antes de abrigar a equipa", "A exposição acumulada aumentou.", "Ir para o abrigo e confirmar uma leitura segura"),
        ("atraso", "Contacto interrompido", "O painel avisa que a resposta da Terra demora.", "Executar o procedimento local autorizado", "Suspender a intervenção até chegar a validação da Terra", "O atraso reduziu a margem de resposta.", "Aplicar o procedimento local e enviar uma mensagem de teste"),
        ("sensor_estrelas", "Sensor de estrelas sem referência",
         "Os sensores de orientação discordam e a nave não sabe exactamente para onde aponta.",
         "Comparar o sensor de estrelas com a referência do Sol",
         "Usar a orientação calculada antes da falha e corrigir depois",
         "A manobra começou mal orientada e gastou propulsante.",
         "Cancelar o impulso, verificar a orientação e realinhar a nave"),
        ("refrigeracao", "Equipamento a sobreaquecer",
         "A temperatura de um módulo sobe apesar de o resto da nave estar estável.",
         "Reduzir a carga do módulo e inspeccionar o arrefecimento",
         "Elevar a potência para concluir mais depressa o ciclo do módulo",
         "O módulo entrou em protecção térmica e consumiu energia da reserva.",
         "Manter as cargas críticas e testar o arrefecimento antes de religar"),
        ("reciclagem_agua", "Água reciclada por verificar",
         "A água do circuito de recuperação ainda não passou no controlo de qualidade.",
         "Separar o lote e usar a reserva de água verificada",
         "Distribuir o lote tratado e recolher uma amostra em paralelo",
         "O lote ficou indisponível e a reserva útil caiu.",
         "Isolar a água por verificar e repetir o tratamento e o controlo"),
    ],
    "lua": [
        ("rochas", "Rochas no pouso", "O ponto nominal tem rochas na área de descida.", "Confirmar uma alternativa alcançável", "Reduzir a velocidade de descida sobre o ponto nominal", "A descida foi interrompida e consumiu propulsante.", "Recalcular e verificar a zona alternativa"),
        ("sombra", "Sombra nos painéis", "O relevo vai tapar a luz que chega aos painéis.", "Poupar energia para aquecimento e suporte de vida", "Dar prioridade à oficina e ao laboratório para concluir os trabalhos", "A autonomia caiu e a oficina desligou.", "Estabilizar a energia e reiniciar cargas por prioridade"),
        ("relevo", "Rádio bloqueado pelo relevo", "Perdeste o sinal atrás de uma elevação.", "Voltar ao último ponto com sinal", "Subir pela rota mais curta até ao próximo ponto de contacto previsto", "A distância até ao último contacto aumentou.", "Recuperar a ligação e confirmar a autonomia de regresso"),
        ("rover_lua", "Poeira levantada pelo rover", "Um guarda-lamas danificado lança poeira.", "Parar e verificar o guarda-lamas", "Reduzir a velocidade do rover e terminar a travessia", "A poeira acumulou-se e a mobilidade ficou limitada.", "Limpar o rover e instalar ou improvisar protecção"),
        ("junta", "Poeira na junta", "Uma ligação do equipamento custa a fechar.", "Limpar e testar a junta", "Apertar a ligação para verificar se o contacto melhora", "A ligação ficou fora de serviço.", "Inspeccionar e substituir ou reparar a ligação"),
        ("gelo_lua", "Gelo numa zona sombreada", "Uma zona promissora exige atravessar terreno frio e inclinado.", "Prospectar com margem de regresso", "Usar a bateria de regresso para alcançar primeiro a zona de gelo", "A exploração excedeu a margem da bateria.", "Recuar para uma rota curta e verificar a margem de regresso"),
        ("poeira_antecamara", "Poeira na antecâmara",
         "A equipa traz regolito nas botas e nos trajes depois da saída.",
         "Limpar os trajes na antecâmara antes de entrar",
         "Concentrar a limpeza no habitat, onde há mais ferramentas",
         "A poeira entrou com o equipamento e reduziu a capacidade de operação.",
         "Isolar o material empoeirado, limpar e testar as ligações"),
        ("oscilacao_termica", "Mudança térmica na crista",
         "O Sol baixa no horizonte e um instrumento na sombra começa a arrefecer.",
         "Reservar energia para o instrumento crítico",
         "Dividir a energia disponível entre as experiências em curso",
         "Faltou energia para estabilizar o instrumento.",
         "Desligar as cargas secundárias e recuperar a temperatura do instrumento"),
        ("retransmissor", "Zona sem linha de visão",
         "A equipa precisa de comunicar de um local escondido atrás do relevo.",
         "Programar contacto através de um retransmissor",
         "Combinar horários fixos para transmitir directamente à base",
         "A equipa perdeu a janela de contacto e a margem de resposta diminuiu.",
         "Recuar para um ponto com sinal e agendar a próxima passagem do retransmissor"),
    ],
    "marte": [
        ("pouso_marte", "Pouso longe da carga", "O ponto mais seguro fica afastado dos módulos.", "Confirmar uma rota até à carga", "Mover a carga primeiro e marcar a rota durante o percurso", "A equipa perdeu tempo e a carga ficou fora de alcance.", "Marcar uma rota segura e verificar a margem de energia"),
        ("tempestade", "Tempestade de poeira", "A produção dos painéis solares está a cair.", "Manter apenas os sistemas essenciais", "Dar prioridade à oficina e ao laboratório para concluir os trabalhos", "A bateria ficou abaixo da margem e a oficina desligou.", "Desligar as cargas secundárias e estabilizar a bateria"),
        ("frio", "Noite fria", "A previsão indica energia insuficiente para aquecer.", "Reservar energia para o aquecimento", "Concluir a experiência e repor a bateria depois do amanhecer", "Um sensor reiniciou durante a noite.", "Restabelecer o aquecimento e verificar o sensor"),
        ("conjuncao", "Janela de rádio limitada", "A ligação à Terra vai ficar limitada pela posição do Sol.", "Preparar tarefas e procedimentos locais", "Reservar as decisões para a próxima oportunidade de contacto", "Uma tarefa ficou sem resposta do controlo de missão.", "Executar o procedimento local e guardar a telemetria"),
        ("gelo_marte", "Gelo provável", "O mapa indica uma área promissora, ainda sem água disponível.", "Confirmar uma amostra e usar água transportada", "Usar a reserva no percurso para iniciar já a extracção", "A reserva de água ficou abaixo do planeado.", "Rever o consumo e confirmar a extracção e o tratamento"),
        ("roda_marte", "Desgaste das rodas", "As rodas mostram desgaste em terreno rochoso.", "Escolher um trajecto que poupe as rodas", "Escolher o trajecto curto para reduzir o tempo de utilização do rover", "O rover perdeu capacidade e deixou carga fora de alcance.", "Reduzir a carga e recuperar a mobilidade"),
        ("painel_marte", "Poeira depositada no painel",
         "O céu está claro, mas o painel continua a produzir pouco após a tempestade.",
         "Verificar a deposição no painel e activar a gestão de energia",
         "Retomar as operações previstas com a luz disponível",
         "O consumo ultrapassou a geração e a reserva caiu.",
         "Poupar energia, inspeccionar o painel e recuperar a geração útil"),
        ("amostra_marte", "Amostras misturadas",
         "Duas amostras de locais diferentes chegaram juntas à bancada.",
         "Isolar os recipientes e confirmar o registo de origem",
         "Preparar uma amostra conjunta para acelerar a análise",
         "Perdeu-se a referência de origem e será preciso recolher outra amostra.",
         "Separar os recipientes, registar o incidente e recolher uma nova amostra identificada"),
        ("abrigo_marte", "Saída durante alerta solar",
         "Um alerta de radiação chega quando a equipa se prepara para sair.",
         "Adiar a saída e proteger a equipa no abrigo",
         "Limitar a saída às tarefas de curta duração",
         "A exposição acumulada aumentou enquanto a equipa estava fora.",
         "Voltar ao abrigo e confirmar as leituras antes de remarcar a saída"),
    ],
}

def carga_minima(destino):
    dias = PERFIS[destino]["horas"] / 24
    return {"agua": int(dias * 6) + 14, "comida": int(dias * 3) + 7,
            "oxigenio": int(dias * 3) + 7, "propulsante": 140,
            "ferramentas": 1, "energia": 1, "radio": 1, "habitat": 1}

from .privacidade import FRASES as FRASES_PT  # noqa: E402
from . import superficie  # noqa: E402


def catalogo():
    return {
        "destinos": {d: {**p, "minimo": carga_minima(d)} for d, p in PERFIS.items()},
        "carga": {k: {"nome": n, "kg": m, "litros": v} for k, (n, m, v) in CARGA.items()},
        "montagem": MONTAGEM,
        "superficie": superficie.catalogo(),
    }

