FROM python:3.12-slim

# Install system dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create virtual environment in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package definition and application code
COPY pyproject.toml ./
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY entrypoint.sh ./

# Install application and production server dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir '.[perf]' && \
    chmod +x /app/entrypoint.sh && \
    mkdir -p /app/instance && \
    chmod 777 /app/instance

ENV PYTHONUNBUFFERED=1 \
    PORT=5000 \
    INFLATION_DB_PATH=/app/instance/inflation_lens.sqlite3 \
    FLASK_APP=app

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--workers", "4", "--worker-class", "gthread", "--threads", "4", "--bind", "0.0.0.0:5000", "app:create_app()"]
