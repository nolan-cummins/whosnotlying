# Who's Not Lying? self-hosted image. Build from the repository root:
#   docker build -t whosnotlying .
FROM node:22-slim

ENV NODE_ENV=production \
    PORT=5050 \
    HOST=0.0.0.0 \
    PACKS_DIR=/app/data/packs \
    DATA_DIR=/app/data

WORKDIR /app

# curl: container healthcheck. poppler-utils: pdftotext for the optional "Upload résumé" feature.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# The only runtime dependency is the QR encoder; TypeScript is run directly by Node (no build step).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY src/ ./src/
COPY packs/ ./packs-seed/
COPY sources/CONVERTING.md ./sources/CONVERTING.md
COPY deployment/web_server.ts ./deployment/web_server.ts

# Everything the game writes (players, history, accounts, packs) lives under /app/data: mount a volume there.
RUN mkdir -p /app/data && \
    ln -s data/players.json /app/players.json && \
    chown -R node:node /app
USER node

EXPOSE 5050
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Seed the packs into the volume; cp -u only replaces a pack when the image's copy is newer, so packs
# you edit or add in the volume are left alone. Legacy per-topic "used" flags migrate into
# data/history.json on the first start (the server does that itself).
CMD ["sh", "-c", "mkdir -p $PACKS_DIR && cp -u packs-seed/*.json $PACKS_DIR/ && exec node deployment/web_server.ts"]
