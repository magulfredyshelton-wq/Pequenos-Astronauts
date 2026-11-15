import unittest

from fastapi.testclient import TestClient

from app.contas import Contas
from app.db import migrar
from app.main import criar_app
from app.servico import Jogo
from teste_bd import esquema_temporario


def relatorio(**extra):
    base = {"chave": "missao-0001-abcdef", "destino": "Lua", "resultado": "ok", "estrelas": 3, "hora": 54,
            "recursos": {"ar": 90, "agua": 60, "comida": 70, "energia": 40, "rad": 12},
            "evas": [{"n": 1, "plano": "curta", "maxDist": 30, "suitMin": 120}], "causas": [],
            "comidaProduzida": 41, "baseNivel": 3, "amostrasAnalisadas": 5, "diario": ["EVA 1 concluída."]}
    base.update(extra)
    return base


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.bd = esquema_temporario(self)
        self.assertIn("007_sandbox.sql", migrar(self.bd))
        self.app = criar_app(Jogo(self.bd), Contas(self.bd))
        self.c = TestClient(self.app); self.c.__enter__(); self.addCleanup(self.c.__exit__, None, None, None)

    def conta(self, cliente, nome, idade=16):
        self.assertEqual(cliente.post("/api/conta/entrar", json={"nome": nome, "idade": idade}).status_code, 200)
        self.assertEqual(cliente.post("/api/conta/nickname", json={"nickname": nome}).status_code, 200)

    def test_exige_conta(self):
        self.assertEqual(self.c.post("/api/sandbox/resultados", json=relatorio()).status_code, 401)
        self.assertEqual(self.c.get("/api/sandbox/resultados").status_code, 401)

    def test_guardar_listar_idempotente_e_ranking(self):
        self.conta(self.c, "aurora")
        r = self.c.post("/api/sandbox/resultados", json=relatorio())
        self.assertEqual((r.status_code, r.json()["guardado"]), (201, True))
        r = self.c.post("/api/sandbox/resultados", json=relatorio())
        self.assertEqual((r.status_code, r.json()["repetido"]), (200, True))
        self.c.post("/api/sandbox/resultados", json=relatorio(chave="missao-0002-abcdef", resultado="rad", estrelas=0, baseNivel=1))
        lista = self.c.get("/api/sandbox/resultados").json()
        self.assertEqual(lista["resumo"], {"missoes": 2, "cumpridas": 1, "melhor": 3, "amostras": 10})
        self.assertEqual(lista["missoes"][0]["destino"], "lua")
        ranking = TestClient(self.app).get("/api/sandbox/ranking").json()["ranking"]
        self.assertEqual([x["nickname"] for x in ranking], ["aurora"])
        self.assertNotIn("nome", ranking[0]); self.assertNotIn("email", ranking[0])

    def test_validacao(self):
        self.conta(self.c, "aurora")
        for mau in (relatorio(chave="x"), relatorio(destino="Venus"), relatorio(resultado="xx"), relatorio(estrelas=4),
                    relatorio(resultado="ar", estrelas=2), relatorio(baseNivel=9), relatorio(hora=-1),
                    relatorio(recursos={"ouro": 1}), relatorio(evas=[{"plano": "x"}]), relatorio(causas=["a" * 301]),
                    relatorio(amostrasAnalisadas="5"), relatorio(estrelas=True)):
            self.assertEqual(self.c.post("/api/sandbox/resultados", json=mau).status_code, 400, mau)

    def test_cenarios_em_ingles_vindos_do_catalogo(self):
        r = self.c.get("/api/sandbox/cenarios", params={"destino": "marte", "semente": "abc123", "lang": "en"})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual((d["destination"], len(d["travel"]), len(d["surface"])), ("Mars", 9, 6))
        self.assertEqual(self.c.get("/api/sandbox/cenarios", params={"destino": "marte", "semente": "abc123"}).json()["surface"], d["surface"])
        for i in d["travel"] + d["surface"]:
            self.assertTrue(all(i[k] for k in ("title", "signal", "safe", "risky", "consequence", "recovery", "concept")))
            self.assertNotRegex(i["title"] + i["signal"], r"[ãçõé]")
        self.assertEqual(d["crew_lines"]["COMANDO"]["ALIVIO"], "Good decision! We can move on to the next task.")
        if d["real_eva"]:
            self.assertEqual(d["real_eva"]["inspired_incident"], d["surface"][0]["id"])
        self.assertEqual(self.c.get("/api/sandbox/cenarios", params={"destino": "venus"}).status_code, 400)
        self.assertEqual(self.c.get("/api/sandbox/cenarios", params={"lang": "xx"}).status_code, 400)
        self.assertEqual(self.c.get("/api/sandbox/cenarios", params={"destino": "lua", "lang": "pt"}).json()["surface"][0]["title"][:1].isupper(), True)

    def test_isolamento_entre_contas(self):
        self.conta(self.c, "aurora")
        self.c.post("/api/sandbox/resultados", json=relatorio())
        outro = TestClient(self.app); outro.__enter__(); self.addCleanup(outro.__exit__, None, None, None)
        self.conta(outro, "cosmos")
        self.assertEqual(outro.get("/api/sandbox/resultados").json()["resumo"]["missoes"], 0)


if __name__ == "__main__":
    unittest.main()
