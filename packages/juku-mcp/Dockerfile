# Juku's MCP server. Build from the repository root:
#   docker build -f packages/juku-mcp/Dockerfile -t juku-mcp:local .
# It runs as a non-root user on a read-only filesystem (ops/compose.yaml)
# and writes only its audit log, on its own volume.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Built where it runs: uv writes this path into every script's first line (#!/app/.venv/bin/python).
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
# Only this package and the workspace packages it needs, at uv.lock's versions.
RUN uv sync --frozen --no-dev --no-editable --package juku-mcp

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin juku \
    && mkdir -p /var/log/juku-mcp && chown juku /var/log/juku-mcp
COPY --from=build /app/.venv /app/.venv
COPY guardrails.yaml /app/guardrails.yaml
ENV PATH=/app/.venv/bin:$PATH \
    JUKU_RULES_PATH=/app/guardrails.yaml \
    PYTHONDONTWRITEBYTECODE=1
USER juku
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["juku-mcp", "serve", "--host", "0.0.0.0", "--port", "8000"]
