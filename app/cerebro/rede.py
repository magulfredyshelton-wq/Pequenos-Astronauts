# Rede neural da tripulação: neurónios LIF (leaky integrate-and-fire) com sensores de Poisson.
#
# IMPLEMENTAÇÃO INDEPENDENTE, escrita a partir da especificação do GUIA_DO_PROJECTO (secção 11):
# arquitectura sensores -> interneurónios -> motores, tabelas em tabelas_missao.py e a API
# LIFBrain / MotorDecoder. NÃO contém código do Pestinha (nervous_system.py).
# Licença: GPL-3.0, por decisão da equipa (guia, secção 16). Origem das tabelas: ver README.
#
# Não implementado (Extra no guia): aprendizagem de pesos (PLASTIC_POSTS) e persistência do estado.
import math

import numpy as np

from app.cerebro.tabelas_missao import (
    CONNECTIONS, INTER_SPEC, LATERAL_INHIBITION, MOTOR_SPEC, NOISE_SIGMA, PANICO_INHIBITION,
    PLASTIC_POSTS, READ_TAU, SENSORY_SPEC, T_REF,
)

V_TH = 1.0                  # limiar de disparo (a «borda do balde»)
SEMENTE_ESTRUTURA = 1       # estrutura por omissão: igual para todos (as diferenças vêm do temperamento e do ruído)
DENSIDADE_LATERAL = 0.7     # inibição lateral entre motores

# Ganhos globais de calibração: escalam os pesos do guia por tipo de ligação. Ajustados por busca para
# reproduzir os casos do guia (secção 11); alterar só com o teste_rede.py a correr.
GANHO_SENSOR = 2.8          # sensores -> interneurónios
GANHO_INTERNO = 3.7         # interneurónios -> interneurónios (excitação)
GANHO_INIBICAO = 3.7        # interneurónios -> interneurónios (inibição)
GANHO_MOTOR = 0.38          # interneurónios -> motores
GANHO_LATERAL = 0.95        # inibição lateral entre motores
GANHO_ADAPTACAO = 0.7       # multiplica o adapt_b das tabelas (força da adaptação)


