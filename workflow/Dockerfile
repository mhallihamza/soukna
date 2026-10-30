# Service workflow Soukna — LangGraph + FastAPI
FROM python:3.12-slim

WORKDIR /app

# Dépendances d'abord (cache de build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code
COPY . .

EXPOSE 8000
# Render impose son PORT (10000) ; défaut 8000 en local / docker compose.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
