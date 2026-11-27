# stur-api

API de consulta de reservas do Stur. Lê a AGI do Stur (somente leitura) e devolve a
venda já calculada e verificada: totais por serviço, conferência dos totais, situação dos
recebimentos e pagamentos, itinerário, vínculos do fee e dado cru como a AGI entregou.

Este repositório é público: não coloque dados reais em código, testes ou documentos.
Números de teste: reserva `90000001` em diante, idreserva `1001` em diante, cliente
`CLIENTE EXEMPLO LTDA`, fornecedor `FORNECEDOR EXEMPLO`.

## Rotas

Prefixo `/api/v1`. O contrato completo (inclusive os envelopes de erro) está em
[`openapi.json`](openapi.json).

| Rota | O que devolve |
|---|---|
| `GET /vendas` | Vendas por número de reserva, período ou os dois, com filtros e resumo do resultado. Devolve o resultado inteiro; a paginação é feita no navegador. |
| `GET /reservas/{numero}` | A reserva (número) com todas as suas vendas. Número sem vendas: 200 com a lista vazia. |
| `GET /reservas/{numero}/vendas/{idreserva}` | Uma venda com cálculos, verificação, itinerário e vínculos. |
| `GET /reservas/{numero}/vendas/{idreserva}/dado-cru` | A venda como a AGI devolveu, com os números exatos. |
| `GET /parametros` | Parâmetros que a tela usa e até quando a API tem dados. |
| `GET /saude` | `{"aplicacao": "ok"}`. Não depende da AGI: é a rota do healthcheck do contêiner. |
| `GET /saude/stur` | Se a AGI aceita o login desta aplicação (`ok`, `sem_resposta`, `acesso_recusado`). Sempre 200. |

Erros ao cliente seguem sempre `{"codigo", "mensagem", "detalhe"}` (mais `campo` no 422),
com a mensagem em pt-BR e sem eco do valor recebido.

## Variáveis de ambiente

Lidas do ambiente (e do `.env` em desenvolvimento). Copie o `.env.example`; os valores reais
ficam só no seu ambiente.

| Variável | Padrão | Uso |
|---|---|---|
| `STUR_API_URL` | obrigatória (exemplo: `https://agi.exemplo.invalid`) | endereço da AGI |
| `STUR_API_USUARIO` | obrigatória | usuário da AGI |
| `STUR_API_SENHA` | obrigatória | senha da AGI |
| `JANELA_INICIO` | `2020-01-01` | início da janela larga; o fim é 31/12 do ano seguinte ao atual |
| `PERIODO_MAXIMO_DIAS` | `31` | período máximo de uma consulta sem número de reserva |
| `LINHAS_POR_PAGINA` | `20` | padrão da lista paginada |
| `OPCOES_POR_PAGINA` | `[20,50,100]` | opções do seletor "Por página" |
| `AGI_TEMPO_LIMITE_S` | `30` | tempo limite de cada chamada à AGI |
| `AGI_INTERVALO_LOGIN_S` | `60` | intervalo mínimo entre verificações de acesso e espera para novo login depois de uma recusa (`0` desliga) |
| `AGI_ITENS_POR_PAGINA` | `2000` | itens por página nas consultas por período (entre 100 e 2000) |
| `CACHE_RESULTADO_S` | `300` | tempo em que o resultado da lista fica em memória |
| `CACHE_RESULTADO_MAX_LINHAS` | `10000` | total de linhas dos resultados em memória; acima disso saem os mais antigos, e um resultado maior que o total não é guardado |
| `CONSULTAS_SIMULTANEAS` | `2` | consultas de `GET /vendas` (por número, período ou os dois) que buscam na AGI ao mesmo tempo (mínimo `1`); as outras esperam a vez, e um resultado guardado responde sem esperar nem ocupar vaga. `GET /parametros` e as rotas de `/reservas` (reserva, venda e dado cru) não ocupam vaga |
| `TOLERANCIA_REAL` | `0.02` | tolerância da verificação dos totais, venda em real |
| `TOLERANCIA_MOEDA_POR_SERVICO` | `0.05` | tolerância por serviço com tarifa convertida |
| `CORTE_TRAJETO_HORAS` | `24` | espera a partir da qual começa um trajeto novo |
| `PRODUTOS_FEE` | `["TAXA FEE"]` | nomes de produto tratados como fee |
| `PRODUTOS_INCENTIVO` | `["INCENTIVO"]` | nomes de produto tratados como incentivo |

## Desenvolvimento

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12.

```bash
uv sync
cp .env.example .env          # preencha só no seu ambiente
uv run pre-commit install
uv run uvicorn stur_api.main:app --reload --no-access-log
```

Verificações (as mesmas do CI):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run bandit -c pyproject.toml -q -r src
TZ=UTC uv run pytest --cov=stur_api    # fuso diferente do de produção, de propósito
uvx --from semgrep==1.165.0 semgrep --error --skip-unknown-extensions \
  --config p/security-audit --config p/secrets
