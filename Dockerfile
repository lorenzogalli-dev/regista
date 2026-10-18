# One image: the FastAPI backend serving the built front-end (single Container App).

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    WEB_DIST=/app/web/dist \
    EVAL_REPORT=/app/docs/eval/report.json

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY sim ./sim
COPY metrics ./metrics
COPY agents ./agents
COPY api ./api
COPY eval ./eval
COPY infra ./infra
COPY docs/eval/report.json ./docs/eval/report.json
COPY --from=web /web/dist ./web/dist
RUN uv sync --frozen --no-dev

# Match data and recorded runs are not in the image: in Azure they are downloaded from Blob
# Storage at startup (api/data_sync.py); locally docker-compose mounts them read-only.
# Hidden ground truth is never copied into the image.
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
