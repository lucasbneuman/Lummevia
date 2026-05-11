FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
COPY packages/agents /app/packages/agents
COPY packages/core /app/packages/core
COPY packages/kilo-adapter /app/packages/kilo-adapter
COPY packages/integrations /app/packages/integrations
COPY packages/model-router /app/packages/model-router
COPY packages/runtime /app/packages/runtime
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/orchestrator-api /app/apps/orchestrator-api
COPY tests /app/tests
COPY .env.example /app/.env.example

WORKDIR /app/apps/orchestrator-api

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
