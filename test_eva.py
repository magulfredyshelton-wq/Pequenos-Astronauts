import json
import tempfile
import unittest
from pathlib import Path
from random import Random
from unittest import mock

from app import eva
from app.catalogo import LINHAS, carga_minima
from app.missao import aplicar, desafio_do_tema, novo_estado, plano_da_rota, relatorio

A = {"id": "a", "anfitriao": True, "nivel": "comandante"}

CSV = (
    "\ufeffEVA,Country,Crew,Vehicle,Date,Duration,Purpose\n"
    '1,Russia,"Leonov, Alexei",Voskhod 2,1965-03-18T00:00:00.000,0:12,"First spacewalk; test of the airlock"\n'
    '2,USA,"White, Edward",Gemini IV,06/03/1965,0:36,Evaluate hand-held manoeuvring unit\n'
    "3,USA,Crew <b>X</b>,ISS,2020-01-15,6:32,Replace a failed battery and repair a cable\n"
    "4,USA,Crew Y,ISS,2021-02-02,7:00,\n"          # sem propósito: é ignorada
    "5,USA,Crew Z,ISS,2021-03-03,sem formato,Collect a sample for science\n"
)


def registos_de_teste(n=30):
    temas = ["reparo", "instalacao", "ciencia", "teste", "montagem", "inspecao", "geral"]
    return [{"eva": str(i), "pais": "EUA", "tripulacao": f"Crew {i}", "veiculo": "ISS",
             "data": f"20{10 + i % 10}-01-01", "duracao_min": 60 + i, "proposito": f"Task {i}",
             "tema": temas[i % len(temas)]} for i in range(n)]


class Parsing(unittest.TestCase):
    def test_csv_com_bom_aspas_e_linhas_invalidas(self):
        registos = eva.interpretar(CSV.encode("utf-8"))
        self.assertEqual([r["eva"] for r in registos], ["1", "2", "3", "5"])  # a 4 não tem propósito
        leonov = registos[0]
        self.assertEqual((leonov["pais"], leonov["data"], leonov["duracao_min"]), ("Rússia", "1965-03-18", 12))
        self.assertEqual(leonov["tripulacao"], "Leonov, Alexei")
        self.assertEqual(registos[1]["data"], "1965-06-03")        # formato mês/dia/ano
        self.assertIsNone(registos[3]["duracao_min"])               # duração ilegível não rebenta

    def test_texto_externo_e_limpo(self):
        registos = eva.interpretar(CSV.encode("utf-8"))
        self.assertNotIn("<", registos[2]["tripulacao"])
        self.assertEqual(eva.limpar("a\x00b\n\tc  d", 50), "a b c d")
        self.assertEqual(len(eva.limpar("x" * 999, 20)), 20)

    def test_json_lista_e_json_socrata(self):
        lista = [{"EVA": "1", "Country": "USA", "Date": "2000-01-01", "Duration": "5:30", "Purpose": "Install a truss"}]
        self.assertEqual(eva.interpretar(json.dumps(lista).encode())[0]["duracao_min"], 330)
        socrata = {"meta": {"view": {"columns": [{"fieldName": ":sid"}, {"fieldName": "eva"}, {"fieldName": "country"},
                                                 {"fieldName": "duration"}, {"fieldName": "purpose"}]}},
                   "data": [[1, "7", "Russia", "1:05", "Inspect antenna"]]}
        registo = eva.interpretar(json.dumps(socrata).encode())[0]
        self.assertEqual((registo["eva"], registo["pais"], registo["duracao_min"], registo["tema"]),
                         ("7", "Rússia", 65, "inspecao"))
        with self.assertRaises(ValueError):
            eva.interpretar(b'{"qualquer": 1}')

    def test_duracoes(self):
        for texto, esperado in [("7:00", 420), ("0:12", 12), ("1:02:40", 63), ("0:00", None), ("7:75", None),
                                ("abc", None), ("", None), (None, None), ("30:00", None)]:
            with self.subTest(texto=texto):
                self.assertEqual(eva.minutos(texto), esperado)

    def test_classificacao(self):
        casos = {"Repair of the solar array": "reparo", "Assembly of the truss": "montagem",
                 "Install new antenna": "instalacao", "Test of the new suit": "teste",
                 "Collect an experiment sample": "ciencia", "Inspect the hull": "inspecao", "Walk": "geral"}
        for texto, tema in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(eva.classificar(texto), tema)


