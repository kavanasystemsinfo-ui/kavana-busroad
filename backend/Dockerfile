# Dockerfile for Kavana BusRoad — backend FastAPI + PWA (desde 2026-09-30)
# Build context = raíz del repo (dockerfile backend/Dockerfile en fly.toml)
# El backend sirve el frontend estático (vite build) para que la PWA viva en
# Fly junto a la API (migración desde Vercel; antes el frontend era Vercel).

# ---- Stage 1: construir el frontend (PWA Vue 3 + Vite) ----
FROM node:22-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build   # genera /app/dist

# ---- Stage 2: backend FastAPI ----
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código + corpus (README, docs) para el RAG
COPY backend/app ./app
COPY README.md ./README.md
COPY docs ./docs

# Frontend ya compilado: /app/static es lo que sirve la PWA
COPY --from=frontend-build /app/dist ./static

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]