class LIFBrain:
    """Rede de 3 camadas. `seed` fixa a estrutura (quem liga a quem); `noise_seed` fixa o ruído
    (None = ruído diferente de cada vez). `temperament` multiplica as sinapses dos sensores para
    os interneurónios indicados (ex.: {"STRESS": 0.7} = reage 30% menos ao stress)."""

    def __init__(self, seed=None, temperament=None, noise_seed=None):
        self.rng = np.random.default_rng(noise_seed)                       # None = ruído sempre diferente
        estrutura = np.random.default_rng(SEMENTE_ESTRUTURA if seed is None else seed)
        self.temperament = dict(temperament or {})

        # --- populações: sensores, interneurónios, motores (por esta ordem) ---
        self.pops = {}                       # nome -> (início, fim)
        n = 0
        for nome, spec in SENSORY_SPEC.items():
            self.pops[nome] = (n, n + spec[0]); n += spec[0]
        self.n_sensores = n
        for spec in INTER_SPEC:
            self.pops[spec[0]] = (n, n + spec[2]); n += spec[2]
        self.n_inter_fim = n
        self.motores = [m[0] for m in MOTOR_SPEC]
        for spec in MOTOR_SPEC:
            self.pops[spec[0]] = (n, n + spec[1]); n += spec[1]
        self.n = n

        for nome, ganho in self.temperament.items():
            if nome not in self.pops:
                raise KeyError(f"temperamento: população desconhecida {nome!r}")

        # --- parâmetros de cada neurónio LIF (inter + motores) ---
        nl = self.n - self.n_sensores
        tau_m = np.empty(nl); adapt_b = np.empty(nl); adapt_tau = np.empty(nl)
        for spec in INTER_SPEC:
            a, b = self.pops[spec[0]]
            tau_m[a - self.n_sensores:b - self.n_sensores] = spec[3]
            adapt_b[a - self.n_sensores:b - self.n_sensores] = spec[4]
            adapt_tau[a - self.n_sensores:b - self.n_sensores] = spec[5]
        for spec in MOTOR_SPEC:
            a, b = self.pops[spec[0]]
            tau_m[a - self.n_sensores:b - self.n_sensores] = spec[2]
            adapt_b[a - self.n_sensores:b - self.n_sensores] = spec[3]
            adapt_tau[a - self.n_sensores:b - self.n_sensores] = spec[4]
        self._fuga = 1.0 / tau_m                                  # vazamento por ms
        self._adapt_b = adapt_b * GANHO_ADAPTACAO
        self._adapt_decay = np.exp(-1.0 / (adapt_tau * 1000.0))   # decaimento da adaptação por ms

        # --- sensores: taxa máxima por neurónio, habituação (d, tau_rec) por grupo ---
        self._sens_taxa = np.empty(self.n_sensores)
        self._sens_grupo = []
        for nome, spec in SENSORY_SPEC.items():
            a, b = self.pops[nome]
            self._sens_taxa[a:b] = spec[1]
            self._sens_grupo.append((nome, a, b, spec[2], spec[3]))
        self._indice_sensor = {g[0]: i for i, g in enumerate(self._sens_grupo)}

        # --- matriz de pesos W[pós, pré] ---
        self.W = np.zeros((self.n, self.n))
        sensores = set(SENSORY_SPEC)
        inter = {s[0] for s in INTER_SPEC}
        motores = set(self.motores)
        for pre, pos, peso, dens in CONNECTIONS:
            if pre not in self.pops or pos not in self.pops:
                raise KeyError(f"ligação com população desconhecida: {pre!r} -> {pos!r}")
            if pre in sensores:
                ganho = GANHO_SENSOR * self.temperament.get(pos, 1.0)
            elif pos in motores:
                ganho = GANHO_MOTOR
            else:
                ganho = GANHO_INTERNO if peso > 0 else GANHO_INIBICAO
            self._ligar(estrutura, pre, pos, peso * ganho, dens)
        for a in self.motores:                                    # inibição lateral entre motores
            for b in self.motores:
                if a != b:
                    forca = PANICO_INHIBITION if a == "PANICO" else LATERAL_INHIBITION
                    self._ligar(estrutura, a, b, -forca * GANHO_LATERAL, DENSIDADE_LATERAL)
        self._Wl = np.ascontiguousarray(self.W[self.n_sensores:, :])
        self.n_sinapses = int(np.count_nonzero(self.W))

        # --- leitura dos motores (média por população, suavizada) ---
        self._m_ini = [self.pops[m][0] - self.n_sensores for m in self.motores]
        self._m_tam = [self.pops[m][1] - self.pops[m][0] for m in self.motores]
        self.reset()

    def _ligar(self, estrutura, pre, pos, peso, dens):
        a0, a1 = self.pops[pre]
        b0, b1 = self.pops[pos]
        mascara = estrutura.random((b1 - b0, a1 - a0)) < dens
        self.W[b0:b1, a0:a1] = mascara * peso

    # ---------------------------------------------------------------- estado
    def reset(self):
        nl = self.n - self.n_sensores
        self._v = np.zeros(nl)
        self._ath = np.zeros(nl)                     # adaptação do limiar
        self._ref = np.zeros(nl, dtype=int)          # passos de refracção que faltam
        self._spikes = np.zeros(self.n)              # disparos do passo anterior
        self._entrada = np.zeros(self.n_sensores)    # valor 0..1 de cada sensor
        self._valor_canal = np.zeros(len(self._sens_grupo))
        self._efic = np.ones(len(self._sens_grupo))  # eficácia (habituação) de cada grupo sensor
        self._taxas = np.zeros(len(self.motores))    # Hz suavizados
        self.tempo_ms = 0

    def stimulate(self, canais):
        """Define os estímulos (0..1) dos sensores. O que não for mencionado fica a 0.
        Um nome desconhecido levanta KeyError (apanha erros de escrita nos canais)."""
        valores = np.zeros(len(self._sens_grupo))
        for nome, valor in canais.items():
            if nome not in self._indice_sensor:
                raise KeyError(f"canal sensorial desconhecido: {nome!r}")
            valores[self._indice_sensor[nome]] = min(1.0, max(0.0, float(valor)))
        self._valor_canal = valores

    def step(self, ms=100):
        """Avança `ms` milissegundos (passos de 1 ms)."""
        ms = int(ms)
        if ms <= 0:
            return
        ns, nl = self.n_sensores, self.n - self.n_sensores
        # eficácia dos sensores por habituação (d: queda por ms de estímulo; tau_rec: recuperação, ms)
        taxas_sens = np.empty(ns)
        for i, (_, a, b, d, tau_rec) in enumerate(self._sens_grupo):
            taxas_sens[a:b] = self._sens_taxa[a:b] * self._valor_canal[i]
        efic = self._efic
        # disparos de Poisson e ruído de todo o bloco de uma só vez (rápido)
        efic_neuronio = np.repeat(efic, [g[2] - g[1] for g in self._sens_grupo])
        p = np.clip(taxas_sens * efic_neuronio / 1000.0, 0.0, 1.0)
        spikes_sens = (self.rng.random((ms, ns)) < p).astype(float)
        ruido = self.rng.standard_normal((ms, nl)) * NOISE_SIGMA

        v, ath, ref, spikes = self._v, self._ath, self._ref, self._spikes
        Wl, fuga, ab, ad = self._Wl, self._fuga, self._adapt_b, self._adapt_decay
        taxas = self._taxas
        alfa = 1.0 / (READ_TAU * 1000.0)
        ini = np.array(self._m_ini)
        tam = np.array(self._m_tam, dtype=float)
        tam_int = self._m_tam
        d_vec = np.array([g[3] for g in self._sens_grupo])
        rec_vec = np.array([g[4] for g in self._sens_grupo])
        usado = (self._valor_canal > 0).astype(float)
        for k in range(ms):
            corrente = Wl @ spikes
            v += -v * fuga + corrente + ruido[k]
            v[ref > 0] = 0.0                                   # período refractário
            np.maximum(ref - 1, 0, out=ref)
            disparou = v >= (V_TH + ath)
            v[disparou] = 0.0
            ref[disparou] = T_REF
            ath += ab * disparou
            ath *= ad
            spikes[:ns] = spikes_sens[k]
            spikes[ns:] = disparou
            inst = np.array([disparou[i:i + t].sum() for i, t in zip(ini, tam_int)])
            taxas += ((inst / tam) * 1000.0 - taxas) * alfa
            # habituação: cai com o uso, recupera para 1
            efic += (1.0 - efic) / np.maximum(rec_vec, 1.0) - d_vec * usado * efic
        self.tempo_ms += ms

    def motor_activity(self):
        """Taxa de disparo (Hz, suavizada) de cada motor."""
        return {m: float(t) for m, t in zip(self.motores, self._taxas)}

    def describe(self):
        return f"LIF {self.n} neurônios, {self.n_sinapses} sinapses (desenhada à mão)"


