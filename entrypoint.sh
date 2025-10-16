#!/bin/bash

# Configurar timezone ANTES de cualquier otra cosa
export TZ=America/Argentina/Buenos_Aires
ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Verificar timezone configurado
echo "Timezone configurado: $(date)"
echo "Timezone actual: $TZ"

# Convertir archivos a formato Unix
echo "Convirtiendo archivos a formato Unix..."
find /app -type f \( -name "*.py" -o -name "*.sh" \) -exec dos2unix {} \;

# Crear directorios de logs
mkdir -p /app/data/logs

# Configurar cron con timezone explícito - CADA 15 MINUTOS PARA TESTING
echo "Configurando cron..."
cat > /tmp/crontab << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=America/Argentina/Buenos_Aires
# Pipeline cada 15 minutos
*/15 * * * * cd /app && /usr/bin/python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-pipeline.log 2>&1
# Heartbeat cada 5 minutos para verificar que cron funciona
*/5 * * * * /bin/echo "$(TZ=America/Argentina/Buenos_Aires /bin/date): Cron heartbeat - PID $$" >> /app/data/logs/cron-heartbeat.log 2>&1
# Test cada minuto para debugging
* * * * * /bin/echo "$(TZ=America/Argentina/Buenos_Aires /bin/date): Cron test minutely" >> /app/data/logs/cron-debug.log 2>&1
EOF

# Instalar crontab
crontab /tmp/crontab

# Verificar instalación
echo "Crontab instalado:"
crontab -l

# Crear archivos de log iniciales
touch /app/data/logs/cron-pipeline.log
touch /app/data/logs/cron-heartbeat.log  
touch /app/data/logs/cron-debug.log
chmod 666 /app/data/logs/cron-*.log

# Ejecutar pipeline al iniciar
echo "Ejecutando el pipeline al iniciar..."
cd /app
python3 pipeline_licitaciones/run_pipeline.py

# Iniciar cron en foreground y monitorear
echo "Pipeline iniciado. Cron configurado para ejecutar CADA 15 MINUTOS (testing) - Argentina."
echo "Iniciando cron daemon..."

# Iniciar cron daemon
cron

# Loop para mantener el contenedor activo y monitorear cron
while true; do
    # Verificar si cron está ejecutándose (usando pidof que es más confiable)
    if ! pidof cron > /dev/null; then
        echo "$(TZ=America/Argentina/Buenos_Aires date): Cron daemon no está ejecutándose, reiniciando..."
        cron
    fi
    
    # Esperar 60 segundos antes de verificar nuevamente
    sleep 60
done