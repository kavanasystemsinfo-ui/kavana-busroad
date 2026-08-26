# Dockerfile for Kavana BusRoad backend (FastAPI)
# Build context = raíz del repo (backend/Dockerfile)
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código + corpus (README, docs) para el RAG
COPY backend/app ./app
COPY README.md ./README.md
COPY docs ./docs

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]