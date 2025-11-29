# Stage 1: Base build stage
FROM python:3.13-slim AS builder

RUN mkdir /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-dev \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Production stage
FROM python:3.13-slim

RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

WORKDIR /app

# Copy dependencies
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: copy entrypoint first
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

# Now copy everything else
COPY --chown=appuser:appuser . .

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
