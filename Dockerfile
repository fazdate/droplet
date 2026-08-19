# syntax=docker/dockerfile:1

# --- Stage 1: build the frontend SPA ---
FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- Stage 2: backend runtime ---
FROM python:3.12-slim AS backend

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY --from=frontend-build /frontend/dist ./static

RUN mkdir -p /app/data/photos

EXPOSE 8080

CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8080"]
