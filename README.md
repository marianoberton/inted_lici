# Pipeline de Licitaciones - Despliegue EasyPanel

Este directorio contiene los archivos mínimos necesarios para desplegar el pipeline de licitaciones en EasyPanel.

## Archivos Incluidos

### Archivos de Configuración
- `Dockerfile` - Imagen Docker optimizada
- `docker-compose.yml` - Configuración de servicios
- `entrypoint.sh` - Script de inicio del contenedor
- `.env.example` - Variables de entorno de ejemplo

### Código Fuente
- `pipeline_licitaciones/` - Módulo principal del pipeline
- `requirements.txt` - Dependencias Python
- `update_db.py` - Script de actualización de base de datos
- `timestamp_manager.py` - Gestor de timestamps

## Configuración para EasyPanel

### 1. Variables de Entorno
Configura estas variables en EasyPanel:

```
TELEGRAM_BOT_TOKEN=tu_token_de_bot_telegram
TELEGRAM_CHAT_ID=tu_chat_id_telegram
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
```

### 2. Volúmenes
Crea un volumen para persistir datos:
- `/app/data` - Para logs y timestamps

### 3. Despliegue
1. Sube este directorio a tu repositorio Git
2. Conecta el repositorio en EasyPanel
3. Configura las variables de entorno
4. Despliega el servicio

## Funcionalidad

El pipeline:
- Se ejecuta automáticamente al iniciar el contenedor
- Descarga datos de CABA, PBA y Nación
- Procesa y actualiza la base de datos Firebase
- Se programa para ejecutar diariamente a las 9:00 AM via cron
- Envía notificaciones por Telegram

## Logs

Los logs se guardan en `/app/data/logs/cron-pipeline.log` dentro del contenedor.

## Soporte

Para problemas o dudas, revisa los logs del contenedor en EasyPanel.