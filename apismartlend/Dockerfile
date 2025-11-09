# Stage 1: Base build stage
FROM python:3.13-slim AS builder

RUN mkdir /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

RUN pip install --upgrade pip 
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production stage
FROM python:3.13-slim

RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app

# 1️⃣ Copia primero el código sin el entrypoint
COPY --chown=appuser:appuser . .

# 2️⃣ Copia entrypoint aparte para asegurarnos que no lo sobrescriben después
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh

# 3️⃣ Dale permisos de ejecución
RUN chmod +x /app/entrypoint.sh

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
