import os
import re
from time import time

from .db import ligacao

IDADE_CONSENTIMENTO = 15
RETENCAO_MENSAGENS = 7 * 86400
RETENCAO_VOZ = 86400
CONVERSA_LIVRE = os.getenv("ASTRO_CONVERSA_LIVRE", "0") == "1"
FRASES = {
    "leituras": "Vamos conferir as leituras.",
    "plano": "Explica o teu plano.",
    "recursos": "Vamos verificar as reservas.",
    "concordo": "Concordo com a tua escolha.",
    "duvida": "Tenho uma dúvida sobre essa escolha.",
    "espera": "Preciso de um momento.",
    "ajuda": "Preciso de ajuda.",
    "obrigado": "Obrigado pela ajuda!",
}
CONTACTO = re.compile(r"https?://|www\.|\b[\w.+-]+\s*@\s*[\w.-]+|(?:\d[\s()+.-]*){7,}|\b(?:whatsapp|telegram|discord|instagram)\b", re.I)


def social_autorizado(conta):
    """Entrada livre: qualquer jogador pode jogar em equipa com código de sala e convite."""
    return True


def exigir_social(conta):
    return None


def bloqueado(conn, a, b):
    return bool(conn.execute(
        "SELECT 1 FROM bloqueios WHERE (autor=%s AND alvo=%s) OR (autor=%s AND alvo=%s)", (a, b, b, a),
    ).fetchone())


def limpar(dsn):
    agora = int(time())
    with ligacao(dsn) as conn:
        conn.execute("DELETE FROM mensagens WHERE enviada_em <= %s OR (audio IS NOT NULL AND enviada_em <= %s)",
                     (agora - RETENCAO_MENSAGENS, agora - RETENCAO_VOZ))
        conn.execute("DELETE FROM comandos WHERE criado_em < now() - interval '7 days'")
        conn.execute("DELETE FROM limites_pedidos WHERE expira_em <= %s", (agora,))
        conn.execute("DELETE FROM convites WHERE expira_em <= %s", (agora,))
        conn.execute("DELETE FROM denuncias WHERE criada_em < now() - interval '90 days' AND revista_em IS NOT NULL")
