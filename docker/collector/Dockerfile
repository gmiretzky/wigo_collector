FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY collector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src

# Command will be overridden by docker-compose or run directly
CMD ["uvicorn", "src.collector.main:app", "--host", "0.0.0.0", "--port", "5000"]
