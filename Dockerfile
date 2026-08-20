FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002 \
    HOST=0.0.0.0 \
    FLASK_DEBUG=false \
    ENABLE_LIVE_SCRAPING=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/data
COPY requirements-hosting.txt ./
RUN pip install --no-cache-dir -r requirements-hosting.txt

COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist

# The SQLite file is demo data only. Mount a persistent volume for any
# approved pilot deployment; do not treat SQLite as a multi-instance store.
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/healthz')"

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8002} --workers 1 --threads 4 --access-logfile - wsgi:app"]