class Catalogo(unittest.TestCase):
    def test_todos_os_temas_apontam_para_desafios_que_existem(self):
        for tema, destinos in eva.TEMAS.items():
            for destino in ("lua", "marte"):
                with self.subTest(tema=tema, destino=destino):
                    ids = [linha[0] for linha in LINHAS[destino]]
                    self.assertTrue(destinos[destino])
                    for id_ in destinos[destino]:
                        self.assertIn(id_, ids[1:])  # nunca o desafio 0 (pouso)
                    self.assertIsNotNone(desafio_do_tema(tema, destino))


class Escolha(unittest.TestCase):
    def test_deterministica_e_vazia(self):
        registos = registos_de_teste()
        self.assertEqual(eva.escolher(7, registos), eva.escolher(7, registos))
        self.assertIsNone(eva.escolher(7, []))
        self.assertIn(eva.escolher(7, registos)["eva"], {r["eva"] for r in registos})

    def test_prefere_registos_completos(self):
        incompletos = [{"eva": "x", "proposito": "Walk", "tema": "geral", "duracao_min": None}]
        completo = {"eva": "ok", "proposito": "Walk", "tema": "geral", "duracao_min": 90}
        for semente in range(20):
            self.assertEqual(eva.escolher(semente, incompletos + [completo])["eva"], "ok")
        self.assertEqual(eva.escolher(1, incompletos)["eva"], "x")  # só há estes: usa-os

    def test_desactivada_por_configuracao(self):
        with mock.patch.object(eva, "EVA_ACTIVO", False):
            self.assertIsNone(eva.escolher(1, registos_de_teste()))


class Plano(unittest.TestCase):
    def test_sem_tema_o_plano_e_o_de_sempre(self):
        for destino in ("lua", "marte"):
            sorteio = Random(19)
            sorteio.choice([0, 1, 6, 7]); sorteio.choice([2, 3, 4, 5, 8])
            esperado = [0, *sorteio.sample(range(1, len(LINHAS[destino])), 6)]
            self.assertEqual(plano_da_rota(destino, 19)[destino], esperado)
            self.assertEqual(plano_da_rota(destino, 19, None), plano_da_rota(destino, 19))

    def test_tema_passa_a_ser_o_primeiro_incidente_da_superficie(self):
        for destino in ("lua", "marte"):
            for tema in eva.TEMAS:
                for semente in range(12):
                    with self.subTest(destino=destino, tema=tema, semente=semente):
                        base = plano_da_rota(destino, semente)
                        plano = plano_da_rota(destino, semente, tema)
                        superficie = plano[destino]
                        self.assertEqual(superficie[0], 0)
                        self.assertEqual(superficie[1], desafio_do_tema(tema, destino))
                        self.assertEqual(len(superficie), len(base[destino]))
                        self.assertEqual(len(set(superficie)), len(superficie))
                        self.assertEqual(plano["viagem"], base["viagem"])


class Missao(unittest.TestCase):
    def lancar(self, destino, registos, cooperativa=True):
        estado = novo_estado()
        aplicar(estado, "destino", destino, A, {"a"})
        aplicar(estado, "carga", carga_minima(destino), A, {"a"})
        with mock.patch.object(eva, "carregar", return_value=registos):
            aplicar(estado, "lancar", None, A, {"a"}, cooperativa=cooperativa)
        return estado

    def test_lancamento_guarda_a_eva_e_orienta_o_plano(self):
        for destino in ("lua", "marte"):
            with self.subTest(destino=destino):
                estado = self.lancar(destino, registos_de_teste())
                referencia = estado["eva"]
                self.assertEqual(estado["plano"][destino][1], desafio_do_tema(referencia["tema"], destino))
                self.assertEqual(LINHAS[destino][estado["plano"][destino][1]][0], referencia["desafio"])
                json.dumps(estado)                              # tem de caber no JSONB da partida
                self.assertLess(len(json.dumps(referencia)), 900)

    def test_modo_solo_guarda_a_eva_sem_plano(self):
        estado = self.lancar("lua", registos_de_teste(), cooperativa=False)
        self.assertIn("eva", estado)
        self.assertNotIn("plano", estado)

    def test_sem_dados_o_jogo_funciona_como_antes(self):
        estado = self.lancar("lua", [])
        self.assertNotIn("eva", estado)
        self.assertEqual(estado["fase"], "viagem")

    def test_nota_aparece_so_no_incidente_escolhido_pela_eva(self):
        estado = self.lancar("lua", registos_de_teste())
        destino, plano = "lua", estado["plano"]["lua"]
        estado["fase"] = "aproximacao"
        aplicar(estado, "pousar", 0, A, {"a"})
        self.assertNotIn("NASA", estado["mensagem"])            # incidente 0 (pouso): sem nota
        estado["desafio"] = None
        estado["proximo"] = 1
        from app.missao import abrir_desafio
        abrir_desafio(estado, destino, plano[1])
        self.assertIn("saída extraveicular real da NASA", estado["mensagem"])
        abrir_desafio(estado, destino, plano[2])
        self.assertNotIn("NASA", estado["mensagem"])

    def test_relatorio_inclui_a_eva(self):
        estado = self.lancar("lua", registos_de_teste())
        estado["desfecho"] = "base_estabilizada"
        resultado = relatorio(estado)
        self.assertEqual(resultado["eva"], estado["eva"])
        self.assertEqual(resultado["horas_missao"], estado["horas"])


