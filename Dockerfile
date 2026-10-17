ARG PYTHON_IMAGE=python:3.13.16-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:${PATH}"
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 juya \
    && useradd --uid 10001 --gid juya --no-create-home juya
WORKDIR /app

FROM base AS build
RUN /usr/local/bin/python -m pip install --no-cache-dir uv==0.13.1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache
COPY src ./src
RUN uv sync --frozen --no-dev --no-cache

FROM base AS runtime
ARG JUYA_SOURCE_COMMIT
LABEL org.opencontainers.image.revision="${JUYA_SOURCE_COMMIT}"
COPY --from=build /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY deploy/container-health.py deploy/bootstrap-admin.py deploy/runtime-preflight.py ./deploy/
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=3 CMD ["python", "/app/deploy/container-health.py", "api"]

FROM runtime AS admin
ENV JUYA_IMAGE_ROLE=admin
LABEL org.opencontainers.image.title="juya-admin-api"
CMD ["python", "-m", "uvicorn", "juya_api.admin:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS mini
ENV JUYA_IMAGE_ROLE=mini
LABEL org.opencontainers.image.title="juya-miniapp-api"
CMD ["python", "-m", "uvicorn", "juya_api.mini:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
