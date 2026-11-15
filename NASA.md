# Dados reais da NASA no jogo

O jogo usa dados reais da NASA em duas camadas:

- `app/eva.py` — saídas extraveiculares reais (já existia).
- `app/nasa.py` — ciência da missão: APOD, DONKI, RadLab e OSDR.

As duas seguem a mesma regra: **a rede só é usada no arranque do servidor** (ou à mão),
nunca durante um comando de jogador. Os dados ficam numa cache em `backend/data/`, e o
jogo continua a funcionar sem cache e sem rede.

## O que cada API acrescenta

| API | Onde entra no jogo | O que o jogador vê |
| --- | --- | --- |
| **APOD** | `estado["ciencia"]["apod"]`, no lançamento e no relatório | A imagem do dia como "fotografia de briefing" da missão, com data e crédito |
| **DONKI** | `estado["ciencia"]["tempo_espacial"]`; incidentes `radiacao` e `abrigo_marte` | Nível de meteorologia espacial (calmo/elevado/severo), eventos reais e se atingem Lua/Marte |
| **RadLab** | `estado["ciencia"]["radiacao"]` | Dose absorvida real medida na ISS (mediana, p95, máximo, instrumento e dia) |
| **OSDR** | `estado["ciencia"]["estudo"]`, no relatório | Um estudo real citável (acesso OSD-xxx, título, organismo, ligação) sobre saúde em voo espacial |
| **Mars Trek** | ainda não ligado; ver abaixo | Terreno, elevação e locais de escavação da superfície 2D |

O DONKI só altera o jogo com `ASTRO_NASA_JOGO=1`: nesse modo, um alerta que atinja o
destino multiplica o custo em exposição do incidente de radiação (1,25× / 1,5× / 2×).
Desligado por omissão para as partidas continuarem determinísticas e os testes não
dependerem da rede.

## Configuração

```dotenv
ASTRO_NASA=1
NASA_API_KEY=a_tua_chave_gratuita   # https://api.nasa.gov (DEMO_KEY tem limites baixos)
ASTRO_NASA_TTL_HORAS=6
ASTRO_NASA_JOGO=0
# ASTRO_NASA_CACHE=backend/data/nasa_cache.json
```

Sincronizar e inspeccionar (a partir de `backend/`):

```bash
python -m app.nasa sync
python -m app.nasa estado
python -m app.nasa amostra
```

O estado também está exposto em `GET /api/nasa` (sem rede: lê a cache).

## Fluxo de um lançamento

1. `app/main.py` chama `nasa.sincronizar_se_preciso()` em segundo plano.
2. `app/nasa.py` grava um único JSON pequeno em `data/nasa_cache.json` (cada fonte pode
   falhar sem apagar as outras).
3. Em `missao.aplicar("lancar")`, `nasa.referencia(destino, semente)` lê a cache e guarda
   um briefing pequeno em `estado["ciencia"]`.
4. `servico._vista()` publica esse bloco e `missao.relatorio()` inclui-o no fim da missão.

## Como ligar o Mars Trek

O Mars Trek publica camadas por WMTS e modelos digitais de elevação. Para o cliente 2D:

1. Usar os tiles como fundo do terreno:
   `https://trek.nasa.gov/tiles/Mars/EQ/{layer}/1.0.0/default/default028mm/{z}/{y}/{x}.png`
   (as camadas e o `GetCapabilities` estão em `https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars`).
2. Pedir um perfil de elevação numa janela à volta do local de pouso e guardá-lo na cache
   (o mesmo padrão de `eva.py`/`nasa.py`).
3. Em `superficie.catalogo()`, devolver `elevacao` e usar o perfil para colocar `ESCAVAR`,
   `POS` e as zonas de pouso em terreno real. O servidor continua a validar distâncias em
   metros, por isso a jogabilidade não muda: só o cenário fica verdadeiro.

Como o cliente 2D não vive neste repositório (`../frontend-2d`), o passo 1 é feito no
frontend; os passos 2 e 3 são no backend.

## Limites e cuidados

- Texto externo é limpo com `eva.limpar` (sem controlos nem `<`/`>`), e só URLs `https://`
  entram no estado.
- Respostas limitadas a 2 MB e pedidos com timeout de 10 s.
- A cache é escrita de forma atómica (`os.replace`).
- Dados da NASA são do domínio público, mas mantém a atribuição da fonte visível no jogo.
