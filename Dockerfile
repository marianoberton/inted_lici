# Dockerfile optimizado para EasyPanel
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    dos2unix \
    cron \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright y configurar Chromium
RUN playwright install chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copiar código fuente
COPY pipeline_licitaciones/ ./pipeline_licitaciones/
COPY entrypoint.sh .
COPY *.py .

# Hacer ejecutable el entrypoint
RUN chmod +x entrypoint.sh

# Crear directorios necesarios
RUN mkdir -p /app/data/logs /app/data/timestamps

# Configurar variables de entorno para Playwright
ENV PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Exponer puerto si es necesario
EXPOSE 8000

# Punto de entrada
ENTRYPOINT ["/app/entrypoint.sh"]