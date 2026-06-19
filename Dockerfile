FROM python:3.12-slim

WORKDIR /app

# Install system deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy everything (dockerignore excludes .venv/ __pycache__/ .git/ tests/ etc.)
COPY . .

# Install Python deps AND the app package
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 8000

# Run migrations then start server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
