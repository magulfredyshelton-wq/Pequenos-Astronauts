# Little Astronauts — estado em 16 Nov 2026

Esta pasta é a raiz do repositório: backend na raiz, frontend em `frontend/`.

## Correr
```
pip install -r requirements.txt
python migrate.py
python run.py
```
O backend encontra o frontend sozinho em `./frontend` (ou em `../frontend`, ou onde `ASTRO_FRONTEND` disser).

## Render
- Root Directory: vazio
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
- Variáveis: `ASTRO_DATABASE_URL` (Neon), `ASTRO_PUBLIC_URL` (endereço do site, sem `/` no fim), `OLLAMA_ENABLED=0`, `ASTRO_CEREBRO=leve`

## O que este pacote junta
| Parte | Origem |
|---|---|
| Frontend | O `frontend/` do zip Pequenos-Astronauts-Backend-API (versão pixel, sem Phaser). |
| Ciência NASA | Já vinha neste frontend (`cienciaNasa()` em `main.js`): aparece no botão NASA do lobby e no relatório final, com dados de `GET /api/nasa` e `relatorio.ciencia`. Não acrescentei nada aqui. |
| Entrada livre | Só nome e idade. Sem email, palavra-passe nem autorização. Sala + convite mantêm-se. `POST /api/conta/entrar {nome, idade}`; migração `008_entrada_livre.sql`. |
| `app/config.py` | Procura o frontend primeiro dentro do repositório. |
| `.gitignore` | Impede que o `.env` (senha da base de dados) vá para o GitHub. |

## Por resolver
- `test_traducao.test_todas_as_mensagens_do_servidor_tem_ingles` falha por duas mensagens internas de `app/nasa.py` sem inglês. Não afecta o jogo.
