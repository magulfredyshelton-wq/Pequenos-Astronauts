"""Da reacção da rede à tripulação que aparece no estado do turno (campo `tripulacao`).
As falas são modelos fixos (nunca geradas por LLM) e sem números: factos e valores vêm das fichas."""
from app.cerebro.cerebro import Reaccao

FALAS = {
    "COMANDO": {
        "PANICO": "Atenção, equipa! Temos de agir já!",
        "PROTESTO": "Isto não está a correr bem. Temos de mudar o plano.",
        "ALIVIO": "Boa decisão! Já podemos passar à próxima tarefa.",
        "TRISTEZA": "Vamos fazer uma pausa e rever o plano.",
        "SERENO": "Tudo calmo. Vamos manter a atenção.",
        "NEUTRO": "À espera da tua próxima decisão.",
    },
    "ENGENHARIA": {
        "PANICO": "Temos um alerta nos sistemas. Vamos verificar as leituras.",
        "PROTESTO": "Vamos comparar as leituras antes de escolher o próximo passo.",
        "ALIVIO": "Os cálculos melhoraram. Esta decisão ajudou muito.",
        "TRISTEZA": "Vamos confirmar o que ainda pode ser recuperado.",
        "SERENO": "Os sistemas estão estáveis por agora.",
        "NEUTRO": "A acompanhar os sistemas.",
    },
    "OPERACOES": {
        "PANICO": "Estou preocupado. Vamos proteger a equipa e seguir o plano.",
        "PROTESTO": "Não gosto desta decisão. Vamos pensar melhor.",
        "ALIVIO": "Ufa! Já respiro melhor.",
        "TRISTEZA": "Precisamos de voltar a trabalhar em equipa.",
        "SERENO": "Estamos bem. Continuamos juntos.",
        "NEUTRO": "Pronto para ajudar.",
    },
}
FALA_PADRAO = "À espera da tua próxima decisão."


def para_estado(reaccoes: dict[str, Reaccao]) -> list[dict]:
    """Lista para o estado do turno: [{"papel", "emocao", "intensidade", "fala"}]."""
    return [
        {
            "papel": papel,
            "emocao": r.emocao,
            "intensidade": round(r.intensidade, 2),
            "fala": FALAS.get(papel, {}).get(r.emocao, FALA_PADRAO),
        }
        for papel, r in reaccoes.items()
    ]
