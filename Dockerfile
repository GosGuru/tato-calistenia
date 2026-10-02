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

# Pinned official Node Linux x64 build. It is glibc-linked, matching this
# Debian runtime; the frontend-builder stage above is Alpine (musl), is
# discarded on purpose and never supplies the Node runtime or native modules.
ARG NODE_VERSION=22.21.1
ARG NODE_DIST_SHA256=219a152ea859861d75adea578bdec3dce8143853c13c5187f40c40e77b0143b2

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8765 \
    TATO_LIBRARY_MODEL_DIR="C:/Users/Maxim/AppData/Local/TatoEditorialRag/models"
# TATO_LIBRARY_MODEL_DIR is the single model-directory override honoured by
# tools/editorial_rag/model_setup.py. The embedding child (embed.mjs) pins
# exactly this path string and rejects any other model_path, so the image
# mirrors it under the app working directory: the assets live at
# /app/C:/Users/Maxim/AppData/Local/TatoEditorialRag/models/<model>/<revision>
# and every read, hash check and child invocation resolves there.

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSLo node.tar.gz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz" \
    && echo "${NODE_DIST_SHA256}  node.tar.gz" | sha256sum -c - \
    && tar -xzf node.tar.gz -C /usr/local --strip-components=1 \
    && rm node.tar.gz \
    && node --version | grep -Fx "v${NODE_VERSION}"

# Embedding runtime dependencies come from the committed lockfile inside the
# image (linux glibc native bits); the working tree never ships node_modules.
COPY tools/editorial_rag/embedding_node/package.json tools/editorial_rag/embedding_node/package-lock.json ./tools/editorial_rag/embedding_node/
RUN npm ci --prefix tools/editorial_rag/embedding_node

COPY tools/editorial_rag/requirements.txt ./tools/editorial_rag/requirements.txt
RUN pip install --no-cache-dir -r ./tools/editorial_rag/requirements.txt

COPY tools/ ./tools/
COPY .agents/ ./.agents/
COPY --from=frontend-builder /app/tools/editorial_rag/web/dist ./tools/editorial_rag/web/dist

# Bake the pinned, hash-verified embedding model at build time. The entrypoint
# downloads and verifies every asset; a failed download or hash check fails the
# image build loudly instead of shipping an image that cannot embed.
RUN python -B -m tools.editorial_rag.model_setup

EXPOSE 8765

CMD ["python", "-B", "-m", "tools.editorial_rag.local_web"]
