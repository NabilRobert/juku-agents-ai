# Juku's web app, with the cron jobs it runs (juku-ops) and the hand-run ones
# (juku-data, juku). Build from the repository root:
#   docker build -f app/Dockerfile -t juku-app:local .
# Read-only filesystem, no capabilities, non-root (ops/compose.yaml).

# 1. The Vue islands (app/web), built to app/src/juku_app/static/dist.
FROM node:24-alpine AS web
WORKDIR /build/app/web
COPY app/web/package.json app/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/web/ ./
# Tailwind keeps only the classes the templates use, so it reads them.
COPY app/src/juku_app/templates /build/app/src/juku_app/templates
RUN npm run build

# 2. The Python packages, at uv.lock's versions, with the built islands inside.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY app/pyproject.toml app/pyproject.toml
COPY app/src/ app/src/
COPY --from=web /build/app/src/juku_app/static/dist app/src/juku_app/static/dist
RUN uv sync --frozen --no-dev --no-editable

# 3. What runs.
FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin juku
COPY --from=build /src/.venv /app/.venv
COPY guardrails.yaml alembic.ini /app/
COPY migrations/ /app/migrations/
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    JUKU_RULES_PATH=/app/guardrails.yaml \
    PYTHONDONTWRITEBYTECODE=1
USER juku
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["juku", "serve", "--host", "0.0.0.0", "--port", "8000"]
