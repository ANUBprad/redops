FROM python:3.12-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Native build tools stay in this stage; only the virtual environment is copied
# into the runtime image.
RUN apk add --no-cache build-base cargo linux-headers libffi-dev openssl-dev libuv-dev

COPY pyproject.toml ./
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.12-alpine AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apk upgrade --no-cache && apk add --no-cache libuv

COPY --from=builder /opt/venv /opt/venv
COPY pyproject.toml ./pyproject.toml
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

FROM runtime AS development
COPY . .
CMD ["uvicorn", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--factory"]

FROM runtime AS production
RUN addgroup -S -g 10001 appuser && \
    adduser -S -u 10001 -G appuser appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser
CMD ["uvicorn", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
