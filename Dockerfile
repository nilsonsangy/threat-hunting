# Container do laboratório threat-hunting.
# Python 3.12 + pandas, dependências declaradas com uv. Inclui tar/bzip2 para
# baixar e extrair o dataset do CERT (.tar.bz2 multi-stream) dentro do container.
FROM python:3.12-slim

# Ferramentas de sistema para baixar/extrair o dataset.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tar bzip2 \
    && rm -rf /var/lib/apt/lists/*

# uv (gestor declarativo de dependências) — binário oficial.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/lab/.venv \
    PATH="/lab/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /lab

# Camada de dependências (cacheável): só os manifestos primeiro.
COPY pyproject.toml uv.lock LICENSE README.md ./
RUN uv sync --frozen --no-install-project

# Código do laboratório. O dataset NÃO é copiado para a imagem: ele é baixado
# para data/ em runtime e acessado pelo bind mount do docker-compose.
COPY src/ ./src/
COPY exercises/ ./exercises/
COPY tests/ ./tests/
COPY scripts/ ./scripts/

# Instala o pacote thlab no ambiente.
RUN uv sync --frozen

# Usuário não-root dono de /lab.
RUN useradd --create-home --uid 1000 lab \
    && chown -R lab:lab /lab
USER lab

# Mantém o serviço vivo para `docker compose run --rm lab <cmd>`.
CMD ["sleep", "infinity"]
