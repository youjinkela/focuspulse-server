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

# Run with entrypoint (migrations then server)
CMD ["./docker-entrypoint.sh"]
