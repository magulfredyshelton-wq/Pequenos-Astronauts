import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from app import nasa
from app.catalogo import LINHAS
from app.http import api
from app.missao import PERDAS, abrir_desafio, novo_estado, perda

APOD = {"date": "2026-11-15", "title": "Leonids over the sea", "media_type": "image",
        "explanation": "A meteor shower <b>seen</b> from Hainan.", "url": "javascript:alert(1)",
        "hdurl": "https://exemplo.test/hd.jpg", "copyright": "Someone"}

DONKI = [
    {"messageType": "FLR", "messageID": "F1", "messageIssueTime": "2026-11-14T21:00Z",
     "messageBody": "## Summary:\nX2.1 flare from Active Region 14579.\n\n## Notes:\n"},
    {"messageType": "CME", "messageID": "C1", "messageIssueTime": "2026-11-14T22:00Z",
     "messageBody": "## Summary:\nEstimated speed: ~1200 km/s. The CME may impact Mars.\n"
                    "Activity ID: 2026-11-14T22:15:00-CME-001\n"},
    {"messageType": "RBE", "messageID": "R1", "messageIssueTime": "2026-11-13T21:00Z",
     "messageBody": "## Summary:\nElectron flux elevated.\n"},
    {"messageType": "Report", "messageID": "W1", "messageIssueTime": "2026-11-12T21:00Z",
     "messageBody": "## Summary:\nWeekly report mentioning Mars and the Moon.\n"},
]

RADLAB = {"columns": ["timestamp", "instrument_id", "absorbed_dose_rate"], "index": [0, 1, 2],
          "data": [["2022-04-01T00:00:00", "DosTel1", 1.0],
                   ["2022-04-01T00:00:10", "DosTel2", 2.0],
                   ["2022-04-01T00:00:20", "DosTel2", 6.0],
                   ["2022-04-01T00:00:30", "DosTel2", "NA"]]}

OSDR = {"hits": {"hits": [{"_source": {
    "Accession": "OSD-310", "Study Title": "Spaceflight bone loss",
    "organism": "Rattus norvegicus", "Study Description": "Bone <b>loss</b> after flight."}}]}}


class Interpretacao(unittest.TestCase):
    def test_apod_limpa_e_so_aceita_https(self):
        dados = nasa.interpretar_apod(APOD)
        self.assertEqual(dados["titulo"], "Leonids over the sea")
        self.assertEqual(dados["url"], "")                      # javascript: recusado
        self.assertEqual(dados["hdurl"], "https://exemplo.test/hd.jpg")
        self.assertNotIn("<", dados["explicacao"])
        self.assertIsNone(nasa.interpretar_apod({"title": ""}))

    def test_donki_classifica_e_detecta_destino(self):
        dados = nasa.interpretar_donki(DONKI, agora=date(2026, 11, 15))
        self.assertEqual(dados["nivel"], 3)                     # X-class / CME rápido
        self.assertEqual(dados["rotulo"], "severo")
        self.assertTrue(dados["afeta"]["marte"])
        self.assertTrue(dados["afeta"]["lua"])                  # X-class: a Lua não tem magnetosfera
        self.assertEqual([e["tipo"] for e in dados["eventos"]], ["CME", "FLR", "RBE"])
        self.assertNotIn("Activity ID", dados["eventos"][1]["resumo"])

    def test_donki_sem_eventos_fica_calmo(self):
        dados = nasa.interpretar_donki([], agora=date(2026, 11, 15))
        self.assertEqual((dados["nivel"], dados["rotulo"]), (0, "calmo"))
        self.assertEqual(dados["eventos"], [])

    def test_nome_do_gabinete_nao_conta_como_impacto(self):
        aviso = [{"messageType": "CME", "messageID": "C2", "messageIssueTime": "2026-11-15T00:00Z",
                  "messageBody": "## Summary:\nC-type CME. Analysis by the Moon to Mars Space Weather "
                                 "Analysis Office and heliospheric modeling.\n"}]
        dados = nasa.interpretar_donki(aviso, agora=date(2026, 11, 15))
        self.assertFalse(dados["afeta"]["lua"])
        self.assertFalse(dados["afeta"]["marte"])

    def test_radlab_calcula_estatisticas(self):
        dados = nasa.interpretar_radlab(RADLAB, "2022-04-01")
        self.assertEqual((dados["amostras"], dados["taxa_mediana"], dados["taxa_maxima"]), (3, 2.0, 6.0))
        self.assertEqual(dados["unidade"], "µGy/h")
        self.assertIsNone(nasa.interpretar_radlab({"columns": ["x"], "data": []}))
        self.assertIsNone(nasa.interpretar_radlab([{"absorbed_dose_rate": "NA"}]))

    def test_osdr_extrai_estudo_citavel(self):
        estudos = nasa.interpretar_osdr(OSDR)
        self.assertEqual(estudos[0]["acesso"], "OSD-310")
        self.assertEqual(estudos[0]["organismo"], "Rattus norvegicus")
        self.assertNotIn("<", estudos[0]["resumo"])
        self.assertTrue(estudos[0]["url"].startswith("https://osdr.nasa.gov/"))

    def test_fator_so_quando_o_destino_e_afectado(self):
        tempo = {"nivel": 2, "afeta": {"lua": False, "marte": True}}
        self.assertEqual(nasa.fator_exposicao(tempo, "marte"), 1.5)
        self.assertEqual(nasa.fator_exposicao(tempo, "lua"), 1.0)
        self.assertEqual(nasa.fator_exposicao({}, "marte"), 1.0)

    def test_perda_escala_apenas_a_exposicao(self):
        base = PERDAS["radiacao"][1]
        self.assertEqual(perda({}, "radiacao"), ("exposicao", base))
        self.assertEqual(perda({"ciencia": {"fator_exposicao": 2.0}}, "radiacao"), ("exposicao", base * 2))
        self.assertEqual(perda({"ciencia": {"fator_exposicao": 2.0}}, "sombra"), PERDAS["sombra"])

    def test_nota_espacial_liga_o_alerta_ao_incidente(self):
        indice = next(i for i, linha in enumerate(LINHAS["viagem"]) if linha[0] == "radiacao")
        estado = novo_estado()
        estado["destino"] = "marte"
        estado["ciencia"] = {"fator_exposicao": 2.0,
                             "tempo_espacial": {"rotulo": "severo",
                                                "eventos": [{"resumo": "CME em direcção a Marte."}]}}
        abrir_desafio(estado, "viagem", indice)
        self.assertIn("NASA DONKI", estado["mensagem"])
        self.assertIn("severo", estado["mensagem"])
        estado["mensagem"] = ""
        estado["ciencia"]["fator_exposicao"] = 1.0
        abrir_desafio(estado, "viagem", indice)
        self.assertNotIn("NASA DONKI", estado["mensagem"])


