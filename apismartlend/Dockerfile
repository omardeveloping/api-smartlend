# Stage 1: Base build stage
FROM python:3.13-slim AS builder

# Crear directorio y configurar entorno
RUN mkdir /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema necesarias para compilar dlib/face_recognition
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

# Instalar dependencias Python
RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Production stage
FROM python:3.13-slim

# Crear usuario no root y preparar directorio
RUN useradd -m -r appuser && \
    mkdir /app && \
    chown -R appuser /app

# Copiar dependencias desde el builder
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Establecer directorio de trabajo
WORKDIR /app

# Copiar código fuente
COPY --chown=appuser:appuser . .

# Librerías del sistema necesarias en runtime
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Permisos entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

# Cambiar a usuario sin privilegios
USER appuser

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Exponer el puerto
EXPOSE 8000

# Ejecutar el entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
