import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch

from app.llm import Ollama


class ProtocoloOllama(unittest.TestCase):
    def test_json_e_reserva(self):
        pedidos = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                pedido = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                pedidos.append((self.path, pedido))
                accao = "segura" if len(pedidos) == 1 else "fora_do_catalogo"
                resposta = json.dumps({"message": {"content": json.dumps({"accao": accao})}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(resposta)))
                self.end_headers()
                self.wfile.write(resposta)

            def log_message(self, *_):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as servidor:
            Thread(target=servidor.serve_forever, daemon=True).start()
            try:
                ia = Ollama(activo=True)
                opcoes = {"segura": "Corrigir a trajectória", "risco": "Ignorar o desvio"}
                with patch("app.llm.OLLAMA", f"http://127.0.0.1:{servidor.server_port}"):
                    self.assertEqual(ia.interpretar("Corrigir a trajectória", opcoes, "Desvio"),
                                     ("segura", "ollama"))
                    self.assertEqual(ia.interpretar("Corrigir a trajectória", opcoes, "Desvio"),
                                     ("segura", "lexico"))
                rota, pedido = pedidos[0]
                self.assertEqual(rota, "/api/chat")
                self.assertFalse(pedido["stream"])
                self.assertEqual(pedido["format"]["properties"]["accao"]["enum"],
                                 ["segura", "risco", "indefinida"])
                self.assertEqual(json.loads(pedido["messages"][1]["content"])["sinal"], "Desvio")
            finally:
                servidor.shutdown()


if __name__ == "__main__":
    unittest.main()

