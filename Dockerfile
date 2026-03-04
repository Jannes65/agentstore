FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir fastapi uvicorn pydantic

EXPOSE 8000

CMD ["uvicorn", "agentstore_api:app", "--host", "0.0.0.0", "--port", "8000"]
