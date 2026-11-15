from pathlib import Path
import os

BACKEND = Path(__file__).resolve().parents[1]


def carregar():
    caminho = BACKEND / ".env"
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
            nome, sep, valor = linha.partition("=")
            if sep and nome.strip() and not nome.lstrip().startswith("#"):
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] in ("'", '"') and valor[-1] == valor[0]:
                    valor = valor[1:-1]
                os.environ.setdefault(nome.strip(), valor)


carregar()
# A matriz LIF é pequena. Evita abrir vários trabalhadores de BLAS por cada passo.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
BD = os.getenv("ASTRO_DATABASE_URL", "").strip()
HOST = os.getenv("ASTRO_HOST", "127.0.0.1")
PORTA = int(os.getenv("ASTRO_PORT", "8000"))
# O frontend pode estar dentro do repositório do backend (./frontend) ou ao lado dele (../frontend).
_FRONTEND_DENTRO = BACKEND / "frontend"
FRONTEND = Path(os.getenv("ASTRO_FRONTEND", str(
    _FRONTEND_DENTRO if _FRONTEND_DENTRO.is_dir() else BACKEND.parent / "frontend"))).resolve()
FRONTEND_2D = Path(os.getenv("ASTRO_FRONTEND_2D", str(BACKEND.parent / "frontend-2d" / "dist"))).resolve()
OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODELO = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
IA_ACTIVA = os.getenv("OLLAMA_ENABLED", "1") == "1"
TEMPO_IA = float(os.getenv("OLLAMA_TIMEOUT", "5"))
CEREBRO = os.getenv("ASTRO_CEREBRO", "auto").strip().lower()
if CEREBRO not in ("auto", "r1", "leve"):
    raise ValueError("ASTRO_CEREBRO deve ser auto, r1 ou leve.")

# Dados reais de EVA (NASA, EUA e Rússia). Ver app/eva.py.
EVA_ACTIVO = os.getenv("ASTRO_EVA", "1") == "1"
EVA_TTL_DIAS = int(os.getenv("ASTRO_EVA_TTL_DIAS", "7"))
EVA_CACHE = Path(os.getenv("ASTRO_EVA_CACHE", str(BACKEND / "data" / "eva_cache.json")))
_EVA_BASE = "https://data.nasa.gov/docs/legacy/Extra-vehicular_Activity_EVA_-_US_and_Russia/Extra-vehicular_Activity_EVA_-_US_and_Russia_rows"
EVA_URLS = os.getenv("ASTRO_EVA_URLS", "").replace(",", " ").split() or [
    _EVA_BASE + ".csv",
    _EVA_BASE + ".json",
    "https://data.nasa.gov/api/views/9kcy-zwvn/rows.csv?accessType=DOWNLOAD",
]

# Dados reais da NASA para a ciência da missão: APOD, DONKI, RadLab e OSDR. Ver app/nasa.py.
NASA_ACTIVO = os.getenv("ASTRO_NASA", "1") == "1"
# Chave gratuita de https://api.nasa.gov (DEMO_KEY tem limites baixos, mas serve para testar).
NASA_CHAVE = (os.getenv("NASA_API_KEY") or os.getenv("ASTRO_NASA_KEY") or "DEMO_KEY").strip() or "DEMO_KEY"
NASA_TTL_HORAS = int(os.getenv("ASTRO_NASA_TTL_HORAS", "6"))
NASA_CACHE = Path(os.getenv("ASTRO_NASA_CACHE", str(BACKEND / "data" / "nasa_cache.json")))
# Com 1, um alerta solar real aumenta o custo em exposição do incidente "radiacao"/"abrigo_marte".
# Desligado por omissão: as partidas continuam determinísticas e os testes não dependem de rede.
NASA_JOGO = os.getenv("ASTRO_NASA_JOGO", "0") == "1"
