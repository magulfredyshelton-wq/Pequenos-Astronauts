import unittest

from app.catalogo import carga_minima
from app.missao import MONTAGEM, Regra, aplicar, dados_desafio, novo_estado, plano_da_rota, relatorio

A = {"id": "a", "anfitriao": True, "nivel": "comandante"}
B = {"id": "b", "anfitriao": False, "nivel": "cadete"}


def iniciar(destino):
    estado = novo_estado()
    aplicar(estado, "destino", destino, A, {"a"})
    aplicar(estado, "carga", carga_minima(destino), A, {"a"})
    aplicar(estado, "lancar", None, A, {"a"}, cooperativa=True)
    estado["semente"] = 19
    estado["plano"] = plano_da_rota(destino, 19)
    return estado


def campanha(estado, escolha):
    while not estado["desfecho"]:
        fase = estado["fase"]
        if estado["desafio"]:
            acao, valor = "responder", "recuperar" if estado["recuperacao"] else escolha
        elif fase == "aproximacao":
            acao, valor = "pousar", 0
        elif fase == "instalacao":
            acao, valor = ("instalar", MONTAGEM[len(estado["montados"])][0]) if estado["descarregada"] else ("descarregar", None)
        else:
            acao, valor = "avancar", None
        aplicar(estado, acao, valor, A, {"a"}, cooperativa=True)


class Missoes(unittest.TestCase):
    def test_rotas_seguras_e_arriscadas(self):
        for destino in ("lua", "marte"):
            with self.subTest(destino=destino):
                estado = iniciar(destino)
                campanha(estado, "segura")
                self.assertEqual(estado["desfecho"], "base_estabilizada")
                self.assertEqual(relatorio(estado)["estrelas"], 3)
                estado = iniciar(destino)
                campanha(estado, "risco")
                self.assertEqual(estado["desfecho"], "missao_falhada")
                self.assertEqual(relatorio(estado)["estrelas"], 0)

    def test_recurso_exposicao_margem_e_adiamentos(self):
        estado = iniciar("lua")
        aplicar(estado, "avancar", None, A, {"a"})
        estado["desafio"] = {"grupo": "viagem", "indice": 0}
        aplicar(estado, "responder", "risco", A, {"a"})
        for _ in range(2):
            aplicar(estado, "responder", "adiar", A, {"a"})
        self.assertNotIn("adiar", dados_desafio(estado, "cadete")["opcoes"])
        with self.assertRaises(Regra):
            aplicar(estado, "responder", "adiar", A, {"a"})
        self.assertEqual(estado["recursos"]["margem"], 4)
        for indice, recurso, reserva in [(2, "oxigenio", 6), (4, "exposicao", 2), (5, "margem", 1)]:
            estado = iniciar("lua")
            estado["desafio"] = {"grupo": "viagem", "indice": indice}
            estado["recursos"][recurso] = reserva
            aplicar(estado, "responder", "risco", A, {"a"})
            self.assertEqual(estado["desfecho"], "missao_falhada")
            with self.assertRaises(Regra):
                aplicar(estado, "avancar", None, A, {"a"})

    def test_descoberta_registada_uma_vez(self):
        estado = iniciar("lua")
        with self.assertRaises(Regra):
            aplicar(estado, "explorar", "amostra", A, {"a"})
        estado["fase"] = "instalacao"
        aplicar(estado, "explorar", "amostra", A, {"a"})
        self.assertEqual(estado["descobertas"], ["amostra"])
        with self.assertRaises(Regra):
            aplicar(estado, "explorar", "amostra", A, {"a"})

    def test_planeamento_e_divergencia(self):
        planos = [plano_da_rota("marte", i) for i in range(15)]
        self.assertTrue(all(len(p["viagem"]) == 2 and len(p["marte"]) == 7 for p in planos))
        self.assertGreater(len({tuple(p["marte"]) for p in planos}), 10)
        estado = iniciar("lua")
        aplicar(estado, "avancar", None, A, {"a"})
        aplicar(estado, "responder", "segura", A, {"a", "b"}, 2, True)
        self.assertEqual(estado["espera_equipa"], "aguarda")
        aplicar(estado, "responder", "risco", B, {"a", "b"}, 2, True)
        self.assertEqual(estado["espera_equipa"], "divergencia")
        aplicar(estado, "responder", "segura", B, {"a", "b"}, 2, True)
        self.assertIsNone(estado["desafio"])
        self.assertIsNone(estado["espera_equipa"])
