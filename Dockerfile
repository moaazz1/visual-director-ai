FROM node:24-bookworm-slim AS frontend
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN python3 -m venv /opt/director && /opt/director/bin/pip install --no-cache-dir -r requirements.txt
COPY api api
COPY --from=frontend /build/web web
COPY deploy/start.sh /usr/local/bin/start-director
RUN mkdir -p /app/.data && chown -R 1000:1000 /app
ENV DATA_DIR=/app/.data COOKIE_SECURE=1 NEXT_TELEMETRY_DISABLED=1 VISION_PROVIDER=gemini
USER 1000:1000
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["bash", "/usr/local/bin/start-director"]
