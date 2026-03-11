FROM python:3.12-slim

WORKDIR /app

COPY services/shared /app/shared
COPY services/gateway/requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir -r /app/gateway/requirements.txt
COPY services/gateway /app/gateway

ENV PYTHONPATH="/app/shared/src:/app/gateway"

WORKDIR /app/gateway

EXPOSE 8080

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
