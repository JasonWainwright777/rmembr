FROM python:3.12-slim

WORKDIR /app

COPY services/shared /app/shared
COPY services/standards/requirements.txt /app/standards/requirements.txt
RUN pip install --no-cache-dir -r /app/standards/requirements.txt
COPY services/standards /app/standards

ENV PYTHONPATH="/app/shared/src:/app/standards"

WORKDIR /app/standards

EXPOSE 8082

CMD ["python", "-m", "src.server"]
