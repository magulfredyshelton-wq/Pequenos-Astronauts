from base64 import b64decode, b64encode
from binascii import Error as ErroBase64
from hashlib import sha256
import json
import math
import secrets
from time import time
from uuid import uuid4

from psycopg.types.json import Jsonb

from .catalogo import PERFIS, catalogo
from .config import BD
from .db import ligacao, transaccao
from .erros import Erro
from .llm import Ollama
from . import superficie, traducao
from .missao import (LOCAIS, Regra, aplicar, avisos_seguranca, dados_desafio, novo_estado, registar, relatorio,
                     resumo_carga)
from .neural import apresentar
from .privacidade import (CONTACTO, CONVERSA_LIVRE, FRASES, IDADE_CONSENTIMENTO, RETENCAO_MENSAGENS,
                          RETENCAO_VOZ, bloqueado, exigir_social, social_autorizado)

NIVEIS = ("cadete", "piloto", "comandante")
VALIDADE_PRESENCA = 12
VALIDADE_CONVITE = 1800
LIMITE_AUDIO = 480 * 1024
LIMITE_CONVERSA_AUDIO = 64 * 1024 * 1024
PAGINA_CONVERSA = 40
FORMATOS_AUDIO = {
    "audio/webm": (0, b"\x1a\x45\xdf\xa3"),
    "audio/ogg": (0, b"OggS"),
    "audio/mp4": (4, b"ftyp"),
}


def hash_(texto):
    return sha256(texto.encode()).hexdigest()


def serializar(valor):
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


