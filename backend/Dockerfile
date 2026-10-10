FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The api service runs this; the notifier overrides it in docker-compose.yml.
CMD ["sh", "-c", "alembic upgrade head && python -m due_brew.seed && exec uvicorn due_brew.api.main:app --host 0.0.0.0 --port 8000 --root-path /due-brew"]
