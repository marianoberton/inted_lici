# Configuración de Firebase para el Pipeline de Licitaciones

## Problema Identificado

El error que estás viendo indica que el contenedor Docker no puede autenticarse con Firebase porque está intentando usar **Application Default Credentials (ADC)** de Google Cloud, pero el contenedor no está ejecutándose en un entorno de Google Cloud.

```
ERROR:firebase_config:Error al inicializar Firebase: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc for more information.
```

## Solución Implementada

### 1. Configuración de Variables de Entorno

El sistema ahora soporta autenticación mediante **Service Account Key** usando variables de entorno. Hay dos opciones:

#### Opción 1: JSON completo como string (RECOMENDADO para Docker)
```bash
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"procesos-inted",...}
```

#### Opción 2: Ruta al archivo de credenciales
```bash
FIREBASE_CREDENTIALS_PATH=/app/pipeline_licitaciones/procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json
```

### 2. Pasos para Configurar

1. **Obtener las credenciales de Firebase:**
   - Ve a [Firebase Console](https://console.firebase.google.com/)
   - Selecciona tu proyecto `procesos-inted`
   - Ve a **Configuración del proyecto** > **Cuentas de servicio**
   - Haz clic en **Generar nueva clave privada**
   - Descarga el archivo JSON

2. **Configurar las variables de entorno:**
   - Copia `.env.example` a `.env`
   - Reemplaza el valor de `FIREBASE_CREDENTIALS_JSON` con el contenido completo del archivo JSON descargado
   - **IMPORTANTE:** El JSON debe estar en una sola línea, sin saltos de línea

3. **Ejemplo de configuración correcta:**
```bash
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"procesos-inted","private_key_id":"abc123","private_key":"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n","client_email":"firebase-adminsdk-qwt8a@procesos-inted.iam.gserviceaccount.com","client_id":"123456789","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs/firebase-adminsdk-qwt8a%40procesos-inted.iam.gserviceaccount.com"}
```

### 3. Orden de Prioridad de Autenticación

El sistema intentará autenticarse en este orden:

1. **FIREBASE_CREDENTIALS_JSON** (variable de entorno con JSON)
2. **FIREBASE_CREDENTIALS_PATH** (ruta al archivo de credenciales)
3. **Archivos en ubicaciones conocidas** (fallback)
4. **Credenciales por defecto de Google Cloud** (solo funciona en GCP)

### 4. Verificar la Configuración

Después de configurar las variables de entorno, puedes probar la conexión:

```bash
# Reconstruir la imagen
docker-compose build

# Probar la conexión a Firebase
docker-compose run --rm pipeline-licitaciones python -c "
from pipeline_licitaciones.firebase_config import get_firestore_client
print('Testing Firebase connection...')
client = get_firestore_client()
print('Firebase connection successful!')
"
```

### 5. Troubleshooting

- **Error de JSON malformado:** Asegúrate de que el JSON esté en una sola línea y que las comillas estén escapadas correctamente
- **Error de permisos:** Verifica que la cuenta de servicio tenga los permisos necesarios en Firebase
- **Error de proyecto:** Confirma que el `project_id` en las credenciales coincida con tu proyecto de Firebase

## Archivos Modificados

- `deploy/.env.example` - Agregada configuración de Firebase
- `deploy/docker-compose.yml` - Configurado para usar archivo .env
- `deploy/pipeline_licitaciones/firebase_config.py` - Ya tenía soporte para múltiples métodos de autenticación

## Próximos Pasos

1. Configura tu archivo `.env` con las credenciales reales
2. Reconstruye y ejecuta el contenedor
3. Verifica que el pipeline funcione correctamente