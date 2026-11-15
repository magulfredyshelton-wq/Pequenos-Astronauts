from concurrent.futures import ThreadPoolExecutor
import json
import unittest
from uuid import uuid4

from app.catalogo import LINHAS, carga_minima
from app.db import ligacao, migrar
from app.main import criar_app
from fastapi.testclient import TestClient
from app.llm import Ollama
from app import neural_r1
from app.neural import estado_inicial, reagir
from app.servico import Jogo
from teste_bd import esquema_temporario


class Campanha(unittest.TestCase):
    def setUp(self):
        self.bd = esquema_temporario(self)
        self.assertGreaterEqual(len(migrar(self.bd)), 6)
        self.assertEqual(migrar(self.bd), [])
        self.jogo = Jogo(self.bd, Ollama(activo=False))
        self.cliente = TestClient(criar_app(self.jogo, legado=True))
        self.cliente.__enter__()
        self.addCleanup(self.cliente.__exit__, None, None, None)

    def http(self, rota, corpo=None, acesso=None, status=200):
        cab = {"Content-Type": "application/json"}
        if acesso:
            cab["Authorization"] = "Bearer " + acesso["token"]
        resposta = self.cliente.request("GET" if corpo is None else "POST", rota, json=corpo, headers=cab)
        self.assertEqual(resposta.status_code, status, resposta.text)
        return resposta.json() if resposta.headers["content-type"].startswith("application/json") else resposta.content

    def criar(self, nivel="cadete"):
        return self.http("/api/partidas", {"nome": "Aurora", "nivel": nivel}, status=201)

    def rota(self, acesso):
        return "/api/partidas/" + acesso["codigo"]

    def comando(self, acesso, acao, valor=None, status=200, versao=None, id_=None):
        rota = self.rota(acesso)
        if versao is None:
            versao = self.http(rota, acesso=acesso)["revisao"]
        return self.http(rota + "/comandos", {"acao": acao, "valor": valor,
                         "id": id_ or uuid4().hex, "revisao": versao}, acesso, status)

    def campanha(self, destino):
        acesso = self.criar("comandante")
        self.assertIn(b'id="palco"', self.http("/"))  # página do frontend 2D
        self.assertIn(b"Little Astronauts", self.http("/js/main.js"))
        self.assertIn(b"superficie", self.http("/js/mundo.js"))
        self.http(self.rota(acesso), status=401)
        self.comando(acesso, "destino", destino)
        self.comando(acesso, "lancar", status=400)
        self.comando(acesso, "carga", {"agua": 10000}, status=400)
        carga = carga_minima(destino) | {"bateria": 1, "filtro": 1, "pecas": 2}
        carga["agua"] += 12
        self.comando(acesso, "carga", carga)
        self.comando(acesso, "lancar")

        percorridos = []
        for i, desafio in enumerate(LINHAS["viagem"]):
            estado = self.comando(acesso, "avancar")["estado"]
            percorridos.append(estado["desafio"]["id"])
            self.assertEqual(estado["desafio"]["id"], desafio[0])
            self.assertEqual(estado["desafio"]["modo"], "resposta_aberta")
            if i == 0:
                antes = self.http(self.rota(acesso), acesso=acesso)
                leitura = self.http(self.rota(acesso) + "/interpretar",
                                    {"texto": desafio[3], "revisao": antes["revisao"]}, acesso)
                self.assertEqual((leitura["opcao"], leitura["metodo"]), ("segura", "lexico"))
                self.assertEqual(self.http(self.rota(acesso), acesso=acesso)["revisao"], antes["revisao"])
                anterior = estado["recursos"]["propulsante"]
                estado = self.comando(acesso, "responder", "risco")["estado"]
                self.assertLess(estado["recursos"]["propulsante"], anterior)
                self.assertTrue(estado["recuperacao"])
                self.comando(acesso, "avancar", status=400)
                horas = self.comando(acesso, "responder", "adiar")["estado"]["horas"]
                recuperada = self.comando(acesso, "responder", "recuperar")["estado"]
                self.assertFalse(recuperada["recuperacao"])
                self.assertGreaterEqual(recuperada["horas"], horas)
            elif desafio[0] == "reciclagem_agua":
                self.comando(acesso, "responder", "risco")
                self.comando(acesso, "avancar", status=400)
                recuperada = self.comando(acesso, "responder", "recuperar")["estado"]
                self.assertIsNone(recuperada["desafio"])
            else:
                self.comando(acesso, "responder", "segura")

        estado = self.comando(acesso, "avancar")["estado"]
        self.assertEqual(estado["fase"], "aproximacao")
        self.assertGreaterEqual(estado["horas"], estado["horas_rota"])
        self.assertEqual(estado["recursos"]["agua"], carga["agua"] - estado["horas"] * 6 // 24 - 8)
        estado = self.comando(acesso, "pousar", 1)["estado"]
        percorridos.append(estado["desafio"]["id"])
        self.comando(acesso, "responder", "segura")
        self.comando(acesso, "instalar", "energia", status=400)
        self.comando(acesso, "descarregar")
        self.comando(acesso, "instalar", "habitat", status=400)
        for modulo in ("energia", "radio", "habitat"):
            estado = self.comando(acesso, "instalar", modulo)["estado"]
            self.assertEqual(estado["inventario"][modulo], 0)
        for desafio in LINHAS[destino][1:]:
            estado = self.comando(acesso, "avancar")["estado"]
            percorridos.append(estado["desafio"]["id"])
            self.assertEqual(estado["desafio"]["id"], desafio[0])
            if desafio[0] in {"poeira_antecamara", "painel_marte"}:
                self.assertTrue(self.comando(acesso, "responder", "risco")["estado"]["recuperacao"])
                self.comando(acesso, "avancar", status=400)
                self.comando(acesso, "responder", "recuperar")
            else:
                self.comando(acesso, "responder", "segura")
        estado = self.comando(acesso, "avancar")["estado"]
        self.assertEqual(estado["desfecho"], "base_estabilizada")
        self.assertEqual(len(estado["tripulacao"]), 3)
        com_novo_servico = Jogo(self.bd, Ollama(activo=False))
        self.assertEqual(com_novo_servico.ver(acesso["codigo"], acesso["token"])["estado"], estado)
        with ligacao(self.bd) as conn:
            bruto = conn.execute("SELECT estado FROM partidas WHERE codigo = %s", (acesso["codigo"],)).fetchone()["estado"]
            self.assertTrue(all(npc["tick"] > 15 for npc in bruto["neural"].values()))
            if neural_r1.R1_ACTIVO:
                self.assertNotIn("neural_r1", estado)
                self.assertEqual(bruto["neural_r1"]["tick"], bruto["neural"]["comando"]["tick"])
                self.assertEqual(len(bruto["neural_r1"]["redes"]), 3)
                self.assertTrue(all(len(npc["estado"]["arrays"]["_spikes"]) == 188
                                    for npc in bruto["neural_r1"]["redes"].values()))
        return percorridos

    def test_rotas(self):
        lua = self.campanha("lua")
        marte = self.campanha("marte")
        self.assertEqual(len(lua), 18)
        self.assertEqual(len(marte), 18)
        self.assertEqual(len(set(lua + marte)), 27)

    def test_cooperacao_repeticao_e_retirada(self):
        a = self.criar()
        rota = self.rota(a)
        conv = self.http(rota + "/convites", {}, a, 201)["convite"]
        dados = {"convite": conv, "nome": "Orion", "nivel": "piloto"}
        b = self.http(rota + "/entrar", dados, status=201)
        self.http(rota + "/entrar", dados, status=403)
        conv = self.http(rota + "/convites", {}, a, 201)["convite"]
        c = self.http(rota + "/entrar", {"convite": conv, "nome": "Nova", "nivel": "comandante"}, status=201)
        self.http(rota + "/presenca", {"x": 2, "z": 3}, b)
        self.assertEqual(next(j for j in self.http(rota, acesso=a)["jogadores"] if j["id"] == b["jogador"])["x"], 2)
        self.comando(b, "destino", "lua", status=400)
        self.comando(a, "destino", "lua")
        self.comando(a, "carga", carga_minima("lua"))
        self.comando(a, "lancar", status=400)
        for jogador in (a, b, c):
            self.comando(jogador, "pronto")
        self.comando(a, "lancar")
        self.comando(a, "assumir_posto")
        self.comando(b, "assumir_posto", status=400)
        ajustada = self.comando(a, "ajustar_rota", 1)["estado"]
        self.assertEqual(ajustada["ajuste_rota"], 1)
        self.assertEqual(ajustada["recursos"]["propulsante"], 136)
        self.comando(b, "avancar", status=400)
        self.comando(a, "libertar_posto")
        revisao = self.http(rota, acesso=a)["revisao"]
        id_ = uuid4().hex
        def repetir(_):
            return self.comando(a, "avancar", versao=revisao, id_=id_)
        with ThreadPoolExecutor(max_workers=3) as exe:
            respostas = list(exe.map(repetir, range(3)))
        self.assertTrue(all(x == respostas[0] for x in respostas))
        self.assertIsNone(respostas[0]["estado"]["desafio"])
        self.comando(b, "avancar")
        self.assertEqual(self.comando(c, "avancar")["estado"]["desafio"]["id"], "desvio")
        self.assertEqual(self.http(rota, acesso=b)["estado"]["desafio"]["modo"], "comparacao")
        self.assertEqual(self.http(rota, acesso=c)["estado"]["desafio"]["modo"], "resposta_aberta")
        self.comando(a, "responder", "risco")
        self.assertEqual(self.comando(a, "retirada")["estado"]["desfecho"], "retirada_segura")


class Neural(unittest.TestCase):
    def test_reaccoes(self):
        estado = {"recursos": {"energia": 100, "oxigenio": 20}, "destino": "lua",
                  "desafio": None, "recuperacao": False, "sinal": "", "historico": [], "neural": estado_inicial()}
        reagir(estado)
        self.assertTrue(all(n["emocao"] == "SERENO" for n in estado["neural"].values()))
        estado.update(desafio={"grupo": "viagem", "indice": 2}, recuperacao=True)
        estado["recursos"].update(energia=5, oxigenio=2)
        for _ in range(3):
            reagir(estado)
        self.assertTrue(any(n["emocao"] in {"PANICO", "PROTESTO", "TRISTEZA"} for n in estado["neural"].values()))
        estado.update(desafio=None, recuperacao=False, sinal="sucesso")
        estado["recursos"].update(energia=90, oxigenio=15)
        for _ in range(4):
            reagir(estado)
        self.assertTrue(any(n["emocao"] == "ALIVIO" for n in estado["neural"].values()))

    @unittest.skipUnless(neural_r1.R1_ACTIVO, "A rede R1 requer NumPy")
    def test_r1_reiniciar_e_retoma_partida_antiga(self):
        import os
        import subprocess
        import sys

        from app.missao import novo_estado, registar

        estado = novo_estado()
        # Uma partida antiga não contém o novo campo. A primeira acção cria-o.
        self.assertNotIn("neural_r1", estado)
        registar(estado, "Sistemas prontos")
        self.assertEqual(len(estado["neural_r1"]["redes"]), 3)

        codigo = (
            "import json, sys; from app.missao import registar; "
            "s=json.load(sys.stdin); s['recursos']['energia']=18; "
            "s['desafio']={'grupo':'marte','indice':1}; s['recuperacao']=True; "
            "registar(s,'Alerta','alerta'); print(json.dumps(s))"
        )
        processo = subprocess.run(
            [sys.executable, "-B", "-c", codigo],
            input=json.dumps(estado), capture_output=True, text=True, check=True,
            encoding="utf-8", env={**os.environ, "ASTRO_CEREBRO": "r1"}, timeout=15,
        )
        estado["recursos"]["energia"] = 18
        estado["desafio"] = {"grupo": "marte", "indice": 1}
        estado["recuperacao"] = True
        registar(estado, "Alerta", "alerta")
        self.assertEqual(json.loads(processo.stdout), estado)
        self.assertTrue(any(npc["reaccao"]["emocao"] in {"PROTESTO", "PANICO"}
                            for npc in estado["neural_r1"]["redes"].values()))


if __name__ == "__main__":
    unittest.main()

