# threat-hunting — Laboratório de detecção de ameaça interna (CERT r4.2)

Laboratório prático e autocontido de **threat hunting** para **ameaça interna
(insider threat)**. Você baixa o *CERT Insider Threat Test Dataset* (release
**r4.2**, da Carnegie Mellon University / CERT) e executa uma sequência de
exercícios de detecção sobre os dados reais — da navegação suspeita à correlação
de sinais num score de risco, validando o resultado contra o gabarito oficial de
insiders do dataset.

Tudo roda dentro de um container (Docker + Python + pandas). Os comandos deste
guia estão prontos para **Windows PowerShell**, mas funcionam igual em Linux/macOS
(é só `docker compose`).

## O que você vai praticar

Seis exercícios encadeados, cada um ligado a uma técnica do MITRE ATT&CK:

| # | Exercício | Sinal de insider | ATT&CK |
|---|---|---|---|
| 1 | Navegação web suspeita | sites de emprego / upload para nuvem pessoal | T1567 |
| 2 | Exfiltração por USB | cópia de arquivos para mídia removível | T1052 |
| 3 | USB fora de hora × logon | conexão fora do expediente em sessão real | T1078 + T1052 |
| 4 | Cópia vs. baseline | volume de cópia acima do padrão do grupo (peer-group) | T1052 |
| 5 | Correlação e score de risco | múltiplos sinais somados por usuário | T1052 / T1567 / T1078 |
| 6 | Validação | ranking confrontado com o gabarito oficial de insiders | — |

---

## Pré-requisitos

- **Docker Desktop** com **Docker Compose v2** (comando `docker compose`).
- Espaço em disco para o dataset: o r4.2 tem ~4,8 GB compactado e expande para
  dezenas de GB.
- Você **não** precisa de Python nem pandas instalados: tudo vive no container.

> Os comandos partem da raiz do repositório:
>
> ```powershell
> cd caminho\para\threat-hunting
> ```

---

## Parte 0 — Preparar o ambiente

Construa a imagem e suba o container do laboratório:

```powershell
docker compose build lab
docker compose up -d lab
```

> O repositório é montado dentro do container (a pasta do projeto e a pasta
> `/lab` no container são a mesma). Então o dataset que você baixar para `data/`
> aparece nos dois lados.

---

## Parte 1 — Baixar o dataset oficial (CERT r4.2)

Os exercícios rodam sobre os **dados reais** do CERT r4.2. Baixe-os antes de
qualquer exercício.

### 1.1 Ver a fonte e os termos (sem baixar)

```powershell
docker compose run --rm lab python scripts/download_cert.py --dry-run
```

### 1.2 Baixar o dataset (~4,8 GB) e o gabarito oficial

```powershell
docker compose run --rm lab python scripts/download_cert.py
```

O script baixa o `r4.2.tar.bz2` e o `answers.tar.bz2` para `data/`, exibindo a
referência e os termos de uso antes de começar, e confere a integridade.

### 1.3 Extrair

```powershell
docker compose run --rm lab python scripts/download_cert.py --extract
```

Ao final, os CSVs ficam em `data/r4.2/` (logon, device, file, http, email, a
pasta `LDAP/`) e o gabarito em `data/answers/`. A partir daqui, os exercícios
leem diretamente esses dados.

> **Volume e desempenho.** O `http.csv` do r4.2 é enorme (dezenas de GB). Os
> exercícios que o usam leem o arquivo em blocos (streaming), sem carregar tudo na
> memória. Ainda assim, exercícios sobre o http podem levar alguns minutos.

---

## Parte 2 — Exercícios em Python

Rode na ordem (1 → 6): eles contam uma história, do primeiro sinal isolado até a
validação final contra o gabarito. Cada exercício imprime o resultado no terminal.

### Exercício 1 — Navegação web suspeita · T1567

Usuários que acessam sites de emprego ou fazem upload para nuvem pessoal.

```powershell
docker compose run --rm lab python -m exercises.ex01_navegacao
```

### Exercício 2 — Exfiltração por USB · T1052

Quem copia arquivos para mídia removível durante uma conexão de USB.

```powershell
docker compose run --rm lab python -m exercises.ex02_usb
```

### Exercício 3 — USB fora de hora × logon · T1078 + T1052

Confirma que a conexão de USB fora do expediente coincide com uma sessão de logon
real do próprio usuário. O expediente é ajustável:

```powershell
docker compose run --rm lab python -m exercises.ex03_usb_fora_hora
docker compose run --rm lab python -m exercises.ex03_usb_fora_hora --expediente 8-18
```

