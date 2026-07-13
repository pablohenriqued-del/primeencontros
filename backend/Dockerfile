FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 1 worker por padrão — RAM é escassa nesta VPS (ver .ai/docs/DEPLOY.md).
# Só subir pra 2 depois de medir com `docker stats` que sobra memória real.
EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