class MotorDecoder:
    """Escolhe a emoção vencedora sem «piscar»: limiar de disparo, margem sobre o 2.º, tempo mínimo
    para trocar (mais curto para PANICO) e histerese (liga a 6 Hz, só desliga abaixo de 60% disso)."""

    LIMIAR_HZ = 6.0
    HISTERESE = 0.6          # fracção do limiar abaixo da qual a emoção actual termina
    MARGEM_HZ = 1.0          # o vencedor tem de ganhar ao 2.º por esta diferença
    TEMPO_MIN_S = 0.8        # candidato novo tem de se manter este tempo
    TEMPO_MIN_URGENTE_S = 0.3

    def __init__(self):
        self.actual = None
        self._candidato = None
        self._desde = 0.0

    def update(self, atividade, now):
        """Devolve (emoção ou None, mudou?). `now` em segundos."""
        ordem = sorted(atividade.items(), key=lambda kv: kv[1], reverse=True)
        (melhor, taxa), segundo = ordem[0], (ordem[1][1] if len(ordem) > 1 else 0.0)
        candidato = None
        if taxa >= self.LIMIAR_HZ and taxa - segundo >= self.MARGEM_HZ:
            candidato = melhor
        elif self.actual is not None and atividade.get(self.actual, 0.0) >= self.LIMIAR_HZ * self.HISTERESE:
            candidato = self.actual                      # histerese: mantém enquanto ainda for forte
        if candidato != self._candidato:
            self._candidato, self._desde = candidato, now
        urgente = candidato == "PANICO"
        espera = self.TEMPO_MIN_URGENTE_S if urgente else self.TEMPO_MIN_S
        mudou = False
        if candidato != self.actual:
            if candidato is None or now - self._desde >= espera:
                if candidato is None and self.actual is not None and \
                        atividade.get(self.actual, 0.0) >= self.LIMIAR_HZ * self.HISTERESE:
                    pass
                else:
                    self.actual, mudou = candidato, True
        return self.actual, mudou