class Aquisicao(unittest.TestCase):
    def test_apod_recua_para_o_dia_anterior(self):
        with mock.patch.object(nasa, "_abrir_json", side_effect=[OSError("500"), APOD]) as abrir:
            dados = nasa._obter_apod()
        self.assertEqual(dados["data"], "2026-11-15")
        self.assertEqual(abrir.call_count, 2)
        self.assertIn("date=", abrir.call_args_list[0].args[0])

    def test_apod_sem_nenhum_dia_levanta_erro(self):
        with mock.patch.object(nasa, "_abrir_json", side_effect=OSError("sem rede")):
            with self.assertRaises(ValueError):
                nasa._obter_apod()


class Cache(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.cache = Path(self.pasta.name) / "data" / "nasa_cache.json"
        for patch in (mock.patch.object(nasa, "NASA_CACHE", self.cache),
                      mock.patch.dict(nasa._MEM, {"dados": None, "marca": None})):
            patch.start()
            self.addCleanup(patch.stop)

    def sincronizar(self, radlab=None):
        with mock.patch.object(nasa, "_obter_apod", return_value=nasa.interpretar_apod(APOD)), \
                mock.patch.object(nasa, "_obter_donki", return_value=nasa.interpretar_donki(DONKI)), \
                mock.patch.object(nasa, "_obter_radlab", return_value=radlab or nasa.interpretar_radlab(RADLAB)), \
                mock.patch.object(nasa, "_obter_estudos", return_value=nasa.interpretar_osdr(OSDR)):
            return nasa.sincronizar()

    def test_sincronizar_grava_e_carregar_le_sem_rede(self):
        estado = self.sincronizar()
        self.assertTrue(estado["activo"])
        self.assertEqual(estado["fontes"], {"apod": True, "donki": True, "radlab": True, "osdr": True})
        self.assertTrue(self.cache.exists())
        nasa._MEM.update(dados=None, marca=None)
        with mock.patch.object(nasa, "_abrir_json", side_effect=AssertionError("não devia usar a rede")):
            self.assertEqual(nasa.carregar()["radiacao"]["taxa_mediana"], 2.0)

    def test_fonte_em_baixo_nao_apaga_o_ultimo_valor_bom(self):
        self.sincronizar()
        bom = nasa.carregar()["radiacao"]
        with mock.patch.object(nasa, "_obter_radlab", side_effect=OSError("sem rede")):
            self.sincronizar()
        self.assertEqual(nasa.carregar()["radiacao"], bom)

    def test_referencia_e_pequena_deterministica_e_opcional(self):
        self.sincronizar()
        with mock.patch.object(nasa, "NASA_ACTIVO", True), mock.patch.object(nasa, "NASA_JOGO", False):
            self.assertEqual(nasa.referencia("marte", 7), nasa.referencia("marte", 7))
            ciencia = nasa.referencia("marte", 7)
            self.assertIn("apod", ciencia)
            self.assertIn("radiacao", ciencia)
            self.assertNotIn("fator_exposicao", ciencia)
            self.assertLess(len(json.dumps(ciencia)), 4000)
        with mock.patch.object(nasa, "NASA_ACTIVO", True), mock.patch.object(nasa, "NASA_JOGO", True):
            self.assertEqual(nasa.referencia("marte", 7)["fator_exposicao"], 2.0)
            self.assertEqual(nasa.referencia("lua", 7)["fator_exposicao"], 2.0)

    def test_endpoint_api_nasa_le_a_cache(self):
        self.sincronizar()
        estado, corpo, _ = api(None, None, "GET", "/api/nasa", {})
        self.assertEqual(estado, 200)
        self.assertTrue(corpo["fontes"]["radlab"])
        self.assertEqual(corpo["radiacao"]["taxa_mediana"], 2.0)

    def test_sem_cache_nao_inventa_dados(self):
        self.assertIsNone(nasa.referencia("lua", 1))
        self.assertEqual(nasa.estado_fonte()["activo"], False)

    def test_cache_corrompida_nao_rebenta(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.write_text("{isto não é json", encoding="utf-8")
        self.assertEqual(nasa.carregar(), {})

    def test_sincronizacao_total_falhada_nao_grava(self):
        with mock.patch.object(nasa, "_obter_apod", side_effect=OSError("sem rede")), \
                mock.patch.object(nasa, "_obter_donki", side_effect=OSError("sem rede")), \
                mock.patch.object(nasa, "_obter_radlab", side_effect=OSError("sem rede")), \
                mock.patch.object(nasa, "_obter_estudos", side_effect=OSError("sem rede")):
            with self.assertRaises(nasa.ErroNasa):
                nasa.sincronizar()
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
