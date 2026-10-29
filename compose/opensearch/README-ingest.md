# Ingestão das fontes no OpenSearch (opcional)

Passo a passo para subir OpenSearch + OpenSearch Dashboards e explorar os dados do
CERT r4.2 visualmente. É um caminho **opcional e isolado**: os exercícios e os
testes rodam sem ele, e nada em `exercises/` ou `tests/` o utiliza.

## Pré-requisitos

- O dataset já baixado e extraído (`data/r4.2/` presente). Veja o README principal.
- Memória suficiente para o OpenSearch (o serviço usa `-Xms512m -Xmx512m`). Em
  Linux pode ser preciso `sudo sysctl -w vm.max_map_count=262144`.

## 1. Subir o OpenSearch + Dashboards

Os serviços ficam sob o profile `opensearch`, então o `up` padrão não os sobe:

```powershell
docker compose --profile opensearch up -d
```

Aguarde a porta `9200` responder:

```powershell
curl http://localhost:9200
```

## 2. Ingerir as fontes

O script cria um índice por fonte (`th-logon`, `th-device`, `th-file`,
`th-email`, `th-http`) e indexa via API `_bulk`. De dentro da rede do compose, o
host é `opensearch:9200`:

```powershell
docker compose run --rm lab python scripts/ingest_opensearch.py --host opensearch:9200
```

Opções: `--limite N` (linhas por fonte de atividade) e `--http-amostra N` (linhas
do http). Como o dataset é grande, o ingest usa recortes por padrão.

## 3. Explorar no Dashboards

Abra `http://localhost:5601`. Em **Dashboards Management → Index patterns**, crie
`th-*` com `date` como campo de tempo e explore em **Discover**. Exemplos:

- `url: *indeed* OR url: *dropbox*` no `th-http` → navegação suspeita.
- `activity: Connect` no `th-device` → conexões de USB.
- `th-file` → cópias de arquivo (correlacione com `th-device` por usuário/hora).

## 4. Encerrar

```powershell
docker compose --profile opensearch down -v
```
