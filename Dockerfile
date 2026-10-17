# Hearsay web demo. Build: docker build -t hearsay .
# Run: docker run --rm -p 8000:8000 --env-file .env hearsay   (then open http://localhost:8000)

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3.12
WORKDIR /app
# Dependencies first, so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin hearsay
COPY --from=build --chown=root:root /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HEARSAY_CACHE_DIR=/tmp/hearsay-cache \
    PORT=8000
USER hearsay
WORKDIR /home/hearsay
EXPOSE 8000
# Render sets PORT; locally it is 8000. The app reads its keys from the environment.
CMD ["sh", "-c", "exec uvicorn hearsay.web.app:app --host 0.0.0.0 --port \"$PORT\" --no-proxy-headers --timeout-keep-alive 75"]
