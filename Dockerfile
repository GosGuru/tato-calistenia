# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/tools/editorial_rag/web
COPY tools/editorial_rag/web/package*.json ./
RUN npm ci
COPY tools/editorial_rag/web/ ./
RUN npm run build

# Stage 2: Production Python Backend
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8765

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY tools/editorial_rag/requirements.txt ./tools/editorial_rag/requirements.txt
RUN pip install --no-cache-dir -r ./tools/editorial_rag/requirements.txt

COPY tools/ ./tools/
COPY .agents/ ./.agents/
COPY --from=frontend-builder /app/tools/editorial_rag/web/dist ./tools/editorial_rag/web/dist

EXPOSE 8765

CMD ["python", "-B", "-m", "tools.editorial_rag.local_web"]
