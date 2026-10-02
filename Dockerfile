# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /app/dashboard

COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install

COPY dashboard ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY collector/requirements.txt /tmp/collector-requirements.txt
COPY predictor/requirements.txt /tmp/predictor-requirements.txt
COPY mcp/requirements.txt /tmp/mcp-requirements.txt
COPY dashboard/backend/requirements.txt /tmp/dashboard-requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/collector-requirements.txt \
    -r /tmp/predictor-requirements.txt \
    -r /tmp/mcp-requirements.txt \
    -r /tmp/dashboard-requirements.txt

COPY collector /app/collector
COPY predictor /app/predictor
COPY mcp /app/mcp
COPY dashboard/backend /app/dashboard/backend
COPY --from=frontend-build /app/dashboard/dist /app/dashboard/dist

COPY docker/supervisord.conf /etc/supervisor/conf.d/btc.conf

EXPOSE 8000 8001 8080

CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
