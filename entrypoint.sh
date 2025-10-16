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

# Crear archivo de variables de entorno para cron
echo "Exportando variables de entorno para cron..."
cat > /app/cron-env.sh << 'EOF'
#!/bin/bash
# Variables de entorno para cron
export TZ=America/Argentina/Buenos_Aires
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF

# Agregar todas las variables de entorno del contenedor al archivo
env | grep -E '^(TELEGRAM_|FIREBASE_|GOOGLE_|GEMINI_)' >> /app/cron-env.sh

# Hacer ejecutable el archivo de entorno
chmod +x /app/cron-env.sh

# Crear crontab con source del archivo de entorno
cat > /tmp/crontab << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=America/Argentina/Buenos_Aires
# Pipeline cada 15 minutos con variables de entorno
*/15 * * * * /bin/bash -c "source /app/cron-env.sh && cd /app && /usr/bin/python3 pipeline_licitaciones/run_pipeline.py" >> /app/data/logs/cron-pipeline.log 2>&1
# Heartbeat cada 5 minutos para verificar que cron funciona
*/5 * * * * /bin/echo "$(TZ=America/Argentina/Buenos_Aires /bin/date): Cron heartbeat - PID $$" >> /app/data/logs/cron-heartbeat.log 2>&1
# Test cada minuto para debugging con variables
* * * * * /bin/bash -c "source /app/cron-env.sh && /bin/echo \"$(TZ=America/Argentina/Buenos_Aires /bin/date): Cron test - Vars: TELEGRAM_TOKEN_CABA=\${TELEGRAM_TOKEN_CABA:0:10}...\"" >> /app/data/logs/cron-debug.log 2>&1
EOF

# Instalar crontab
echo "Instalando crontab..."
crontab /tmp/crontab

# Verificar que crontab se instaló correctamente
echo "Verificando crontab instalado:"
crontab -l

# Crear archivos de log iniciales
echo "Creando archivos de log iniciales..."
touch /app/data/logs/cron-pipeline.log
touch /app/data/logs/cron-heartbeat.log
touch /app/data/logs/cron-debug.log
touch /app/data/logs/cron-diagnostics.log

# Crear script de diagnóstico (si no existe)
cat > /app/debug_cron.sh << 'EOF'
#!/bin/bash

echo "=== DIAGNÓSTICO CRON - $(date) ===" >> /app/data/logs/cron-diagnostics.log

# 1. Estado del proceso cron
echo "1. Estado del proceso cron:" >> /app/data/logs/cron-diagnostics.log
ps aux | grep -E '[c]ron|CRON' >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log

# 2. Crontab instalado
echo "2. Crontab actual:" >> /app/data/logs/cron-diagnostics.log
crontab -l >> /app/data/logs/cron-diagnostics.log 2>&1
echo "" >> /app/data/logs/cron-diagnostics.log

# 3. Variables de entorno disponibles
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
    source /app/cron-env.sh && cd /app && timeout 60 /usr/bin/python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-diagnostics.log 2>&1
    echo "Exit code: $?" >> /app/data/logs/cron-diagnostics.log
else
    echo "No se puede ejecutar - archivo cron-env.sh no existe" >> /app/data/logs/cron-diagnostics.log
fi
echo "" >> /app/data/logs/cron-diagnostics.log

# 6. Logs de cron del sistema
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

echo "=== FIN DIAGNÓSTICO ===" >> /app/data/logs/cron-diagnostics.log
echo "" >> /app/data/logs/cron-diagnostics.log
EOF

# Hacer ejecutable el script de diagnóstico
chmod +x /app/debug_cron.sh

# Ejecutar diagnóstico inicial
echo "Ejecutando diagnóstico inicial de cron..."
/app/debug_cron.sh
chmod 666 /app/data/logs/cron-*.log

# Ejecutar pipeline al iniciar
echo "Ejecutando el pipeline al iniciar..."
cd /app
python3 pipeline_licitaciones/run_pipeline.py

# Iniciar cron en foreground y monitorear
echo "Pipeline iniciado. Cron configurado para ejecutar CADA 15 MINUTOS (testing) - Argentina."
echo "Iniciando cron daemon..."

# Iniciar cron en foreground con logging mejorado
echo "Iniciando cron daemon..."
service cron start

# Verificar que cron se inició correctamente
sleep 2
if pgrep cron > /dev/null; then
    echo "✓ Cron daemon iniciado correctamente"
else
    echo "✗ ERROR: Cron daemon no se pudo iniciar"
    exit 1
fi

# Ejecutar diagnóstico cada 5 minutos en background
(
    while true; do
        sleep 300  # 5 minutos
        /app/debug_cron.sh
    done
) &

# Mantener el contenedor activo y monitorear cron
echo "Contenedor iniciado. Monitoreando cron..."
while true; do
    if ! pgrep cron > /dev/null; then
        echo "$(date): ALERTA - Cron daemon se detuvo, reiniciando..." >> /app/data/logs/cron-diagnostics.log
        service cron start
        sleep 5
    fi
    sleep 30
done