"""Cada mensagem que o servidor pode enviar tem tradução inglesa (evita português no modo inglês)."""
import ast
import glob
import unittest

from app import catalogo, traducao
from app.catalogo import LINHAS
from app.missao import CONCEITOS

CHAMADAS = {"Erro", "exigir", "registar", "fechar_missao", "Regra", "append", "falha"}
IGNORAR = ("SELECT", "UPDATE", "INSERT", "DELETE", "CREATE", "ALTER", "%", "{}")
INTERNAS = {": só são aceites URLs https", " registos válidos", " é inválido.", "Instala requirements-neural.txt ou usa ASTRO_CEREBRO=leve."}


def mensagens():
    vistas = {}
    for caminho in sorted(glob.glob("app/*.py")):
        if caminho.endswith(("catalogo_en.py", "traducao.py", "cenarios.py", "eva.py", "email.py", "db.py", "config.py")):
            continue
        with open(caminho, encoding="utf-8") as ficheiro:
            arvore = ast.parse(ficheiro.read())
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            nome = getattr(no.func, "id", getattr(no.func, "attr", ""))
            if nome not in CHAMADAS:
                continue
            for s in [*no.args, *(k.value for k in no.keywords)]:  # só argumentos directos; concatenações têm teste próprio
                if isinstance(s, ast.JoinedStr):
                    texto = "".join(v.value if isinstance(v, ast.Constant) else "7" for v in s.values)
                elif isinstance(s, ast.Constant) and isinstance(s.value, str):
                    texto = s.value
                else:
                    continue
                if len(texto) >= 12 and " " in texto and not texto.lstrip().upper().startswith(IGNORAR) and texto not in INTERNAS:
                    vistas.setdefault(texto.strip(), caminho)
    return vistas


class Traducao(unittest.TestCase):
    def test_todas_as_mensagens_do_servidor_tem_ingles(self):
        em_falta = [f"{c}: {s}" for s, c in mensagens().items() if traducao.texto(s) == s]
        self.assertEqual(em_falta, [])

    def test_catalogo_e_incidentes(self):
        for linhas in LINHAS.values():
            for linha in linhas:
                for campo in linha[1:]:
                    self.assertNotEqual(traducao.texto(campo), campo, campo)
                self.assertNotEqual(traducao.texto(CONCEITOS[linha[0]]), CONCEITOS[linha[0]])
        cat = traducao.resposta(catalogo.catalogo())
        self.assertEqual(cat["destinos"]["lua"]["nome"], "Moon")
        self.assertEqual(cat["carga"]["agua"]["nome"], "Water")
        self.assertEqual(cat["montagem"][0][1], "Install power and test the battery")

    def test_textos_compostos_e_dados_do_jogador(self):
        self.assertEqual(traducao.texto("Destino seleccionado: Marte."), "Destination selected: Mars.")
        self.assertIn("co₂ filter", traducao.texto(CONCEITOS["co2"] + " Usaste filtro de co₂ da carga."))
        self.assertIn("emergency plan", traducao.texto("A reserva de oxigénio acabou. O controlo de missão activou o plano de emergência."))
        self.assertEqual(traducao.texto("Avanço aprovado por 1 de 2 jogadores ligados."), "Advance approved by 1 of 2 connected players.")
        vista = traducao.resposta({"jogadores": [{"nome": "Água", "nickname": "Comida"}], "estado": {"mensagem": "Manifesto de carga actualizado."}})
        self.assertEqual(vista["jogadores"][0], {"nome": "Água", "nickname": "Comida"})
        self.assertEqual(vista["estado"]["mensagem"], "Cargo manifest updated.")


    def test_vista_da_partida_com_anfitriao_e_traduzida(self):
        # a vista traz «anfitriao» no topo, como um jogador; o estado tem de ser traduzido na mesma
        vista = traducao.resposta({"codigo": "ABC", "anfitriao": True, "eu": "x", "jogadores": [{"nome": "Lua", "anfitriao": True}],
                                   "estado": {"mensagem": "Manifesto de carga actualizado.",
                                              "desafio": {"id": "impacto", "titulo": "Impacto no painel",
                                                          "opcoes": {"segura": "Reduzir consumos e estabilizar a energia"}}}})
        self.assertEqual(vista["estado"]["mensagem"], "Cargo manifest updated.")
        self.assertEqual(vista["estado"]["desafio"]["titulo"], "Panel impact")
        self.assertEqual(vista["estado"]["desafio"]["opcoes"]["segura"], "Cut power use and stabilise the energy")
        self.assertEqual(vista["jogadores"][0]["nome"], "Lua")

if __name__ == "__main__":
    unittest.main()