```

O semgrep roda isolado (`uvx`) porque conflita com o fastapi no ambiente do projeto.

### SonarQube

A análise vai para o projeto `stur-consulta` no servidor SonarQube da equipe. A configuração
(host, chave, fontes, cobertura) está em `sonar-project.properties`. O token fica fora do
repositório: defina `SONAR_TOKEN` no ambiente ou em um `.env` ignorado pelo git.

```bash
scripts/sonar.sh                    # pytest com cobertura (coverage.xml) + uv run pysonar
scripts/sonar.sh --somente-scan     # reaproveita o coverage.xml existente
scripts/sonar.sh --tentativas 5     # tentativas do scan (1 a 5, padrão 3)
```

O scan espera o Quality Gate e falha se ele reprovar.

### Modelo da AGI

`src/stur_api/agi/modelos.py` é gerado do dicionário de campos da AGI, que vem de dados
reais e fica **fora do repositório**:

```bash
uv run python scripts/gerar_modelos.py <caminho>/dicionario_campos.json > src/stur_api/agi/modelos.py
uv run ruff format src/stur_api/agi/modelos.py
```

O script copia só nomes e tipos de campo, nunca valores.

### Contrato

O `openapi.json` é gerado pelo código e versionado. O frontend gera os tipos a partir dele,
e o job `contrato` do CI falha se ele estiver desatualizado. Depois de mudar uma rota ou um
modelo de resposta:

```bash
uv run python -m stur_api.openapi_export > openapi.json
```

Os `operationId` são o nome da função da rota (`consultar_vendas`, `abrir_reserva`,
`abrir_venda`, `dado_cru_da_venda`, `parametros`, `saude`, `saude_stur`); mudar um nome muda
o nome gerado no frontend.

## Docker

Imagem `linux/amd64`, multi-stage com uv, usuário sem privilégio e base fixada por digest.

```bash
docker build --platform linux/amd64 -t stur-api:teste .
docker run --rm -p 8000:8000 \
  -e STUR_API_URL=https://agi.exemplo.invalid \
  -e STUR_API_USUARIO=usuario -e STUR_API_SENHA=senha \
  stur-api:teste
curl -s localhost:8000/api/v1/saude    # {"aplicacao":"ok"}
```

O `HEALTHCHECK` consulta `/api/v1/saude`. A imagem sobe o uvicorn com `--no-access-log`.
Em produção, passe `STUR_API_URL`, `STUR_API_USUARIO` e `STUR_API_SENHA` pelo ambiente do
servidor, nunca na imagem.

## Privacidade dos logs

O log traz método, rota (o modelo, como `/api/v1/reservas/{numero}`, sem a query), status,
duração, número da reserva e idreserva. Nunca entram:

- a query string nem os textos de filtro (cliente, fornecedor, emissor);
- o corpo de pedido ou resposta, nome de cliente ou passageiro;
- a URL da AGI, usuário, senha ou token.

Por isso o access log do uvicorn fica desligado (`--no-access-log`): ele grava a query.
Exceções não tratadas saem só com o nome da classe, sem mensagem nem traceback com valores.
Os loggers `httpx` e `httpcore` ficam em WARNING porque o INFO deles grava a URL da AGI.

## CI e release

- `.github/workflows/ci.yml` (pull request e push): `quality` (ruff, mypy, bandit, pytest com
  cobertura), `sast` (semgrep), `segredos` (gitleaks), `contrato` (`openapi.json` em dia) e
  `imagem` (build sem publicar, com um teste de saúde).
- `.github/workflows/release.yml`: roda **depois** do `ci`, via `workflow_run`, e só se o
  `ci` foi um push na `main` com todos os jobs verdes.

Fluxo da `main`: push -> CI verde -> release -> imagem.

1. O push na `main` dispara o `ci`. Na `main` ele não é cancelado por um push seguinte.
2. Se o `ci` terminou verde, o `release` leva a `main` ao commit que o CI aprovou
   (`git reset --hard` no `head_sha`) e roda o `python-semantic-release`: calcula a versão
   pelos Conventional Commits, atualiza `pyproject.toml`, `uv.lock` (só a versão do próprio
   projeto) e `CHANGELOG.md`, e cria o commit de versão, a tag e o GitHub Release. Sem
   `feat`/`fix` desde a última tag, não há versão e a imagem não sai.
3. Se houve versão, o job `imagem` faz checkout da tag e publica
   `ghcr.io/pedroct/stur-api:{versão}` (`linux/amd64`) com o `GITHUB_TOKEN`
   (`packages: write` só nesse job; `contents: write` só no job `release`).

Por isso a `main` não deve ter proteção que bloqueie o push do commit de versão pelo
`github-actions`. As Actions de terceiros ficam fixadas por SHA de commit, com a versão em
comentário. Commits em Conventional Commits, descrição em pt-BR.
