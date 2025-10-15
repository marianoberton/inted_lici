#!/bin/bash

# Convertir archivos a formato Unix
echo "Convirtiendo archivos a formato Unix..."
find /app -type f \( -name "*.py" -o -name "*.sh" \) -exec dos2unix {} \;

# Configurar cron
echo "Configurando cron..."
echo "0 7-20 * * * cd /app && python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-pipeline.log 2>&1" | crontab -

# Iniciar cron en segundo plano
cron &

# Ejecutar pipeline al iniciar
echo "Ejecutando el pipeline al iniciar..."
cd /app
python3 pipeline_licitaciones/run_pipeline.py

# Mantener el contenedor activo
echo "Pipeline iniciado. Cron configurado para ejecutar cada hora entre las 7:00 AM y 8:00 PM."
tail -f /dev/null