class Cache(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.cache = Path(self.pasta.name) / "data" / "eva_cache.json"
        for patch in (mock.patch.object(eva, "EVA_CACHE", self.cache),
                      mock.patch.dict(eva._MEM, {"registos": None, "marca": None, "obtido_em": 0.0, "origem": ""})):
            patch.start()
            self.addCleanup(patch.stop)
        self.csv = "EVA,Country,Crew,Vehicle,Date,Duration,Purpose\n" + "".join(
            f"{i},USA,Crew,ISS,2020-01-01,{1 + i % 7}:00,Repair item {i}\n" for i in range(40))

    def test_sincronizar_grava_e_carregar_le_sem_rede(self):
        with mock.patch.object(eva, "_abrir", return_value=self.csv.encode()) as abrir:
            estado = eva.sincronizar(["https://exemplo.test/eva.csv"])
        abrir.assert_called_once()
        self.assertEqual((estado["total"], estado["activo"]), (40, True))
        self.assertTrue(self.cache.exists())
        eva._MEM.update(registos=None, marca=None)             # simula um novo processo
        with mock.patch.object(eva, "_abrir", side_effect=AssertionError("não devia usar a rede")):
            self.assertEqual(len(eva.carregar()), 40)

    def test_tenta_a_proxima_url_e_rejeita_respostas_pequenas(self):
        respostas = {"https://a.test/x": b"EVA,Country,Purpose\n1,USA,Repair\n", "https://b.test/x": self.csv.encode()}
        with mock.patch.object(eva, "_abrir", side_effect=lambda url: respostas[url]):
            self.assertEqual(eva.sincronizar(list(respostas))["origem"], "https://b.test/x")

    def test_falha_total_levanta_erro_e_nao_apaga_a_cache(self):
        with mock.patch.object(eva, "_abrir", return_value=self.csv.encode()):
            eva.sincronizar(["https://a.test/x"])
        with mock.patch.object(eva, "_abrir", side_effect=OSError("sem rede")):
            with self.assertRaises(eva.ErroEva):
                eva.sincronizar(["https://a.test/x", "http://inseguro.test/x"])
            self.assertEqual(len(eva.carregar()), 40)

    def test_so_aceita_https(self):
        with mock.patch.object(eva, "_abrir") as abrir:
            with self.assertRaises(eva.ErroEva):
                eva.sincronizar(["http://a.test/x", "file:///etc/passwd"])
        abrir.assert_not_called()

    def test_arranque_so_vai_a_rede_se_a_cache_faltar_ou_for_velha(self):
        with mock.patch.object(eva, "_abrir", return_value=self.csv.encode()) as abrir:
            with mock.patch.object(eva, "EVA_URLS", ["https://a.test/x"]):
                self.assertTrue(eva.sincronizar_se_preciso())
                self.assertFalse(eva.sincronizar_se_preciso())   # cache fresca
                eva._MEM["obtido_em"] -= 8 * 86400
                self.assertTrue(eva.sincronizar_se_preciso())    # cache velha
        self.assertEqual(abrir.call_count, 2)

    def test_arranque_sem_rede_nao_rebenta(self):
        with mock.patch.object(eva, "_abrir", side_effect=OSError("sem rede")):
            with mock.patch.object(eva, "EVA_URLS", ["https://a.test/x"]):
                self.assertFalse(eva.sincronizar_se_preciso())
        self.assertFalse(eva.estado_fonte()["activo"])

    def test_cache_corrompida_nao_rebenta(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text("{isto não é json", encoding="utf-8")
        self.assertEqual(eva.carregar(), [])


if __name__ == "__main__":
    unittest.main()
