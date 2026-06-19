FROM python:3.12-slim

WORKDIR /app

# Install system deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy app
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Copy entrypoint
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Run with entrypoint (migrations then server)
CMD ["./docker-entrypoint.sh"]
