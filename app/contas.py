from hashlib import sha256
import os
import re
import secrets
from time import time
from urllib.parse import urlsplit
from uuid import uuid4

from psycopg.errors import UniqueViolation

from .config import BD
from .db import ligacao, transaccao
from .erros import Erro

# Entrada livre: o jogador diz só o nome e a idade. Não há email, palavra-passe nem confirmação.
# O cookie de sessão serve apenas para o servidor saber quem é quem dentro da sala.
PUBLICO = os.getenv("ASTRO_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
DOMINIO = urlsplit(PUBLICO)
COOKIE = "astro_sessao"
DURACAO_SESSAO = 7 * 86400
IDADE_MINIMA, IDADE_MAXIMA = 8, 120
CODIGO = re.compile(r"[A-Za-z0-9_-]{43}")
NICKNAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_]{2,19}")


def hash_(valor):
    return sha256(valor.encode("utf-8")).hexdigest()


def validar_configuracao():
    if (DOMINIO.scheme not in ("http", "https") or not DOMINIO.hostname or DOMINIO.path
            or DOMINIO.query or DOMINIO.fragment or DOMINIO.username or DOMINIO.password):
        raise RuntimeError("ASTRO_PUBLIC_URL deve ser apenas a origem do jogo.")


def normalizar_nickname(nickname):
    if isinstance(nickname, str):
        nickname = nickname.strip().removeprefix("@")
        if NICKNAME.fullmatch(nickname):
            return nickname.lower()
    raise Erro(400, "Usa 3 a 20 letras, números ou _, começando por uma letra ou número.")


class Limites:
    def __init__(self, bd):
        self.bd = bd

    def verificar(self, chave, maximo, segundos):
        agora = int(time())
        janela = agora // segundos
        with ligacao(self.bd) as conn:
            fila = conn.execute(
                "INSERT INTO limites_pedidos VALUES (%s, %s, %s, 1) "
                "ON CONFLICT (chave, janela) DO UPDATE SET total = limites_pedidos.total + 1 "
                "WHERE limites_pedidos.total < %s RETURNING total",
                (hash_(repr(chave)), janela, (janela + 1) * segundos, maximo),
            ).fetchone()
        if not fila:
            raise Erro(429, "Muitas tentativas. Tenta novamente mais tarde.")


class Contas:
    def __init__(self, bd=BD):
        self.bd = bd
        self.limites = Limites(bd)

    def entrar(self, nome, idade, ip):
        """Entrada livre: cria o jogador com nome e idade e abre a sessão."""
        self.limites.verificar(("entrar", ip), 300, 3600)
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 24 or not nome.strip().isprintable():
            raise Erro(400, "Indica um nome de astronauta com 1 a 24 caracteres.")
        if type(idade) is not int or not IDADE_MINIMA <= idade <= IDADE_MAXIMA:
            raise Erro(400, "Indica uma idade entre 8 e 120 anos.")
        token = secrets.token_urlsafe(32)
        agora = int(time())
        with ligacao(self.bd) as conn, transaccao(conn):
            conn.execute("DELETE FROM sessoes_conta WHERE expira_em <= %s", (agora,))
            conta = conn.execute(
                "INSERT INTO contas(id, nome, idade, confirmada_em) VALUES (%s, %s, %s, %s) RETURNING *",
                (uuid4().hex, nome.strip(), idade, agora),
            ).fetchone()
            conn.execute("INSERT INTO sessoes_conta VALUES (%s, %s, %s)",
                         (hash_(token), conta["id"], agora + DURACAO_SESSAO))
        return self.perfil(conta), token

    def verificar(self, token):
        if not CODIGO.fullmatch(token):
            raise Erro(401, "Indica o teu nome e a idade para continuar.")
        with ligacao(self.bd) as conn:
            conta = conn.execute(
                "SELECT c.* FROM contas c JOIN sessoes_conta s ON s.conta = c.id "
                "WHERE s.token_hash = %s AND s.expira_em > %s", (hash_(token), int(time()))
            ).fetchone()
        if conta is None:
            raise Erro(401, "Indica o teu nome e a idade para continuar.")
        return self.perfil(conta)

    def definir_nickname(self, perfil, nickname):
        nickname = normalizar_nickname(nickname)
        try:
            with ligacao(self.bd) as conn, transaccao(conn):
                conta = conn.execute(
                    "SELECT * FROM contas WHERE id = %s FOR NO KEY UPDATE", (perfil["id"],),
                ).fetchone()
                actual = conta["nickname"]
                if actual == nickname:
                    return self.perfil(conta)
                if actual is not None:
                    raise Erro(409, "A tua conta já tem um nickname.")
                conn.execute("UPDATE contas SET nickname = %s WHERE id = %s", (nickname, perfil["id"]))
        except UniqueViolation:
            raise Erro(409, "Este nickname já está em uso. Escolhe outro.") from None
        return {**perfil, "nickname": nickname}

    def sair(self, token):
        if CODIGO.fullmatch(token):
            with ligacao(self.bd) as conn:
                conn.execute("DELETE FROM sessoes_conta WHERE token_hash = %s", (hash_(token),))

    @staticmethod
    def perfil(conta):
        idade = conta["idade"]
        nivel = "cadete" if idade <= 11 else "piloto" if idade <= 14 else "comandante"
        return {"id": conta["id"], "nome": conta["nome"], "idade": idade,
                "nivel": nivel, "nickname": conta["nickname"]}
