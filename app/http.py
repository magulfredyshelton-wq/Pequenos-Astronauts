from http.cookies import CookieError, SimpleCookie
import json
import os
from random import Random
import re
from urllib.parse import parse_qs

from . import cenarios, eva, nasa
from .catalogo import catalogo
from .config import IA_ACTIVA, MODELO, PORTA
from .contas import COOKIE, DOMINIO, DURACAO_SESSAO, IDADE_MINIMA, PUBLICO
from .neural_r1 import R1_ACTIVO
from .privacidade import FRASES
from .servico import LIMITE_AUDIO, Erro


def negar_constante(valor):
    raise ValueError("Número inválido: " + valor)


def cookie_token(cookies):
    try:
        valor = SimpleCookie(cookies).get(COOKIE)
        return valor.value if valor else ""
    except CookieError:
        return ""


def cookie_sessao(token, duracao):
    seguro = "; Secure" if DOMINIO.scheme == "https" else ""
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={duracao}{seguro}"


def validar_post(tipo, origem):
    origens = {PUBLICO}
    if DOMINIO.scheme == "http":  # demo local
        origens.add(os.getenv("ASTRO_DEV_ORIGIN", "http://localhost:5173"))
        origens.update({"http://127.0.0.1:5173", f"http://localhost:{PORTA}", f"http://127.0.0.1:{PORTA}"})
    if origem and origem not in origens:
        raise Erro(403, "O pedido veio de outra origem.")
    if tipo.partition(";")[0].strip().lower() != "application/json":
        raise Erro(415, "Envia um pedido em JSON.")


