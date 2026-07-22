FROM python:3.11-slim

WORKDIR /app/models

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY models/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models/ .
COPY ingestion/config/tickers.yaml /app/ingestion/config/tickers.yaml

ENV PYTHONUNBUFFERED=1
ENV MLFLOW_TRACKING_URI=http://mlflow:5000

CMD ["python", "train.py", "--help"]
