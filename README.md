# Pipeline de Licitaciones - Deploy

Versión optimizada del Pipeline de Licitaciones para despliegue en contenedores.

## Configuración

### Variables de Entorno

El pipeline soporta múltiples métodos para configurar credenciales:

#### Opción 1: Variables de Entorno (Recomendado)
```bash
export FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
```

#### Opción 2: Archivo de Credenciales
```bash
export FIREBASE_CREDENTIALS_PATH="/path/to/credentials.json"
```

### Configuración en Plataformas Cloud

Crear las siguientes variables de entorno:
- `FIREBASE_CREDENTIALS_JSON`: Credenciales de base de datos
- `TELEGRAM_BOT_TOKEN`: Token de notificaciones
- `TELEGRAM_CHAT_ID`: ID de chat
- `GEMINI_API_KEY`: Clave de API de IA

## Características

- Pipeline completo automatizado
- Configuración segura de credenciales
- Docker optimizado
- Cron automático
- Notificaciones
- Integración con base de datos
- Procesamiento IA
- Logs persistentes
- Manejo de errores

## Estructura

```
deploy/
├── pipeline_licitaciones/     # Código principal
├── Dockerfile                 # Imagen Docker
├── docker-compose.yml         # Configuración
├── entrypoint.sh             # Script de inicio
├── requirements.txt          # Dependencias
└── .env.example             # Plantilla de variables
```

## Seguridad

- Sin credenciales hardcodeadas
- Múltiples métodos de autenticación
- Fallbacks seguros
- Logs sin secretos

## Uso

```bash
cp .env.example .env
# Configurar variables en .env
docker-compose up -d --build
```

## Logs

```bash
docker-compose logs -f
```