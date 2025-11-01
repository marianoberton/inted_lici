#!/bin/bash

# Configurar timezone ANTES de cualquier otra cosa
export TZ=America/Argentina/Buenos_Aires
ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Verificar timezone configurado
echo "Timezone configurado: $(date)"
echo "Timezone actual: $TZ"

# Convertir archivos a formato Unix (COMENTADO PARA DEBUG)
echo "DEBUG: Saltando conversión dos2unix..."
# find /app -type f \( -name "*.py" -o -name "*.sh" \) -exec dos2unix {} \;

# Crear directorios de logs
mkdir -p /app/data/logs
# Test de escritura en el directorio de logs
echo "Testing write permissions to /app/data/logs..."
if touch /app/data/logs/test.log; then
    echo "Write permissions are OK."
    rm /app/data/logs/test.log
else
    echo "ERROR: Cannot write to /app/data/logs. Check volume permissions."
fi


# Instalar navegadores de Playwright si faltan (Chromium)
echo "Verificando/instalando navegadores de Playwright (Chromium)..."
python3 -m playwright install chromium || true


# Configurar cron con timezone explícito - CADA 10 MINUTOS PARA TESTING
echo "Configurando cron..."

# Crear archivo de variables de entorno para cron
echo "Exportando variables de entorno para cron..."
cat > /app/cron-env.sh << 'EOF'
#!/bin/bash
# Variables de entorno para cron
export TZ=America/Argentina/Buenos_Aires
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
EOF

# Agregar todas las variables de entorno del contenedor al archivo, exportándolas con quoting seguro
env | grep -E '^(TELEGRAM_|FIREBASE_|GOOGLE_|GEMINI_|PLAYWRIGHT_)' | while IFS='=' read -r KEY VAL; do
    # Usar printf %q para escapar correctamente valores con espacios, comillas y saltos
    printf "export %s=%q\n" "$KEY" "$VAL"
done >> /app/cron-env.sh

# Alinear alias de variables de Telegram
cat >> /app/cron-env.sh << 'EOF'
# Aliases para variables de Telegram si faltan nombres alternativos
export TELEGRAM_TOKEN="${TELEGRAM_TOKEN_CABA:-$TELEGRAM_TOKEN}"
export TELEGRAM_CHAT_IDS="${TELEGRAM_CHAT_IDS_CABA:-$TELEGRAM_CHAT_IDS}"
EOF

# Hacer ejecutable el archivo de entorno
chmod +x /app/cron-env.sh

# Crear wrapper para la ejecución del pipeline con flock
cat > /app/run_pipeline_cron.sh << 'EOF'
#!/bin/bash
set -euo pipefail
source /app/cron-env.sh
export RUN_CONTEXT=cron
cd /app
if /usr/bin/flock -n /app/data/pipeline.lock -c "/usr/bin/python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-pipeline.log 2>&1"; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi
# Enviar reporte de estado siempre, incluso si falla el pipeline
/usr/bin/python3 pipeline_licitaciones/status_report.py --context "${RUN_CONTEXT}" --exit-code "${EXIT_CODE}" || true
exit "${EXIT_CODE}"
EOF
chmod +x /app/run_pipeline_cron.sh

# Configurar cron usando /etc/cron.d (más estable en contenedores)
# Permitir configurar los schedules vía variables de entorno (Easypanel)
CRON_SCHEDULE="${CRON_SCHEDULE:-*/10 * * * *}"
CRON_HEARTBEAT_SCHEDULE="${CRON_HEARTBEAT_SCHEDULE:-*/5 * * * *}"
CRON_DEBUG_SCHEDULE="${CRON_DEBUG_SCHEDULE:-* * * * *}"
cat > /etc/cron.d/pipeline << EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TZ=America/Argentina/Buenos_Aires

# Heartbeat cada 5 minutos para verificar que cron funciona
$CRON_HEARTBEAT_SCHEDULE root /bin/bash -lc 'date "+%Y-%m-%d %H:%M:%S - cron alive" >> /app/data/logs/cron-heartbeat.log'

# Pipeline cada 10 minutos usando wrapper (carga env y usa flock)
$CRON_SCHEDULE root /bin/bash -lc '/app/run_pipeline_cron.sh'

# Test de variables cada minuto (opcional)
$CRON_DEBUG_SCHEDULE root /bin/bash -lc 'source /app/cron-env.sh && L="\${TELEGRAM_TOKEN_CABA:-}"; echo "\$(date): Cron test - TELEGRAM_TOKEN_CABA len=\${#L}" >> /app/data/logs/cron-debug.log'
EOF
chmod 0644 /etc/cron.d/pipeline

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
    source /app/cron-env.sh && cd /app && timeout 600 /usr/bin/python3 pipeline_licitaciones/run_pipeline.py >> /app/data/logs/cron-diagnostics.log 2>&1
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
EOF

# Hacer ejecutable el script de diagnóstico
chmod +x /app/debug_cron.sh

# Ejecutar diagnóstico inicial
echo "Ejecutando diagnóstico inicial de cron..."
/app/debug_cron.sh
chmod 666 /app/data/logs/cron-*.log

# Enviar reporte inicial de estado a Telegram
echo "Enviando reporte de estado inicial a Telegram..."
export RUN_CONTEXT=startup
python3 pipeline_licitaciones/status_report.py --context "${RUN_CONTEXT}" || true

# Ejecutar pipeline al iniciar
# echo "Ejecutando el pipeline al iniciar..."
# cd /app
# python3 pipeline_licitaciones/run_pipeline.py

# Iniciar cron en foreground y monitorear
echo "Pipeline iniciado. Cron configurado para ejecutar CADA 10 MINUTOS (testing) - Argentina."
echo "Iniciando cron daemon..."

# Ejecutar el pipeline una vez al iniciar, protegido por flock
bash -lc '/app/run_pipeline_cron.sh' || true

# Iniciar cron en foreground (proceso principal del contenedor)
echo "Iniciando cron en foreground como proceso principal..."
exec cron -f