from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from time import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.catalogo import carga_minima
from app.contas import Contas
from app.db import ligacao
from app.erros import Erro
from app.main import criar_app
from app.privacidade import limpar
from app.servico import Jogo
from teste_bd import esquema_temporario


class Online(unittest.TestCase):
    def setUp(self):
        self.bd = esquema_temporario(self)
        contas = Contas(self.bd)
        self.app = criar_app(Jogo(self.bd), contas)
        self.a, self.b = self.cliente(), self.cliente()

    def cliente(self):
        cliente = TestClient(self.app)
        cliente.__enter__()
        self.addCleanup(cliente.__exit__, None, None, None)
        return cliente

    def pedido(self, cliente, rota, dados=None, esperado=200):
        resposta = cliente.get(rota) if dados is None else cliente.post(rota, json=dados)
        self.assertEqual(resposta.status_code, esperado, resposta.text)
        return resposta.json()

    def criar_conta(self, cliente, nome, idade):
        """Entrada livre: só nome e idade. O nickname (para o ranking) continua a ser opcional."""
        self.pedido(cliente, "/api/conta/entrar", {"nome": nome, "idade": idade})
        return self.pedido(cliente, "/api/conta/nickname", {"nickname": nome})

    def equipa(self):
        jogo = self.pedido(self.a, "/api/partidas", {}, 201)
        rota = "/api/partidas/" + jogo["codigo"]
        convite = self.pedido(self.a, rota + "/convites", {}, 201)["convite"]
        return rota, {"codigo": jogo["codigo"], "convite": convite}

    def test_entrada_livre_valida_nome_e_idade(self):
        self.pedido(self.a, "/api/conta", esperado=401)
        self.pedido(self.a, "/api/conta/entrar", {"nome": "", "idade": 10}, 400)
        self.pedido(self.a, "/api/conta/entrar", {"nome": "aurora", "idade": 7}, 400)
        self.pedido(self.a, "/api/conta/entrar", {"nome": "aurora", "idade": "10"}, 400)
        perfil = self.pedido(self.a, "/api/conta/entrar", {"nome": " aurora ", "idade": 10})
        self.assertEqual((perfil["nome"], perfil["idade"], perfil["nivel"], perfil["nickname"]), ("aurora", 10, "cadete", None))
        self.assertNotIn("email", perfil)
        self.assertEqual(self.pedido(self.a, "/api/conta")["id"], perfil["id"])
        for rota in ("pedir-confirmacao", "confirmar", "consentimento", "autorizar"):
            self.pedido(self.a, "/api/conta/" + rota, {}, 404)
        self.pedido(self.a, "/api/conta/sair", {})
        self.pedido(self.a, "/api/conta", esperado=401)

    def test_convite_codigo_frases_e_bloqueio(self):
        self.criar_conta(self.a, "aurora", 16)
        self.criar_conta(self.b, "cosmos", 10)
        rota, convite = self.equipa()
        self.pedido(self.a, rota + "/convites", {"nickname": "cosmos"}, 400)
        self.pedido(self.b, "/api/convites/usar", {**convite, "convite": "x" * 24}, 404)
        self.pedido(self.b, "/api/convites/usar", convite, 201)
        self.pedido(self.b, "/api/convites/usar", convite, 404)
        self.pedido(self.b, rota)
        self.pedido(self.a, rota + "/mensagens", {"tipo": "texto", "texto": "Olá", "chave": uuid4().hex}, 403)
        id_ = self.pedido(self.a, rota + "/mensagens",
                          {"tipo": "frase", "frase": "plano", "chave": uuid4().hex}, 201)["id"]
        vista = self.pedido(self.b, rota + "/presenca", {"x": 0, "z": 4, "mensagens_depois": 0})
        self.assertEqual(vista["conversa"], "frases")
        self.assertEqual(vista["mensagens"][0]["id"], id_)
        self.pedido(self.b, rota + "/denunciar", {"motivo": "mensagem", "mensagem": id_})
        self.pedido(self.b, rota + "/bloquear", {})
        self.assertEqual(self.pedido(self.a, rota + "/mensagens"), [])
        self.pedido(self.a, rota + "/mensagens", {"tipo": "frase", "frase": "plano", "chave": uuid4().hex}, 403)
        _, segundo_convite = self.equipa()
        self.pedido(self.b, "/api/convites/usar", segundo_convite, 403)

    def test_progresso_a_solo_aparece_na_retoma(self):
        self.criar_conta(self.a, "aurora", 16)
        self.criar_conta(self.b, "cosmos", 16)
        rota, convite = self.equipa()
        self.pedido(self.b, "/api/convites/usar", convite, 201)
        self.pedido(self.b, rota)

        def comando(cliente, acao, valor=None):
            revisao = self.pedido(cliente, rota)["revisao"]
            return self.pedido(cliente, rota + "/comandos", {
                "id": uuid4().hex, "acao": acao, "valor": valor, "revisao": revisao,
            })

        comando(self.a, "destino", "lua")
        comando(self.a, "carga", carga_minima("lua"))
        comando(self.a, "pronto")
        comando(self.b, "pronto")
        comando(self.a, "lancar")
        self.pedido(self.b, rota + "/ausente", {})
        vista = comando(self.a, "avancar")
        self.assertIsNotNone(vista["estado"]["desafio"])
        progresso = self.pedido(self.b, rota)["estado"]["progresso_a_solo"]
        self.assertEqual(progresso[-1]["revisao"], vista["revisao"])
        self.assertTrue(self.pedido(self.b, rota)["estado"]["historico"][-1]["a_solo"])

    @patch("app.servico.CONVERSA_LIVRE", True)
    def test_voz_retencao_e_limites_partilhados(self):
        self.criar_conta(self.a, "aurora", 16)
        self.criar_conta(self.b, "cosmos", 15)
        rota, convite = self.equipa()
        self.pedido(self.b, "/api/convites/usar", convite, 201)
        self.pedido(self.a, rota + "/mensagens",
                    {"tipo": "texto", "texto": "o meu email é pessoa@example.test", "chave": uuid4().hex}, 400)
        audio = b64encode(bytes.fromhex("1a45dfa3") + bytes(36)).decode()
        voz = {"tipo": "audio", "formato": "audio/webm", "audio": audio, "chave": uuid4().hex}
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: self.pedido(self.a, rota + "/mensagens", voz, 201)["id"], range(2)))
        self.assertEqual(ids[0], ids[1])
        ficheiro = rota + "/audio/" + str(ids[0])
        self.assertEqual(self.pedido(self.b, ficheiro)["audio"], audio)
        with ligacao(self.bd) as conn:
            conn.execute("UPDATE mensagens SET enviada_em=%s", (int(time()) - 86401,))
        self.pedido(self.b, ficheiro, esperado=404)
        limpar(self.bd)
        with ligacao(self.bd) as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM mensagens").fetchone())
        a, b = Contas(self.bd), Contas(self.bd)
        a.limites.verificar(("qa", "partilhado"), 1, 300)
        with self.assertRaises(Erro) as falha:
            b.limites.verificar(("qa", "partilhado"), 1, 300)
        self.assertEqual(falha.exception.status, 429)
