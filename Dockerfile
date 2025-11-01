# Usar imagen base con Playwright preinstalado (versión actualizada)
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# Configurar directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    cron \
    dos2unix \
    util-linux \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar browsers de Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código fuente
COPY pipeline_licitaciones/ ./pipeline_licitaciones/
COPY entrypoint.sh .
COPY *.py .

# Hacer ejecutable el script de entrada
RUN chmod +x entrypoint.sh

# Configurar variables de entorno
ENV PYTHONPATH=/app
ENV TZ=America/Argentina/Buenos_Aires
ENV GOOGLE_GEMINI_API_KEY=""

# Crear directorios para datos persistentes
RUN mkdir -p /app/data/logs /app/data/timestamps
HEALTHCHECK --interval=5m --timeout=10s --start-period=1m --retries=3 CMD bash -lc 'test -f /app/data/logs/cron-heartbeat.log && [ $(($(date +%s) - $(stat -c %Y /app/data/logs/cron-heartbeat.log))) -lt 600 ] || exit 1'

# Punto de entrada
ENTRYPOINT ["./entrypoint.sh"]