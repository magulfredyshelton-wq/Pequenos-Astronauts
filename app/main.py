import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg import DataError, OperationalError
from starlette.concurrency import run_in_threadpool

from . import eva, nasa, traducao
from .config import EVA_ACTIVO, FRONTEND, FRONTEND_2D, NASA_ACTIVO
from .contas import Contas, validar_configuracao
from .db import migrar
from .http import api, ler_json, limite_pedido, validar_post
from .servico import Erro, Jogo
from .privacidade import limpar
from .sandbox import Sandbox

log = logging.getLogger(__name__)


async def manutencao(dsn):
    while True:
        try:
            await run_in_threadpool(limpar, dsn)
        except OperationalError:
            log.warning("Limpeza adiada por indisponibilidade do PostgreSQL.")
        await asyncio.sleep(300)


def criar_app(jogo=None, contas=None, *, legado=False):
    jogo = jogo if jogo is not None else Jogo()
    contas = contas if contas is not None else Contas(jogo.bd)
    sandbox = Sandbox(jogo.bd)

    @asynccontextmanager
    async def vida(_):
        validar_configuracao()
        await run_in_threadpool(migrar, jogo.bd)
        tarefa = asyncio.create_task(manutencao(jogo.bd))
        # Dados EVA da NASA: sincroniza em segundo plano. O jogo arranca mesmo sem rede.
        sincronizacao_eva = (asyncio.create_task(run_in_threadpool(eva.sincronizar_se_preciso))
                             if EVA_ACTIVO else None)
        # Ciência da missão (APOD, DONKI, RadLab, OSDR): idem, em segundo plano e sem bloquear.
        sincronizacao_nasa = (asyncio.create_task(run_in_threadpool(nasa.sincronizar_se_preciso))
                              if NASA_ACTIVO else None)
        try:
            yield
        finally:
            tarefa.cancel()
            with suppress(asyncio.CancelledError):
                await tarefa

    app = FastAPI(title="Pequenos Astronautas", lifespan=vida)

    @app.api_route("/api/{caminho:path}", methods=["GET", "POST"])
    async def encaminhar(caminho: str, pedido: Request):
        # «X-Lang: en» pede a resposta em inglês; o jogo guarda e calcula tudo em português.
        ingles = pedido.headers.get("x-lang", "").lower() == "en"
        falha = lambda texto, estado: JSONResponse({"erro": traducao.texto(texto) if ingles else texto}, status_code=estado)
        try:
            dados = {}
            rota = "/api/" + caminho
            if pedido.method == "POST":
                validar_post(pedido.headers.get("content-type", ""), pedido.headers.get("origin", ""))
                bruto = bytearray()
                limite = limite_pedido(rota)
                async for bloco in pedido.stream():
                    bruto.extend(bloco)
                    if len(bruto) > limite:
                        raise Erro(413, "Pedido demasiado grande.")
                dados = ler_json(bruto, limite)
            status, resposta, cabecalhos = await run_in_threadpool(
                api, jogo, contas, pedido.method, rota, dados,
                pedido.headers.get("cookie", ""), pedido.client.host if pedido.client else "",
                pedido.headers.get("authorization", ""), legado, consulta=pedido.url.query, sandbox=sandbox,
            )
            if ingles:
                resposta = traducao.resposta(resposta)
            return JSONResponse(resposta, status_code=status, headers={**cabecalhos, "Cache-Control": "no-store",
                                                                     "Referrer-Policy": "no-referrer",
                                                                     "X-Content-Type-Options": "nosniff"})
        except Erro as erro:
            return falha(str(erro), erro.status)
        except OperationalError:
            return falha("A base de dados está temporariamente indisponível.", 503)
        except (ValueError, OverflowError, RecursionError, DataError):
            return falha("Os valores do pedido são inválidos.", 400)

    if FRONTEND_2D.is_dir():  # cliente 2D sandbox (build do Vite), em /jogo2d/
        app.mount("/jogo2d", StaticFiles(directory=FRONTEND_2D, html=True), name="jogo2d")
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


app = criar_app()