class Jogo:
    def __init__(self, bd=BD, ia=None):
        self.bd = bd
        self.ia = ia if ia is not None else Ollama()

    def _identificar(self, conn, codigo, identidade):
        if isinstance(identidade, dict):
            jogador = conn.execute(
                "SELECT * FROM jogadores WHERE partida = %s AND conta_id = %s", (codigo, identidade["id"])
            ).fetchone()
        else:
            jogador = conn.execute(
                "SELECT * FROM jogadores WHERE partida = %s AND conta_id IS NULL AND segredo_hash = %s",
                (codigo, hash_(identidade)),
            ).fetchone()
        if jogador is None:
            if not identidade:
                raise Erro(401, "Entra numa partida primeiro.")
            raise Erro(403, "Só os membros da equipa têm acesso a esta partida.")
        if isinstance(identidade, dict) and not social_autorizado(identidade):
            self._exigir_equipa_autorizada(conn, codigo, identidade)
        return jogador

    def _exigir_equipa_autorizada(self, conn, codigo, conta):
        if conn.execute(
            "SELECT 1 FROM jogadores WHERE partida=%s OFFSET 1 LIMIT 1", (codigo,),
        ).fetchone():
            exigir_social(conta)

    def _novo_jogador(self, conn, codigo, nome, nivel, anfitriao, conta=None):
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 24:
            raise Erro(400, "Escreve um nome de astronauta com 1 a 24 caracteres.")
        if nivel not in NIVEIS:
            raise Erro(400, "Escolhe Cadete, Piloto ou Comandante.")
        token = secrets.token_urlsafe(32)
        id_ = uuid4().hex
        conn.execute("INSERT INTO jogadores(id, partida, nome, nivel, segredo_hash, anfitriao, conta_id) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (id_, codigo, nome.strip(), nivel, hash_(token), anfitriao, conta))
        conn.execute("INSERT INTO presencas VALUES (%s, %s, 0, 4.6)", (id_, time()))
        acesso = {"codigo": codigo, "jogador": id_}
        if conta is None:
            acesso["token"] = token
        return acesso

    def criar(self, nome, nivel, conta=None):
        with ligacao(self.bd) as conn, transaccao(conn):
            codigo = secrets.token_hex(6).upper()
            conn.execute("INSERT INTO partidas(codigo, revisao, estado) VALUES (%s, 0, %s)",
                         (codigo, Jsonb(novo_estado())))
            return self._novo_jogador(conn, codigo, nome, nivel, 1, conta)

    def _verificar_convite(self, conn, codigo, identidade):
        jogador = self._identificar(conn, codigo, identidade)
        if not jogador["anfitriao"]:
            raise Erro(403, "Só o anfitrião pode convidar no hangar.")
        partida = self._partida(conn, codigo, bloquear=True)
        self._verificar_vaga(conn, partida, 2 if isinstance(identidade, dict) else 3, lancada=403)

    def _verificar_vaga(self, conn, partida, limite=2, *, lancada=409):
        if partida["estado"]["fase"] != "preparacao_na_terra":
            raise Erro(lancada, "O lançamento já aconteceu.")
        total = conn.execute(
            "SELECT count(*) AS total FROM jogadores WHERE partida = %s", (partida["codigo"],),
        ).fetchone()["total"]
        if total >= limite:
            raise Erro(409, "A equipa já está completa.")

    def _limpar_convites(self, conn, codigo):
        conn.execute("DELETE FROM convites WHERE partida = %s", (codigo,))
        conn.execute("DELETE FROM convites_conta WHERE partida = %s", (codigo,))

    def convite(self, codigo, identidade):
        with ligacao(self.bd) as conn, transaccao(conn):
            self._verificar_convite(conn, codigo, identidade)
            conn.execute("DELETE FROM convites WHERE partida = %s", (codigo,))
            convite = secrets.token_urlsafe(18)
            conn.execute("INSERT INTO convites VALUES (%s, %s, %s)",
                         (hash_(convite), codigo, time() + VALIDADE_CONVITE))
            return {"convite": convite}

    def gerar_convite(self, codigo, conta):
        exigir_social(conta)
        return self.convite(codigo, conta)

    def usar_convite(self, codigo, convite, conta):
        exigir_social(conta)
        if not isinstance(convite, str) or not 20 <= len(convite) <= 128:
            raise Erro(400, "Indica um código válido.")
        with ligacao(self.bd) as conn, transaccao(conn):
            partida = self._partida(conn, codigo, bloquear=True)
            token = conn.execute(
                "SELECT 1 FROM convites WHERE partida=%s AND segredo_hash=%s AND expira_em>%s",
                (codigo, hash_(convite), time()),
            ).fetchone()
            if not token:
                raise Erro(404, "O código expirou ou já foi utilizado.")
            anfitriao = conn.execute(
                "SELECT c.id, c.idade FROM contas c "
                "JOIN jogadores j ON j.conta_id=c.id WHERE j.partida=%s AND j.anfitriao=1", (codigo,),
            ).fetchone()
            if not anfitriao or not social_autorizado(anfitriao) or bloqueado(conn, conta["id"], anfitriao["id"]):
                raise Erro(403, "Esta equipa não está disponível.")
            if anfitriao["id"] == conta["id"]:
                raise Erro(400, "Partilha o código com o teu colega.")
            self._verificar_vaga(conn, partida)
            jogador = self._novo_jogador(conn, codigo, conta["nome"], conta["nivel"], 0, conta["id"])
            conn.execute("UPDATE presencas SET vista_em=0 WHERE jogador=%s", (jogador["jogador"],))
            self._limpar_convites(conn, codigo)
            return jogador

    def entrar(self, codigo, convite, nome, nivel):
        if not isinstance(convite, str) or not 8 <= len(convite) <= 128:
            raise Erro(400, "O convite é obrigatório.")
        with ligacao(self.bd) as conn, transaccao(conn):
            partida = self._partida(conn, codigo, bloquear=True)
            registo = conn.execute(
                "SELECT 1 FROM convites WHERE partida = %s AND segredo_hash = %s AND expira_em > %s",
                (codigo, hash_(convite), time())
            ).fetchone()
            if not registo:
                raise Erro(403, "Convite inválido, usado ou expirado.")
            self._verificar_vaga(conn, partida, 3)
            criado = self._novo_jogador(conn, codigo, nome, nivel, 0)
            self._limpar_convites(conn, codigo)
            return criado

    def listar(self, conta):
        with ligacao(self.bd) as conn:
            filas = conn.execute(
                "SELECT p.codigo, p.estado, p.criada_em, j.id, j.anfitriao FROM jogadores j "
                "JOIN partidas p ON p.codigo = j.partida WHERE j.conta_id = %s ORDER BY p.criada_em DESC, p.codigo DESC",
                (conta["id"],),
            )
            resultado = []
            for fila in filas:
                estado = fila["estado"]
                resultado.append({"codigo": fila["codigo"], "jogador": fila["id"],
                                  "anfitriao": bool(fila["anfitriao"]), "fase": estado["fase"],
                                  "destino": estado["destino"], "desfecho": estado["desfecho"]})
            return resultado

    def associar_anterior(self, codigo, conta, segredo):
        if not isinstance(segredo, str) or not 1 <= len(segredo) <= 128:
            raise Erro(400, "A chave da partida anterior é inválida.")
        with ligacao(self.bd) as conn, transaccao(conn):
            self._partida(conn, codigo, bloquear=True)
            antigo = self._identificar(conn, codigo, segredo)
            if not social_autorizado(conta):
                self._exigir_equipa_autorizada(conn, codigo, conta)
            if conn.execute("SELECT 1 FROM jogadores WHERE partida = %s AND conta_id = %s",
                            (codigo, conta["id"])).fetchone():
                raise Erro(409, "Esta conta já pertence a esta equipa.")
            conn.execute("UPDATE jogadores SET conta_id = %s, nome = %s, nivel = %s, segredo_hash = %s WHERE id = %s",
                         (conta["id"], conta["nome"], conta["nivel"], hash_(secrets.token_urlsafe(32)), antigo["id"]))
        return {"codigo": codigo, "jogador": antigo["id"]}

    def ausente(self, codigo, identidade):
        with ligacao(self.bd) as conn, transaccao(conn):
            jogador = self._identificar(conn, codigo, identidade)
            partida = self._partida(conn, codigo, bloquear=True)
            conn.execute("UPDATE presencas SET vista_em = 0 WHERE jogador = %s", (jogador["id"],))
            estado = partida["estado"]
            votos = estado.get("votos_desafio", {})
            if jogador["id"] in votos or jogador["id"] in estado["votos"]:
                estado["espera_equipa"] = None
                votos.pop(jogador["id"], None)
                estado["votos"] = [id_ for id_ in estado["votos"] if id_ != jogador["id"]]
                conn.execute("UPDATE partidas SET revisao = revisao + 1, estado = %s WHERE codigo = %s",
                             (Jsonb(estado), codigo))
        return {"estado": "ausente"}

    def _partida(self, conn, codigo, *, bloquear=False):
        consulta = "SELECT * FROM partidas WHERE codigo = %s"
        if bloquear:
            consulta += " FOR NO KEY UPDATE"
        partida = conn.execute(consulta, (codigo,)).fetchone()
        if partida is None:
            raise Erro(404, "A partida não foi encontrada.")
        return partida

    def _jogadores(self, conn, codigo):
        agora = time()
        filas = conn.execute(
            "SELECT j.id, j.nome, j.nivel, j.anfitriao, p.vista_em, p.x, p.z, a.nickname "
            "FROM jogadores j JOIN presencas p ON p.jogador = j.id "
            "LEFT JOIN contas a ON a.id = j.conta_id WHERE j.partida = %s ORDER BY j.anfitriao DESC, j.id",
            (codigo,)
        ).fetchall()
        return [{"id": r["id"], "nome": r["nome"], "nivel": r["nivel"], "anfitriao": bool(r["anfitriao"]),
                 "nickname": r["nickname"],
                 "ligado": agora - r["vista_em"] <= VALIDADE_PRESENCA, "x": r["x"], "z": r["z"]}
                for r in filas]

    def _vista(self, codigo, revisao, estado, jogador, jogadores):
        publico = {k: v for k, v in estado.items()
                   if k not in {"neural", "neural_r1", "reservas_iniciais", "sinal", "plano", "semente"}}
        publico["relatorio"] = relatorio(estado)
        publico["avisos_seguranca"] = avisos_seguranca(estado)
        publico["desafio"] = dados_desafio(estado, jogador["nivel"])
        ligados = {membro["id"] for membro in jogadores if membro["ligado"]}
        publico["votos_desafio"] = {id_: opcao for id_, opcao in estado.get("votos_desafio", {}).items()
                                    if id_ in ligados}
        publico["carga_resumo"] = resumo_carga(estado)
        publico["duracao_horas"] = PERFIS[estado["destino"]]["horas"] if estado["destino"] else 0
        publico["tripulacao"] = apresentar(estado)
        publico["superficie"] = superficie.publico(estado)
        return {"codigo": codigo, "revisao": revisao, "eu": jogador["id"], "nivel": jogador["nivel"],
                "anfitriao": bool(jogador["anfitriao"]), "jogadores": jogadores, "estado": publico}

    def ver(self, codigo, token, posicao=None, cursor=None):
        with ligacao(self.bd) as conn, transaccao(conn):
            jogador = self._identificar(conn, codigo, token)
            if posicao is None:
                conn.execute("UPDATE presencas SET vista_em = %s WHERE jogador = %s", (time(), jogador["id"]))
            else:
                x, z = posicao
                if (type(x) not in (int, float) or type(z) not in (int, float)
                        or not math.isfinite(x) or not math.isfinite(z) or abs(x) > 10.4 or abs(z) > 6.8):
                    raise Erro(400, "A posição está fora do hangar.")
                conn.execute("UPDATE presencas SET vista_em = %s, x = %s, z = %s WHERE jogador = %s",
                             (time(), x, z, jogador["id"]))
            partida = self._partida(conn, codigo)
            if superficie.acabou(partida["estado"], jogador["id"]):  # traje sem oxigénio: regresso de emergência
                partida = self._partida(conn, codigo, bloquear=True)
                if superficie.expirar(partida["estado"], jogador["id"]):
                    registar(partida["estado"], superficie.MENSAGEM_EMERGENCIA, "alerta")
                    partida["revisao"] += 1
                    conn.execute("UPDATE partidas SET revisao = %s, estado = %s WHERE codigo = %s",
                                 (partida["revisao"], Jsonb(partida["estado"]), codigo))
            vista = self._vista(codigo, partida["revisao"], partida["estado"],
                               jogador, self._jogadores(conn, codigo))
            if isinstance(token, dict):
                vista["conversa"] = self._modo_conversa(conn, codigo)
                if cursor is not None:
                    vista["mensagens"] = self._mensagens(conn, codigo, vista["conversa"], cursor)
            return vista

    def _modo_conversa(self, conn, codigo):
        membros = conn.execute(
            "SELECT c.id, c.idade FROM contas c "
            "JOIN jogadores j ON j.conta_id=c.id WHERE j.partida=%s", (codigo,),
        ).fetchall()
        if len(membros) != 2 or not all(social_autorizado(m) for m in membros):
            return "desligada"
        if bloqueado(conn, membros[0]["id"], membros[1]["id"]):
            return "desligada"
        if CONVERSA_LIVRE and all(m["idade"] >= 15 for m in membros):
            return "livre"
        return "frases"

    def moderar(self, codigo, conta, tipo, corpo):
        with ligacao(self.bd) as conn, transaccao(conn):
            jogador = self._identificar(conn, codigo, conta)
            self._partida(conn, codigo, bloquear=True)
            outro = conn.execute(
                "SELECT id, conta_id FROM jogadores WHERE partida=%s AND id<>%s AND conta_id IS NOT NULL",
                (codigo, jogador["id"]),
            ).fetchone()
            if not outro:
                raise Erro(404, "Não há um colega nesta partida.")
            alvo = outro["conta_id"]
            if tipo == "bloquear":
                conn.execute("INSERT INTO bloqueios VALUES (%s,%s) ON CONFLICT DO NOTHING", (conta["id"], alvo))
                return {"bloqueado": True}
            motivo, mensagem = corpo.get("motivo"), corpo.get("mensagem")
            if motivo not in ("conduta", "contacto", "mensagem"):
                raise Erro(400, "Escolhe um motivo válido.")
            if mensagem is not None:
                if type(mensagem) is not int or not 1 <= mensagem < 2**63 or not conn.execute(
                    "SELECT 1 FROM mensagens WHERE id=%s AND partida=%s AND jogador=%s",
                    (mensagem, codigo, outro["id"]),
                ).fetchone():
                    raise Erro(404, "A mensagem já não está disponível.")
            conn.execute(
                "INSERT INTO denuncias(partida,autor,alvo,mensagem,motivo) VALUES (%s,%s,%s,%s,%s)",
                (codigo, conta["id"], alvo, mensagem, motivo),
            )
            return {"registada": True}

    def mensagens(self, codigo, conta, depois, antes=None):
        with ligacao(self.bd) as conn:
            self._identificar(conn, codigo, conta)
            return self._mensagens(conn, codigo, self._modo_conversa(conn, codigo), depois, antes)

    def _mensagens(self, conn, codigo, modo, depois, antes=None):
        if modo == "desligada":
            return []
        campos = (
            "SELECT m.id, m.jogador, j.nome, a.nickname, m.enviada_em, m.texto, m.formato "
            "FROM mensagens m JOIN jogadores j ON j.id = m.jogador "
            "LEFT JOIN contas a ON a.id = j.conta_id "
            "WHERE m.partida = %s AND m.enviada_em > %s AND "
            "(m.audio IS NULL OR m.enviada_em > %s)"
        )
        agora = int(time())
        parametros = (codigo, agora - RETENCAO_MENSAGENS, agora - RETENCAO_VOZ)
        if modo == "frases":
            campos += " AND m.formato IS NULL AND m.texto = ANY(%s)"
            parametros += (list(FRASES.values()),)
        if depois is not None:
            return conn.execute(
                campos + " AND m.id > %s ORDER BY m.id LIMIT %s", parametros + (depois, PAGINA_CONVERSA),
            ).fetchall()
        if antes is not None:
            campos += " AND m.id < %s"
            parametros += (antes,)
        filas = conn.execute(campos + " ORDER BY m.id DESC LIMIT %s", parametros + (PAGINA_CONVERSA,)).fetchall()
        return list(reversed(filas))

    def enviar_mensagem(self, codigo, conta, corpo):
        chave = corpo.get("chave")
        if not isinstance(chave, str) or not 8 <= len(chave) <= 80:
            raise Erro(400, "Identificador da mensagem inválido.")
        agora = int(time())
        with ligacao(self.bd) as conn, transaccao(conn):
            jogador = self._identificar(conn, codigo, conta)["id"]
            self._partida(conn, codigo, bloquear=True)
            modo = self._modo_conversa(conn, codigo)
            if modo == "desligada" or (modo == "frases" and corpo.get("tipo") != "frase"):
                raise Erro(403, "Usa as opções de conversa autorizadas para a equipa.")
            texto, formato, audio = self._conteudo_mensagem(corpo)
            anterior = conn.execute(
                "SELECT id, texto, formato, audio FROM mensagens WHERE partida = %s AND jogador = %s AND chave = %s",
                (codigo, jogador, chave),
            ).fetchone()
            if anterior:
                if (anterior["texto"], anterior["formato"], anterior["audio"]) != (texto, formato, audio):
                    raise Erro(409, "Este identificador já foi usado para outra mensagem.")
                return {"id": anterior["id"]}
            recentes = conn.execute(
                "SELECT count(*) AS total FROM mensagens WHERE partida = %s AND jogador = %s AND enviada_em >= %s",
                (codigo, jogador, agora - 10),
            ).fetchone()["total"]
            if recentes >= 10:
                raise Erro(429, "Espera um pouco antes de enviares outra mensagem.")
            if audio is not None:
                usados = conn.execute(
                    "SELECT coalesce(sum(octet_length(audio)), 0) AS total FROM mensagens "
                    "WHERE partida = %s AND enviada_em > %s", (codigo, agora - RETENCAO_VOZ),
                ).fetchone()["total"]
                if usados + len(audio) > LIMITE_CONVERSA_AUDIO:
                    raise Erro(409, "Esta partida atingiu o limite de gravações. Podes continuar por texto.")
            fila = conn.execute(
                "INSERT INTO mensagens(partida, jogador, chave, enviada_em, texto, formato, audio) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (codigo, jogador, chave, agora, texto, formato, audio),
            ).fetchone()
            return fila

    @staticmethod
    def _conteudo_mensagem(corpo):
        if corpo.get("tipo") == "frase":
            id_ = corpo.get("frase")
            if not isinstance(id_, str) or id_ not in FRASES:
                raise Erro(400, "Escolhe uma frase disponível.")
            return FRASES[id_], None, None
        if corpo.get("tipo") == "texto":
            texto = corpo.get("texto")
            if not isinstance(texto, str) or not 1 <= len(texto.strip()) <= 500:
                raise Erro(400, "Escreve uma mensagem com até 500 caracteres.")
            if CONTACTO.search(texto):
                raise Erro(400, "Retira contactos pessoais e links da mensagem.")
            return texto.strip(), None, None
        if corpo.get("tipo") != "audio":
            raise Erro(400, "Tipo de mensagem desconhecido.")
        formato, codificado = corpo.get("formato"), corpo.get("audio")
        if not isinstance(formato, str) or formato not in FORMATOS_AUDIO or not isinstance(codificado, str):
            raise Erro(400, "Formato de áudio inválido.")
        if len(codificado) > 4 * ((LIMITE_AUDIO + 2) // 3):
            raise Erro(413, "A gravação é demasiado grande.")
        try:
            audio = b64decode(codificado, validate=True)
        except (ErroBase64, ValueError) as erro:
            raise Erro(400, "A gravação é inválida.") from erro
        if len(audio) > LIMITE_AUDIO:
            raise Erro(413, "A gravação é demasiado grande.")
        inicio, assinatura = FORMATOS_AUDIO[formato]
        if len(audio) < 16 or not audio.startswith(assinatura, inicio):
            raise Erro(400, "A gravação é inválida.")
        return None, formato, audio

    def audio_mensagem(self, codigo, conta, id_):
        with ligacao(self.bd) as conn:
            self._identificar(conn, codigo, conta)
            if self._modo_conversa(conn, codigo) != "livre":
                raise Erro(403, "A equipa não tem acesso à voz.")
            fila = conn.execute(
                "SELECT formato, audio FROM mensagens WHERE partida=%s AND id=%s AND audio IS NOT NULL "
                "AND enviada_em>%s", (codigo, id_, int(time()) - RETENCAO_VOZ),
            ).fetchone()
            if not fila:
                raise Erro(404, "A gravação não foi encontrada.")
            return {"formato": fila["formato"], "audio": b64encode(fila["audio"]).decode("ascii")}

    def interpretar(self, codigo, token, texto, revisao, lang=None):
        if not isinstance(texto, str) or not 1 <= len(texto.strip()) <= 500:
            raise Erro(400, "Escreve uma resposta com até 500 caracteres.")
        vista = self.ver(codigo, token)
        desafio = vista["estado"]["desafio"]
        if not desafio or vista["revisao"] != revisao:
            raise Erro(409, "O desafio mudou. Consulta a partida actualizada.")
        if vista["nivel"] != "comandante":
            raise Erro(403, "Usa as opções disponíveis para o teu nível.")
        if CONTACTO.search(texto):
            raise Erro(400, "Retira contactos pessoais e links antes de interpretar o plano.")
        opcoes, sinal = desafio["opcoes"], desafio["sinal"]
        if lang == "en":  # o comandante escreveu em inglês: compara com as manobras em inglês
            opcoes, sinal = {k: traducao.texto(v) for k, v in opcoes.items()}, traducao.texto(sinal)
        escolha, metodo = self.ia.interpretar(texto.strip(), opcoes, sinal)
        return {"opcao": escolha, "rotulo": desafio["opcoes"].get(escolha), "metodo": metodo,
                "revisao": revisao}

    def comando(self, codigo, token, comando, acao, valor, revisao):
        if (not isinstance(comando, str) or not 8 <= len(comando) <= 80
                or not isinstance(acao, str) or type(revisao) is not int or revisao < 0):
            raise Erro(400, "Comando ou revisão inválidos.")
        pedido = serializar([acao, valor, revisao])
        with ligacao(self.bd) as conn, transaccao(conn):
            jogador = self._identificar(conn, codigo, token)
            partida = self._partida(conn, codigo, bloquear=True)
            anterior = conn.execute(
                "SELECT pedido, resposta FROM comandos WHERE partida = %s AND jogador = %s AND id = %s",
                (codigo, jogador["id"], comando)
            ).fetchone()
            if anterior:
                if anterior["pedido"] != pedido:
                    raise Erro(409, "Este identificador já foi usado para outro comando.")
                return anterior["resposta"]

            if partida["revisao"] != revisao:
                raise Erro(409, "A partida mudou. Confirma o estado antes de repetir a acção.")
            conn.execute("UPDATE presencas SET vista_em = %s WHERE jogador = %s", (time(), jogador["id"]))
            jogadores = self._jogadores(conn, codigo)
            ligados = {j["id"] for j in jogadores if j["ligado"]}
            estado = partida["estado"]
            # Na superfície, a presença dá a distância à nave em metros; o motor valida a proximidade.
            presente = next(j for j in jogadores if j["id"] == jogador["id"])
            agora = time()
            posicao = presente["x"] * superficie.ESCALA if estado["pouso"] is not None else None
            if superficie.expirar(estado, jogador["id"], agora):  # o oxigénio do traje acabou entretanto
                registar(estado, superficie.MENSAGEM_EMERGENCIA, "alerta")
                if acao in (*superficie.ACOES, "explorar"):
                    acao = None
            evento_anterior = estado["historico"][-1] if estado["historico"] else None
            try:
                if acao is not None:
                    aplicar(estado, acao, valor, jogador, ligados, len(jogadores),
                            cooperativa=jogador['conta_id'] is not None, posicao=posicao, agora=agora)
            except Regra as erro:
                raise Erro(400, str(erro)) from erro

            evento = estado["historico"][-1] if estado["historico"] else None
            if len(jogadores) > len(ligados) and evento is not None and evento is not evento_anterior:
                evento["a_solo"] = True
                registo = estado.setdefault("progresso_a_solo", [])
                registo.append({"revisao": revisao + 1, "horas": evento["horas"], "mensagem": evento["mensagem"]})
                estado["progresso_a_solo"] = registo[-10:]
            if acao == "lancar":
                self._limpar_convites(conn, codigo)
            nova = revisao + 1
            vista = self._vista(codigo, nova, estado, jogador, jogadores)
            conn.execute("UPDATE partidas SET revisao = %s, estado = %s WHERE codigo = %s", (nova, Jsonb(estado), codigo))
            conn.execute("INSERT INTO comandos(partida,jogador,id,pedido,resposta) VALUES (%s, %s, %s, %s, %s)",
                         (codigo, jogador["id"], comando, pedido, Jsonb(vista)))
            return vista

