# Stage 1: build the React app
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Django + gunicorn, serving the built SPA through WhiteNoise
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist ./static_frontend
# Hugging Face Spaces runs containers as uid 1000 and routes traffic to port 7860.
RUN useradd --create-home --uid 1000 app && mkdir -p /app/var && chown -R app /app
USER app
ENV PORT=7860
EXPOSE 7860
# gthread: requests spend their time waiting on upstream APIs, so threads scale better than processes.
CMD ["sh", "-c", "gunicorn config.wsgi --bind 0.0.0.0:${PORT:-7860} --workers 2 --threads 8 --timeout 120"]