### Exercício 4 — Cópia vs. baseline do grupo · T1052

Volume de cópia comparado contra a baseline do próprio usuário e a do grupo de
pares (papel no LDAP). O desvio, não o valor absoluto, acusa o outlier.

```powershell
docker compose run --rm lab python -m exercises.ex04_copia_arquivos
```

### Exercício 5 — Correlação e score de risco

Cruza os quatro sinais numa janela e soma um score aditivo por usuário.

```powershell
docker compose run --rm lab python -m exercises.ex05_correlacao
```

### Exercício 6 — Validação contra o gabarito oficial

Confronta o ranking do exercício 5 com o gabarito de insiders do r4.2 (verdadeiros
positivos × falsos positivos).

```powershell
docker compose run --rm lab python -m exercises.ex06_validacao
```

### Rodar a suíte de testes

```powershell
docker compose run --rm lab pytest -q
```

---

## Parte 3 — Visualizar no OpenSearch (opcional)

Opcional, para explorar os mesmos dados numa interface web. Nada dos exercícios
depende disso.

```powershell
# subir OpenSearch + Dashboards
docker compose --profile opensearch up -d

# ingerir as fontes (de dentro da rede do compose)
docker compose run --rm lab python scripts/ingest_opensearch.py --host opensearch:9200

# abrir no navegador
# http://localhost:5601
```

Em **Dashboards Management → Index patterns**, crie um pattern `th-*` com `date`
como campo de tempo e explore em **Discover**. Exemplos:

- `url: *indeed* OR url: *dropbox*` no índice `th-http` → navegação suspeita.
- `activity: Connect` no `th-device` → conexões de USB.

Encerrar:

```powershell
docker compose --profile opensearch down -v
```

O passo a passo detalhado está em
[`compose/opensearch/README-ingest.md`](./compose/opensearch/README-ingest.md).

---

## Encerrar o laboratório

```powershell
docker compose down -v --remove-orphans
```

---

## Mapa de comandos (PowerShell)

| Objetivo | Comando |
|---|---|
| Construir a imagem | `docker compose build lab` |
| Subir o laboratório | `docker compose up -d lab` |
| Baixar o dataset | `docker compose run --rm lab python scripts/download_cert.py` |
| Extrair o dataset | `docker compose run --rm lab python scripts/download_cert.py --extract` |
| Rodar um exercício | `docker compose run --rm lab python -m exercises.ex01_navegacao` |
| Rodar os testes | `docker compose run --rm lab pytest -q` |
| Subir o OpenSearch | `docker compose --profile opensearch up -d` |
| Encerrar tudo | `docker compose down -v --remove-orphans` |

Módulos de exercício: `ex01_navegacao`, `ex02_usb`, `ex03_usb_fora_hora`,
`ex04_copia_arquivos`, `ex05_correlacao`, `ex06_validacao`.

---

## Estrutura do repositório

```text
threat-hunting/
├── README.md                 # este guia
├── LICENSE                   # MIT (código do laboratório)
├── pyproject.toml / uv.lock  # dependências (pandas, pytest) via uv
├── Dockerfile                # Python 3.12 + uv
├── docker-compose.yml        # serviço `lab` (default) + profile `opensearch`
├── data/                     # dataset baixado (gitignored): r4.2/ e answers/
├── src/thlab/                # núcleo: loaders, timewin, baseline, score, domains
├── exercises/                # ex01..ex06
├── tests/                    # testes dos exercícios e do núcleo
├── scripts/                  # download_cert.py e ingest_opensearch.py
└── compose/opensearch/       # material do caminho opcional
```

---

## Dados: origem, licença e créditos

O dataset **não** é versionado neste repositório — você o baixa da fonte oficial
(o diretório `data/` é ignorado pelo Git). Isso respeita os termos de uso do
dataset.

- **Fonte:** *Insider Threat Test Dataset*, Carnegie Mellon University (CERT
  Division), distribuído no KiltHub:
  <https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247>
- **Referência:** Glasser, J.; Lindauer, B. *Bridging the Gap: A Pragmatic
  Approach to Generating Insider Threat Data*. IEEE Security and Privacy
  Workshops, 2013.
- **Gerador dos dados:** os arquivos de teste foram produzidos pela **ExactData,
  LLC** (© 2011, todos os direitos reservados) sob acordo com a CMU/SEI. Respeite
  a licença incluída no próprio dataset (`r4.2/license.txt`) ao usá-lo ou
  publicar trabalhos derivados.

O **código** deste laboratório é de **Nilson Sangy** e está sob a licença
[MIT](./LICENSE). A licença MIT cobre o código, não o dataset.
