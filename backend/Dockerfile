FROM python:3.11-slim

LABEL maintainer="Qwen Council Team"
LABEL description="Qwen Council — Multi-agent code review with memory"

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory to project root so "backend." imports resolve
WORKDIR /app

# Install system dependencies (only what's needed for psycopg2 / asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code into /app/backend/ so "from backend.X import Y" works
COPY ./ ./backend/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run with module-style import path
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
