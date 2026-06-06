# ── Stage 1: build do frontend ──────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: backend Python + frontend estático ──────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# dependências do backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# código do backend
COPY backend/ ./

# frontend buildado copiado para pasta que o FastAPI vai servir
COPY --from=frontend-build /app/frontend/dist ./static

# Railway define a porta via $PORT — uvicorn lê e usa
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
