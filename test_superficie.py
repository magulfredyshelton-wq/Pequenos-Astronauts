"""Exploração da superfície no servidor: traje, oxigénio, rover, escavação, laboratório e pontos."""
import unittest

from app import superficie
from app.catalogo import carga_minima
from app.missao import MONTAGEM, Regra, aplicar, novo_estado, plano_da_rota, relatorio

A = {"id": "a", "anfitriao": True, "nivel": "comandante"}
B = {"id": "b", "anfitriao": False, "nivel": "cadete"}


def na_superficie(destino="lua", rover=True):
    estado = novo_estado()
    aplicar(estado, "destino", destino, A, {"a"})
    aplicar(estado, "carga", {**carga_minima(destino), "rover": 1 if rover else 0}, A, {"a"})
    aplicar(estado, "lancar", None, A, {"a"}, cooperativa=True)
    estado["semente"] = 19
    estado["plano"] = plano_da_rota(destino, 19)
    while estado["fase"] == "viagem":
        aplicar(estado, "responder" if estado["desafio"] else "avancar", "segura" if estado["desafio"] else None, A, {"a"}, cooperativa=True)
    aplicar(estado, "pousar", 0, A, {"a"}, cooperativa=True)
    aplicar(estado, "responder", "segura", A, {"a"}, cooperativa=True)
    aplicar(estado, "descarregar", None, A, {"a"}, cooperativa=True)
    return estado


def fazer(estado, acao, valor=None, m=0.0, t=1000.0, quem=A):
    aplicar(estado, acao, valor, quem, {"a", "b"}, 2, True, posicao=m, agora=t)


