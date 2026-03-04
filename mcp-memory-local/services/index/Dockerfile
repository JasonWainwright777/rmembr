FROM python:3.12-slim

WORKDIR /app

COPY services/shared /app/shared
COPY services/index/requirements.txt /app/index/requirements.txt
RUN pip install --no-cache-dir -r /app/index/requirements.txt
COPY services/index /app/index

ENV PYTHONPATH="/app/shared/src:/app/index"

WORKDIR /app/index

EXPOSE 8081

CMD ["python", "-m", "src.server"]
