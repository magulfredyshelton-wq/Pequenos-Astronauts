"""Os 3 NPCs: 3 instâncias do mesmo cérebro, com temperamentos e sementes diferentes."""
from app.cerebro.cerebro import Cerebro, CerebroLIF, CerebroNulo, Reaccao

# papel: (temperamento, semente). Proposta inicial, a afinar (guia, secção 11).
PERFIS = {
    "COMANDO":    ({"STRESS": 0.7, "ALERTA": 0.8}, 11),   # calmo
    "ENGENHARIA": ({"ALERTA": 1.0, "STRESS": 0.9}, 22),   # analítica
    "OPERACOES":  ({"STRESS": 1.2, "ALERTA": 1.2}, 33),   # sensível
}


class Tripulacao:
    """Junta os cérebros dos NPCs. Se um falhar, esse NPC fica NEUTRO e o jogo continua."""

    def __init__(self, cerebros: dict[str, Cerebro], modo: str = "personalizado"):
        self._cerebros = cerebros
        self.modo = modo                  # "lif", "nulo" ou "personalizado"

    @classmethod
    def lif(cls, demo: bool = False, ganho: float = 1.0) -> "Tripulacao":
        """3 CerebroLIF. Com demo=True as sementes ficam fixas (repetível); senão o ruído varia.
        `ganho` multiplica os temperamentos (ex.: 0.6 para um Cadete mais tolerante)."""
        cerebros = {
            papel: CerebroLIF(
                temperamento={k: v * ganho for k, v in temperamento.items()},
                semente=semente if demo else None,
            )
            for papel, (temperamento, semente) in PERFIS.items()
        }
        return cls(cerebros, modo="lif")

    @classmethod
    def nula(cls) -> "Tripulacao":
        """Plano B: ninguém reage, só regras."""
        return cls({papel: CerebroNulo() for papel in PERFIS}, modo="nulo")

    @classmethod
    def criar(cls, demo: bool = False, ganho: float = 1.0) -> "Tripulacao":
        """Tenta a rede; se não existir ou falhar ao arrancar, usa o plano B."""
        try:
            return cls.lif(demo=demo, ganho=ganho)
        except Exception:
            return cls.nula()

    def pensar(self, canais: dict) -> dict[str, Reaccao]:
        resultado = {}
        for papel, cerebro in self._cerebros.items():
            try:
                resultado[papel] = cerebro.pensar(canais)
            except Exception:
                resultado[papel] = Reaccao("NEUTRO", 0.0)
        return resultado
