FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .

CMD ["python", "-m", "aduns_fx.cli", "live", "--config", "config/live.example.json"]
