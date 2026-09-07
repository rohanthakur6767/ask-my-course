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

# Dev server is fine for the demo / local compose.
# For real production, run gunicorn instead (e.g. gunicorn core.wsgi).
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