def limite_pedido(caminho):
    if re.fullmatch(r"/api/partidas/[^/]+/mensagens/?", caminho):
        return 4 * ((LIMITE_AUDIO + 2) // 3) + 1024
    return 32768


def id_mensagem(valor):
    if not re.fullmatch(r"[0-9]{1,19}", valor) or int(valor) > 2**63 - 1:
        raise Erro(400, "Identificador de mensagem inválido.")
    return int(valor)


def api(jogo, contas, metodo, caminho, corpo, cookies="", ip="", autorizacao="", legado=False, consulta="", sandbox=None):
    partes = caminho.strip("/").split("/")
    token = cookie_token(cookies)
    if metodo == "GET" and caminho == "/api/saude":
        return 200, {"estado": "ok", "ollama_configurado": IA_ACTIVA, "modelo": MODELO,
                     "cerebro": "r1" if R1_ACTIVO else "leve"}, {}
    if metodo == "GET" and caminho == "/api/catalogo":
        return 200, {**catalogo(), "frases": FRASES}, {}
    if metodo == "GET" and caminho == "/api/eva":
        registos = eva.carregar()
        amostra = [eva.referencia(r) for r in Random().sample(registos, min(3, len(registos)))]
        return 200, {**eva.estado_fonte(), "amostra": amostra}, {}
    if metodo == "GET" and caminho == "/api/nasa":
        return 200, nasa.estado_fonte(), {}
    if partes[:2] == ["api", "conta"]:
        return api_conta(contas, metodo, caminho, corpo, token, ip)
    if partes[:2] == ["api", "sandbox"] and sandbox is not None:
        return api_sandbox(sandbox, contas, metodo, caminho, corpo, token, consulta)

    if metodo == "POST" and caminho == "/api/convites/usar":
        conta = contas.verificar(token)
        contas.limites.verificar(("usar-convite", conta["id"]), 12, 60)
        codigo, segredo = corpo.get("codigo"), corpo.get("convite")
        if not isinstance(codigo, str) or not re.fullmatch(r"[A-Fa-f0-9]{12}", codigo):
            raise Erro(400, "O código de partida é inválido.")
        return 201, jogo.usar_convite(codigo.upper(), segredo, conta), {}

    if partes[:2] != ["api", "partidas"] or not 2 <= len(partes) <= 5:
        raise Erro(404, "Endereço desconhecido.")
    conta = None
    if legado and not token:
        identidade = autorizacao.removeprefix("Bearer ") if autorizacao.startswith("Bearer ") else ""
    else:
        conta = identidade = contas.verificar(token)
    nome = conta["nome"] if conta else corpo.get("nome")
    nivel = conta["nivel"] if conta else corpo.get("nivel")
    conta_id = conta["id"] if conta else None
    if len(partes) == 2:
        if metodo == "GET" and conta:
            return 200, jogo.listar(conta), {}
        if metodo == "POST":
            return 201, jogo.criar(nome, nivel, conta_id), {}
    codigo = partes[2].upper() if len(partes) >= 3 else ""
    if len(partes) == 3 and metodo == "GET":
        return 200, jogo.ver(codigo, identidade), {}
    if conta and metodo == "GET":
        if len(partes) == 4 and partes[3] == "mensagens":
            parametros = parse_qs(consulta, keep_blank_values=True, max_num_fields=8)
            if "depois" in parametros and "antes" in parametros:
                raise Erro(400, "Escolhe um único cursor de mensagens.")
            depois = id_mensagem(parametros["depois"][0]) if "depois" in parametros else None
            antes = id_mensagem(parametros["antes"][0]) if "antes" in parametros else None
            return 200, jogo.mensagens(codigo, conta, depois, antes), {}
        if len(partes) == 5 and partes[3] == "audio":
            return 200, jogo.audio_mensagem(codigo, conta, id_mensagem(partes[4])), {}
    if len(partes) == 4 and metodo == "POST":
        acao = partes[3]
        if acao == "mensagens" and conta:
            return 201, jogo.enviar_mensagem(codigo, conta, corpo), {}
        if acao == "convites":
            if conta:
                contas.limites.verificar(("convite", conta["id"]), 12, 60)
                if corpo:
                    raise Erro(400, "Usa um código privado de convite.")
                return 201, jogo.gerar_convite(codigo, conta), {}
            if legado:
                return 201, jogo.convite(codigo, identidade), {}
        if acao == "entrar" and legado and not conta:
            return 201, jogo.entrar(codigo, corpo.get("convite"), nome, nivel), {}
        if acao in ("denunciar", "bloquear") and conta:
            contas.limites.verificar((acao, conta["id"]), 12, 3600)
            return 200, jogo.moderar(codigo, conta, acao, corpo), {}
        if acao == "associar" and conta:
            return 200, jogo.associar_anterior(codigo, conta, corpo.get("segredo")), {}
        if acao == "presenca":
            cursor = corpo.get("mensagens_depois")
            if cursor is not None and (type(cursor) is not int or not 0 <= cursor < 2**63):
                raise Erro(400, "Identificador de mensagem inválido.")
            return 200, jogo.ver(codigo, identidade, (corpo.get("x"), corpo.get("z")), cursor), {}
        if acao == "ausente":
            return 200, jogo.ausente(codigo, identidade), {}
        if acao == "comandos":
            return 200, jogo.comando(codigo, identidade, corpo.get("id"), corpo.get("acao"),
                                     corpo.get("valor"), corpo.get("revisao")), {}
        if acao == "interpretar":
            return 200, jogo.interpretar(codigo, identidade, corpo.get("texto"), corpo.get("revisao"),
                                         corpo.get("lang")), {}
    raise Erro(404, "Operação desconhecida.")


def api_sandbox(sandbox, contas, metodo, caminho, corpo, token, consulta=""):
    if metodo == "GET" and caminho == "/api/sandbox/cenarios":
        q = parse_qs(consulta, keep_blank_values=True, max_num_fields=6)
        um = lambda k, d: (q.get(k) or [d])[0]
        return 200, cenarios.pacote(um("destino", "lua").lower(), um("semente", "demo"), um("lang", "en").lower()), {}
    if metodo == "GET" and caminho == "/api/sandbox/ranking":
        return 200, sandbox.ranking(), {}
    conta = contas.verificar(token)
    if metodo == "GET" and caminho == "/api/sandbox/resultados":
        return 200, sandbox.listar(conta), {}
    if metodo == "POST" and caminho == "/api/sandbox/resultados":
        contas.limites.verificar(("sandbox", conta["id"]), 60, 3600)
        resposta = sandbox.guardar(conta, corpo)
        return (201 if resposta["guardado"] else 200), resposta, {}
    raise Erro(404, "Operação desconhecida.")


def api_conta(contas, metodo, caminho, corpo, token, ip):
    if metodo == "GET" and caminho == "/api/conta":
        return 200, contas.verificar(token), {}
    if metodo == "GET" and caminho == "/api/conta/politica":
        return 200, {"idade_minima": IDADE_MINIMA}, {}
    if metodo == "POST":
        if caminho == "/api/conta/entrar":  # entrada livre: só nome e idade
            perfil, sessao = contas.entrar(corpo.get("nome"), corpo.get("idade"), ip)
            return 200, perfil, {"Set-Cookie": cookie_sessao(sessao, DURACAO_SESSAO)}
        if caminho == "/api/conta/nickname":
            return 200, contas.definir_nickname(contas.verificar(token), corpo.get("nickname")), {}
        if caminho == "/api/conta/sair":
            contas.sair(token)
            return 200, {"estado": "desligada"}, {"Set-Cookie": cookie_sessao("", 0)}
    raise Erro(404, "Operação desconhecida.")


def ler_json(bruto, limite=32768):
    if len(bruto) > limite:
        raise Erro(413, "Pedido demasiado grande.")
    try:
        dados = json.loads(bruto or b"{}", parse_constant=negar_constante)
    except (ValueError, UnicodeError, RecursionError) as erro:
        raise Erro(400, "O pedido deve conter JSON válido.") from erro
    if not isinstance(dados, dict):
        raise Erro(400, "O pedido deve conter um objecto JSON.")
    return dados
