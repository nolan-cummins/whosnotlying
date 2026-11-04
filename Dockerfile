# Who's Not Lying? self-hosted image. Build from the repository root:
#   docker build -t whosnotlying .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5050 \
    HOST=0.0.0.0 \
    PACKS_DIR=/app/data/packs \
    DATA_DIR=/app/data

WORKDIR /app

# curl: container healthcheck. poppler-utils: pdftotext for the optional "Upload résumé" feature.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl poppler-utils && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY packs/ ./packs-seed/
COPY sources/CONVERTING.md ./sources/CONVERTING.md
COPY deployment/web_server.py ./web_server.py

# Everything the game writes (players, history, accounts, packs) lives under /app/data: mount a volume there.
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    ln -s data/players.json /app/players.json && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 5050
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# 1. One-time migration of legacy per-topic "used" flags into data/history.json (no-op once it exists).
# 2. Seed the packs into the volume; cp -u only replaces a pack when the image's copy is newer, so packs
#    you edit or add in the volume are left alone.
CMD ["sh", "-c", "mkdir -p $PACKS_DIR && python3 -c 'from src import accounts, packs; accounts.has_history_file() or accounts.init_history(packs.legacy_used_keys())' && cp -u packs-seed/*.json $PACKS_DIR/ && exec python3 web_server.py"]
