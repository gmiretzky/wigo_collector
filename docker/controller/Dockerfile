FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

COPY docker/controller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set Python path to find src
ENV PYTHONPATH=/app

CMD ["uvicorn", "src.wigo.main:app", "--host", "0.0.0.0", "--port", "8443"]
