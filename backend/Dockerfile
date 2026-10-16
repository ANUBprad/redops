FROM python:3.12-slim-trixie AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build/install dependencies in a separate stage so compilers and headers
# do not ship in the production runtime image.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.12-slim-trixie AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

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
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 10001 appuser && \
    useradd --system --uid 10001 --gid appuser appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser
CMD ["uvicorn", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
