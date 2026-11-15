"""Tabelas da rede R1 definidas no guia da equipa, secção 11."""
import math

PLASTIC_POSTS = {"CONFIANCA": 1.0, "CALMA": 1.0, "STRESS": -1.0, "DESANIMO": -1.0}

SENSORY_SPEC = {
    #                    n   rate    d       tau_rec
    "O2_BAIXO":        (6,  80.0, 0.0,      1.0),    # oxigénio baixo (não habitua)
    "ENERGIA_BAIXA":   (6,  80.0, 0.0,      1.0),    # energia baixa
    "AGUA_BAIXA":      (6,  80.0, 0.0,      1.0),    # água baixa
    "TEMPESTADE":      (6,  80.0, 0.0002, 600.0),    # evento activo (habitua devagar)
    "ACCAO_BOA":       (6,  80.0, 0.0,      1.0),    # o jogador fez uma boa acção
    "ACCAO_ARRISCADA": (6,  80.0, 0.0,      1.0),    # o jogador fez uma acção arriscada
    "NAO_PERCEBI":     (6,  60.0, 0.0,      1.0),    # a compreensão não percebeu a resposta
    "SUCESSO_RECENTE": (6,  60.0, 0.0,      1.0),    # boas decisões seguidas
    "BASE_ESTAVEL":    (6,  60.0, 0.0,      1.0),    # tudo dentro dos limites
}

INTER_SPEC = [
    ("ALERTA",    "exc", 16,  20.0, 0.030, 1.5, (0.32, 0.10)),
    ("STRESS",    "exc", 12, 150.0, 0.010, 3.0, (0.32, 0.35)),
    ("CALMA",     "exc", 12, 300.0, 0.010, 3.0, (0.32, 0.60)),
    ("CONFIANCA", "exc", 12, 200.0, 0.020, 2.0, (0.58, 0.28)),
    ("DESANIMO",  "exc", 12, 400.0, 0.010, 4.0, (0.58, 0.58)),
    ("INIBICAO",  "inh", 20,  10.0, 0.000, 1.0, (0.45, 0.92)),
]

# MOTORES (a reacção da tripulação): nome, n, tau_m (ms), adapt_b, adapt_tau (s)
MOTOR_SPEC = [
    ("PANICO",   10, 25.0, 0.060, 1.0),
    ("ALIVIO",   10, 50.0, 0.040, 3.0),
    ("PROTESTO", 10, 50.0, 0.030, 4.0),
    ("TRISTEZA", 10, 80.0, 0.020, 5.0),
    ("SERENO",   10, 60.0, 0.030, 4.0),
]

# CONEXÕES: (pré, pós, peso, densidade)
CONNECTIONS = [
    # sensores -> interneurónios
    ("O2_BAIXO",        "ALERTA",    0.14, 0.6),
    ("O2_BAIXO",        "STRESS",    0.06, 0.6),
    ("ENERGIA_BAIXA",   "ALERTA",    0.06, 0.6),
    ("ENERGIA_BAIXA",   "STRESS",    0.10, 0.6),
    ("AGUA_BAIXA",      "ALERTA",    0.05, 0.6),
    ("AGUA_BAIXA",      "STRESS",    0.08, 0.6),
    ("TEMPESTADE",      "ALERTA",    0.08, 0.6),
    ("TEMPESTADE",      "STRESS",    0.05, 0.6),
    ("ACCAO_BOA",       "CONFIANCA", 0.12, 0.6),
    ("ACCAO_BOA",       "CALMA",     0.05, 0.6),
    ("ACCAO_ARRISCADA", "STRESS",    0.14, 0.6),
    ("ACCAO_ARRISCADA", "ALERTA",    0.04, 0.6),
    ("NAO_PERCEBI",     "DESANIMO",  0.10, 0.6),
    ("SUCESSO_RECENTE", "CONFIANCA", 0.08, 0.6),
    ("SUCESSO_RECENTE", "CALMA",     0.04, 0.6),
    ("BASE_ESTAVEL",    "CALMA",     0.12, 0.6),

    # interneurónios entre si
    ("ALERTA",    "INIBICAO",  0.10, 0.5),
    ("STRESS",    "INIBICAO",  0.04, 0.5),
    ("CONFIANCA", "INIBICAO",  0.06, 0.5),
    ("CALMA",     "STRESS",   -0.06, 0.5),
    ("CALMA",     "ALERTA",   -0.06, 0.5),
    ("STRESS",    "CALMA",    -0.05, 0.5),
    ("STRESS",    "CONFIANCA", -0.05, 0.5),
    ("CONFIANCA", "STRESS",   -0.05, 0.5),
    ("CONFIANCA", "DESANIMO", -0.05, 0.5),
    ("DESANIMO",  "CONFIANCA", -0.06, 0.5),
    ("INIBICAO",  "ALERTA",   -0.04, 0.5),
    ("INIBICAO",  "STRESS",   -0.03, 0.5),
    ("INIBICAO",  "CONFIANCA", -0.03, 0.5),

    # interneurónios -> motores
    ("ALERTA",    "PANICO",    0.50, 0.6),
    ("STRESS",    "PANICO",    0.15, 0.6),
    ("STRESS",    "PROTESTO",  0.55, 0.6),
    ("DESANIMO",  "TRISTEZA",  0.45, 0.6),
    ("CONFIANCA", "ALIVIO",    0.70, 0.6),
    ("CALMA",     "SERENO",    0.50, 0.6),
    ("INIBICAO",  "PANICO",   -0.08, 0.5),
    ("INIBICAO",  "ALIVIO",   -0.08, 0.5),
    ("INIBICAO",  "PROTESTO", -0.04, 0.5),
    ("INIBICAO",  "SERENO",   -0.08, 0.5),
]

DECISION_MOTORS = set()        # todos os motores são "expressão" e competem entre si
LATERAL_INHIBITION = 0.05      # cada motor inibe os outros
PANICO_INHIBITION = 0.10       # o pânico inibe mais forte

T_REF = 3                      # período refratário (passos de 1 ms)
NOISE_SIGMA = 0.025
READ_TAU = 0.5                 # s: suavização da taxa motora
TRACE_DECAY = math.exp(-1.0 / 120.0)
RASTER_BIN_MS = 10             # raster do monitor: uma coluna a cada 10 ms
RASTER_BINS = 300              # 3 s de história
