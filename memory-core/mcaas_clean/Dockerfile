FROM python:3.12-slim-bookworm AS base

# ── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL 16
    postgresql-16 postgresql-16-pgvector postgresql-client-16 \
    # Redis
    redis-server \
    # Process supervisor
    supervisor \
    # Utilities
    curl wget ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# ── Ollama ────────────────────────────────────────────────────────────────────
RUN curl -fsSL https://ollama.ai/install.sh | sh

# ── Python application ────────────────────────────────────────────────────────
WORKDIR /app
COPY memory-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY memory-core/ /app/

# ── Config and supervisor ─────────────────────────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/memory-core.conf
COPY scripts/init_postgres.sh /init_postgres.sh
RUN chmod +x /init_postgres.sh

# ── Data volumes ──────────────────────────────────────────────────────────────
RUN mkdir -p /data/postgres /data/ollama /data/soul /data/config \
    && chown -R postgres:postgres /data/postgres

# ── Pull embedding model at build time (layer-cached) ────────────────────────
# Comment out for faster builds; model will pull at first startup if not cached
RUN ollama serve & \
    sleep 6 && \
    ollama pull nomic-embed-text && \
    sleep 2 && \
    kill %1 || true

# ── Expose only the API port ──────────────────────────────────────────────────
EXPOSE 4200

# PostgreSQL, Redis, and Ollama are internal only — never exposed

VOLUME ["/data/postgres", "/data/ollama", "/data/soul", "/data/config"]

ENTRYPOINT ["/init_postgres.sh"]