class Superficie(unittest.TestCase):
    def test_traje_oxigenio_e_regresso(self):
        e = na_superficie()
        fazer(e, "sair_base", m=1.4, t=1000)
        eu = e["superficie"]["astronautas"]["a"]
        self.assertEqual(eu["local"], "fora")
        self.assertEqual(superficie.oxigenio(eu, 1000), superficie.OXIGENIO_TRAJE)
        self.assertEqual(superficie.oxigenio(eu, 1120), superficie.OXIGENIO_TRAJE - 120)
        self.assertEqual(superficie.publico(e, 1120)["astronautas"]["a"]["oxigenio"], 180)
        with self.assertRaisesRegex(Regra, "porta"):
            fazer(e, "entrar_base", m=80, t=1100)
        fazer(e, "entrar_base", m=2, t=1130)
        self.assertEqual(eu["local"], "dentro")
        self.assertEqual(superficie.oxigenio(eu, 5000), superficie.OXIGENIO_TRAJE)

    def test_oxigenio_esgotado_traz_de_volta_e_desconta(self):
        e = na_superficie()
        fazer(e, "sair_base", t=1000)
        fazer(e, "recolher", 0, m=-48, t=1100)
        self.assertFalse(superficie.expirar(e, "a", 1290))
        self.assertTrue(superficie.acabou(e, "a", 1301))
        self.assertTrue(superficie.expirar(e, "a", 1301))
        eu = e["superficie"]["astronautas"]["a"]
        self.assertEqual((eu["local"], eu["leva"]["solo"], e["superficie"]["emergencias"]), ("dentro", 0, 1))
        self.assertEqual(e["superficie"]["cavados"], [0])  # o buraco fica feito, a amostra perdeu-se

    def test_recolher_exige_traje_e_proximidade(self):
        e = na_superficie()
        with self.assertRaisesRegex(Regra, "traje"):
            fazer(e, "recolher", "rocha", m=-95)
        fazer(e, "sair_base")
        with self.assertRaisesRegex(Regra, "Aproxima-te"):
            fazer(e, "recolher", "rocha", m=-40)
        fazer(e, "recolher", "rocha", m=-93)
        with self.assertRaisesRegex(Regra, "amostrada"):
            fazer(e, "recolher", "rocha", m=-95)
        fazer(e, "recolher", 4, m=-336)
        with self.assertRaisesRegex(Regra, "escavado"):
            fazer(e, "recolher", 4, m=-336)
        self.assertEqual(e["superficie"]["astronautas"]["a"]["leva"], {"rocha": True, "solo": 0, "gelo": 1})

    def test_laboratorio_regista_descoberta_e_amostras(self):
        e = na_superficie("marte")
        fazer(e, "sair_base")
        fazer(e, "recolher", "rocha", m=-95)
        fazer(e, "recolher", 1, m=70)
        with self.assertRaisesRegex(Regra, "dentro"):
            fazer(e, "analisar", "rocha", m=-95)
        with self.assertRaisesRegex(Regra, "picareta"):
            fazer(e, "explorar", "amostra", m=-95)
        fazer(e, "entrar_base", m=1)
        fazer(e, "analisar", "rocha")
        fazer(e, "analisar", "solo")
        self.assertIn("amostra", e["descobertas"])
        self.assertEqual(e["superficie"]["amostras"], {"solo": 1, "gelo": 0})
        with self.assertRaisesRegex(Regra, "Não trouxeste"):
            fazer(e, "analisar", "gelo")

    def test_scanner_exige_estar_la_fora_e_perto(self):
        e = na_superficie()
        with self.assertRaisesRegex(Regra, "traje"):
            fazer(e, "explorar", "baliza", m=210)
        fazer(e, "sair_base")
        with self.assertRaisesRegex(Regra, "Aproxima-te"):
            fazer(e, "explorar", "baliza", m=100)
        fazer(e, "explorar", "baliza", m=208)
        fazer(e, "explorar", "cratera", m=-290)
        self.assertEqual(e["descobertas"], ["baliza", "cratera"])

    def test_rover_partilhado(self):
        e = na_superficie()
        fazer(e, "sair_base")
        fazer(e, "sair_base", quem=B)
        with self.assertRaisesRegex(Regra, "Aproxima-te"):
            fazer(e, "rover", "entrar", m=60)
        fazer(e, "rover", "entrar", m=-9)
        with self.assertRaisesRegex(Regra, "condutor"):
            fazer(e, "rover", "entrar", m=-9, quem=B)
        with self.assertRaisesRegex(Regra, "Sai do rover"):
            fazer(e, "recolher", 3, m=-200)
        fazer(e, "rover", "sair", m=-198.4)
        self.assertEqual(e["superficie"]["rover"], {"m": -198.4, "condutor": None})
        fazer(e, "rover", "entrar", m=-198, quem=B)
        sem = na_superficie(rover=False)
        fazer(sem, "sair_base")
        with self.assertRaisesRegex(Regra, "rover"):
            fazer(sem, "rover", "entrar", m=-9)

    def test_pontos_contam_amostras_e_emergencias(self):
        def terminar(e):
            while not e["desfecho"]:
                if e["desafio"]:
                    acao, valor = "responder", "recuperar" if e["recuperacao"] else "segura"
                elif e["fase"] == "instalacao":
                    acao, valor = "instalar", MONTAGEM[len(e["montados"])][0]
                else:
                    acao, valor = "avancar", None
                aplicar(e, acao, valor, A, {"a"}, cooperativa=True)
            return relatorio(e)
        base = terminar(na_superficie())
        self.assertIsNone(base["exploracao"])
        e = na_superficie()
        aplicar(e, "responder", "risco", A, {"a"}, cooperativa=True) if e["desafio"] else None
        fazer(e, "sair_base", t=1000)
        fazer(e, "recolher", 0, m=-48, t=1010)
        fazer(e, "entrar_base", m=1, t=1020)
        fazer(e, "analisar", "solo", t=1030)
        fazer(e, "sair_base", t=2000)
        superficie.expirar(e, "a", 2400)
        rel = terminar(e)
        self.assertEqual(rel["exploracao"], {"amostras": 1, "escavacoes": 1, "saidas": 2, "emergencias": 1})
        self.assertEqual(rel["pontos"], max(0, min(100, base["pontos"] + 2 - 5)))


if __name__ == "__main__":
    unittest.main()
