#!/bin/bash

# Script de diagnóstico completo para cron
echo "=== DIAGNÓSTICO CRON - $(date) ===" >> /app/data/logs/cron-diagnostics.log

# 1. Verificar que cron esté ejecutándose
echo "1. Estado del proceso cron:" >> /app/data/logs/cron-diagnostics.log
ps aux | grep cron >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log

# 2. Verificar crontab instalado
echo "2. Crontab actual:" >> /app/data/logs/cron-diagnostics.log
crontab -l >> /app/data/logs/cron-diagnostics.log 2>&1
echo "" >> /app/data/logs/cron-diagnostics.log

# 3. Verificar variables de entorno
echo "3. Variables de entorno disponibles:" >> /app/data/logs/cron-diagnostics.log
env | grep -E '^(TELEGRAM_|FIREBASE_|GOOGLE_|GEMINI_|PATH|TZ)' >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log

# 4. Verificar archivo de entorno para cron
echo "4. Contenido de /app/cron-env.sh:" >> /app/data/logs/cron-diagnostics.log
if [ -f /app/cron-env.sh ]; then
    cat /app/cron-env.sh >> /app/data/logs/cron-diagnostics.log
else
    echo "ARCHIVO /app/cron-env.sh NO EXISTE!" >> /app/data/logs/cron-diagnostics.log
fi
echo "" >> /app/data/logs/cron-diagnostics.log

# 5. Test manual del comando de cron
echo "5. Test manual del comando de cron:" >> /app/data/logs/cron-diagnostics.log
echo "Ejecutando: source /app/cron-env.sh && cd /app && /usr/bin/python3 pipeline_licitaciones/run_pipeline.py" >> /app/data/logs/cron-diagnostics.log
if [ -f /app/cron-env.sh ]; then
    source /app/cron-env.sh && cd /app && timeout 600 /usr/bin/python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-diagnostics.log 2>&1
    echo "Exit code: $?" >> /app/data/logs/cron-diagnostics.log
else
    echo "No se puede ejecutar - archivo cron-env.sh no existe" >> /app/data/logs/cron-diagnostics.log
fi
echo "" >> /app/data/logs/cron-diagnostics.log

# 6. Verificar logs de cron del sistema
echo "6. Logs de cron del sistema:" >> /app/data/logs/cron-diagnostics.log
if [ -f /var/log/cron ]; then
    tail -20 /var/log/cron >> /app/data/logs/cron-diagnostics.log
elif [ -f /var/log/cron.log ]; then
    tail -20 /var/log/cron.log >> /app/data/logs/cron-diagnostics.log
else
    echo "No se encontraron logs de cron del sistema" >> /app/data/logs/cron-diagnostics.log
fi
echo "" >> /app/data/logs/cron-diagnostics.log

# 7. Verificar permisos y estructura de directorios
echo "7. Estructura de directorios y permisos:" >> /app/data/logs/cron-diagnostics.log
ls -la /app/ >> /app/data/logs/cron-diagnostics.log
ls -la /app/data/logs/ >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log

# 8. Configuración de /etc/cron.d/pipeline
echo "8. Configuración /etc/cron.d/pipeline:" >> /app/data/logs/cron-diagnostics.log
if [ -f /etc/cron.d/pipeline ]; then
    cat /etc/cron.d/pipeline >> /app/data/logs/cron-diagnostics.log
else
    echo "No existe /etc/cron.d/pipeline" >> /app/data/logs/cron-diagnostics.log
fi
echo "" >> /app/data/logs/cron-diagnostics.log

echo "=== FIN DIAGNÓSTICO ===" >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log