"""O cérebro da tripulação: codificador (estado -> canais), rede LIF e plano B."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Reaccao:
    """O que a tripulação 'sente' neste turno."""
    emocao: str                     # PANICO, ALIVIO, PROTESTO, TRISTEZA, SERENO ou NEUTRO
    intensidade: float              # 0 a 1
    taxas: dict = field(default_factory=dict)     # Hz de cada motor (para depuração)


class Codificador:
    """Traduz o estado da base nos números 0..1 que os sensores da rede recebem."""

    LIMIAR_BAIXO = 0.6              # acima disto o recurso não preocupa
    CANAIS = {"oxigenio": "O2_BAIXO", "energia": "ENERGIA_BAIXA", "agua": "AGUA_BAIXA"}

    def codificar(self, base, accoes, nao_percebi: bool = False, sucesso_recente: bool = False):
        canais = {}
        pior = 0.0
        for nome, canal in self.CANAIS.items():
            recurso = base.recursos.get(nome)
            if recurso is None:
                continue
            nivel = self._rampa(recurso.valor)
            canais[canal] = nivel
            pior = max(pior, nivel)

        tempestade = 1.0 if base.evento else 0.0
        canais["TEMPESTADE"] = tempestade
        canais["ACCAO_BOA"] = 1.0 if any(a.boa for a in accoes) else 0.0
        canais["ACCAO_ARRISCADA"] = 1.0 if any(not a.boa for a in accoes) else 0.0
        canais["NAO_PERCEBI"] = 1.0 if nao_percebi else 0.0          # a compreensão devolveu «nenhum»
        canais["SUCESSO_RECENTE"] = 1.0 if sucesso_recente else 0.0  # boas decisões seguidas
        canais["BASE_ESTAVEL"] = max(0.0, 1.0 - max(pior, 0.5 * tempestade))
        return canais

    def _rampa(self, valor):
        """1.0 quando o recurso está vazio, 0.0 quando está acima do limiar."""
        return max(0.0, min(1.0, (self.LIMIAR_BAIXO - valor) / self.LIMIAR_BAIXO))


class Cerebro(Protocol):
    """O 'contrato': qualquer cérebro tem de saber pensar(canais) -> Reaccao."""
    def pensar(self, canais: dict) -> Reaccao: ...


class CerebroLIF:
    """Instância da rede LIF R1 em app/cerebro/rede.py."""

    def __init__(self, temperamento=None, semente=None, segundos_por_turno=3.0):
        from app.cerebro.rede import LIFBrain, MotorDecoder      # import tardio: sem rede.py o plano B funciona
        self._rede = LIFBrain(temperament=temperamento, noise_seed=semente)
        self._decoder = MotorDecoder()
        self._passos = int(segundos_por_turno * 10)   # passos de 100 ms
        self._tempo = 0.0

    def pensar(self, canais):
        emocao = None
        for _ in range(self._passos):
            self._rede.stimulate(canais)
            self._rede.step(100)
            self._tempo += 0.1
            emocao, _ = self._decoder.update(self._rede.motor_activity(), now=self._tempo)
        taxas = self._rede.motor_activity()
        if emocao is None:
            return Reaccao("NEUTRO", 0.0, taxas)
        return Reaccao(emocao, min(1.0, taxas[emocao] / 20.0), taxas)


class CerebroNulo:
    """Plano B: um 'cérebro' que não sente nada. O jogo continua só com regras."""

    def pensar(self, canais):
        return Reaccao("NEUTRO", 0.0)
