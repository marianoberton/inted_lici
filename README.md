# Pipeline de Licitaciones - Deploy para EasyPanel

Este directorio contiene la versión optimizada del Pipeline de Licitaciones preparada específicamente para despliegue en **EasyPanel**.

## 🔧 Configuración Segura de Credenciales

### Métodos de Configuración de Firebase

El pipeline soporta **múltiples métodos** para configurar las credenciales de Firebase de manera segura:

#### Opción 1: Variables de Entorno (Recomendado para Producción)

```bash
# Configurar credenciales como JSON string
export FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project-id",...}'
```

#### Opción 2: Archivo de Credenciales (Desarrollo Local)

```bash
# Configurar ruta al archivo de credenciales
export FIREBASE_CREDENTIALS_PATH="/path/to/your/firebase-credentials.json"
```

#### Opción 3: Credenciales por Defecto de Google Cloud

Para entornos de Google Cloud, el pipeline puede usar las credenciales por defecto automáticamente.

### Configuración en EasyPanel

1. **Crear las variables de entorno** en EasyPanel:
   - `FIREBASE_CREDENTIALS_JSON`: El contenido completo del archivo JSON de credenciales
   - `TELEGRAM_BOT_TOKEN`: Token del bot de Telegram
   - `TELEGRAM_CHAT_ID`: ID del chat de Telegram
   - `GEMINI_API_KEY`: Clave de API de Gemini

2. **Ejemplo de configuración**:
   ```
   FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"procesos-inted",...}
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=-1001234567890
   GEMINI_API_KEY=AIzaSyC...
   ```

## 🚀 Características

- ✅ **Pipeline completo** para CABA, PBA y Nación
- ✅ **Configuración segura** de credenciales Firebase
- ✅ **Docker optimizado** con Playwright preinstalado
- ✅ **Cron automático** configurado para ejecución diaria
- ✅ **Notificaciones Telegram** de novedades
- ✅ **Integración Firebase** Firestore
- ✅ **Procesamiento IA** con Gemini
- ✅ **Logs persistentes** y timestamps
- ✅ **Manejo de errores** robusto

## 📁 Estructura

```
deploy/
├── pipeline_licitaciones/     # Código principal del pipeline
│   ├── firebase_config.py     # Configuración segura de Firebase
│   ├── extraccion_*.py        # Scripts de extracción
│   ├── enviar_novedades*.py   # Scripts de notificaciones
│   └── ...
├── Dockerfile                 # Imagen Docker optimizada
├── docker-compose.yml         # Configuración de contenedor
├── entrypoint.sh             # Script de inicio
├── requirements.txt          # Dependencias Python
├── .env.example             # Plantilla de variables de entorno
└── README.md                # Esta documentación
```

## 🔒 Seguridad

- **❌ Sin credenciales hardcodeadas**: Todas las credenciales se manejan via variables de entorno
- **✅ Múltiples métodos de autenticación**: Flexibilidad para diferentes entornos
- **✅ Fallbacks seguros**: El sistema intenta múltiples métodos de autenticación
- **✅ Logs sin secretos**: Los logs no exponen información sensible

## 🐳 Despliegue

### En EasyPanel

1. **Crear nuevo servicio** desde repositorio Git
2. **Configurar variables de entorno** (ver sección anterior)
3. **Configurar volúmenes persistentes**:
   - `/app/data/logs` → Para logs
   - `/app/data/timestamps` → Para timestamps
4. **Configurar cron** (opcional): `0 9 * * *` para ejecución diaria a las 9 AM

### Localmente con Docker

```bash
# Clonar y configurar
git clone <repository-url>
cd deploy

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Construir y ejecutar
docker-compose up --build
```

## 📊 Monitoreo

- **Logs**: Disponibles en `/app/data/logs/`
- **Timestamps**: Guardados en `/app/data/timestamps/`
- **Notificaciones**: Enviadas automáticamente via Telegram
- **Estado**: Verificable via logs del contenedor

## 🔧 Troubleshooting

### Error de Credenciales Firebase

```
Error al inicializar Firebase: [Errno 2] No such file or directory
```

**Solución**: Verificar que `FIREBASE_CREDENTIALS_JSON` esté configurado correctamente.

### Error de Playwright

```
Playwright Chromium executable not found
```

**Solución**: El Dockerfile ya incluye la instalación de Chromium. Reconstruir la imagen.

### Error de Permisos

```
Permission denied: '/app/data/logs'
```

**Solución**: Verificar que los volúmenes estén configurados correctamente en EasyPanel.

## 📞 Soporte

Para problemas o consultas:
1. Revisar los logs del contenedor
2. Verificar la configuración de variables de entorno
3. Consultar la documentación de EasyPanel