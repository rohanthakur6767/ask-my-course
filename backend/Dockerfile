# Backend image for Ask My Course (Django + DRF).
FROM python:3.13-slim

# Keep Python lean and unbuffered so logs appear immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

EXPOSE 8000

# Production start: run migrations, then serve with gunicorn.
# Binds to $PORT if the host sets one (Render does); defaults to 8000 otherwise.
# (Local docker compose overrides this command to use runserver.)
CMD ["sh", "-c", "python manage.py migrate && gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120"]
