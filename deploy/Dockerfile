FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build -- --base=/static/ --outDir=../backend/static_build --emptyOutDir

FROM python:3.13-slim AS application
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    DJANGO_SETTINGS_MODULE=config.settings.production
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend-build /app/backend/static_build/ /app/backend/static_build/
RUN DJANGO_SECRET_KEY=build-only-placeholder-key-with-at-least-fifty-characters \
    DJANGO_ALLOWED_HOSTS=localhost \
    POSTGRES_DB=build POSTGRES_USER=build POSTGRES_PASSWORD=build \
    POSTGRES_HOST=127.0.0.1 POSTGRES_SSLMODE=require \
    python backend/manage.py collectstatic --noinput
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app
EXPOSE 10000
CMD ["sh", "-c", "gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 30"]
