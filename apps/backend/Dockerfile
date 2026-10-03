FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY apps/backend/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY apps/backend /app
RUN DJANGO_SETTINGS_MODULE=config.settings.test python manage.py collectstatic --noinput
RUN useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60 --access-logfile - --error-logfile - --graceful-timeout 30"]
