# Guía de Seguridad - Pipeline de Licitaciones

## 🔒 Configuración Segura de Credenciales

### Firebase - Múltiples Métodos de Autenticación

El pipeline implementa un sistema robusto de autenticación Firebase que soporta múltiples métodos:

#### 1. Variables de Entorno (Recomendado para Producción)

**Método preferido para EasyPanel y entornos de producción:**

```bash
# Configurar el JSON completo como variable de entorno
FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"procesos-inted","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}'
```

**Ventajas:**
- ✅ No requiere archivos en el sistema de archivos
- ✅ Ideal para contenedores y servicios cloud
- ✅ Fácil rotación de credenciales
- ✅ No se expone en el código fuente

#### 2. Archivo de Credenciales (Desarrollo Local)

**Para desarrollo local y testing:**

```bash
# Configurar la ruta al archivo de credenciales
FIREBASE_CREDENTIALS_PATH="/path/to/your/firebase-credentials.json"
```

**Ventajas:**
- ✅ Fácil para desarrollo local
- ✅ Compatible con herramientas de Google Cloud
- ✅ Permite usar archivos existentes

#### 3. Credenciales por Defecto de Google Cloud

**Para entornos de Google Cloud Platform:**

El sistema automáticamente detecta y usa las credenciales por defecto cuando se ejecuta en:
- Google Cloud Run
- Google Compute Engine
- Google Kubernetes Engine
- Entornos con `gcloud auth application-default login`

## 🛡️ Implementación de Seguridad

### Clase FirebaseConfig

El archivo `firebase_config.py` implementa la lógica de seguridad:

```python
class FirebaseConfig:
    def __init__(self):
        # Intenta múltiples métodos de autenticación
        # 1. Variable de entorno JSON
        # 2. Archivo de credenciales
        # 3. Credenciales por defecto
        # 4. Búsqueda de archivo local (fallback)
```

### Orden de Prioridad

1. **FIREBASE_CREDENTIALS_JSON** - Variable de entorno con JSON completo
2. **FIREBASE_CREDENTIALS_PATH** - Ruta a archivo de credenciales
3. **Credenciales por defecto** - Google Cloud Application Default Credentials
4. **Búsqueda local** - Busca archivos `*firebase-adminsdk*.json` en el directorio

## 🔧 Configuración por Entorno

### EasyPanel (Producción)

1. **Ir a Variables de Entorno** en el panel de EasyPanel
2. **Agregar nueva variable:**
   - **Nombre:** `FIREBASE_CREDENTIALS_JSON`
   - **Valor:** El contenido completo del archivo JSON de credenciales

```json
{
  "type": "service_account",
  "project_id": "procesos-inted",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-xxx@procesos-inted.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxx%40procesos-inted.iam.gserviceaccount.com"
}
```

### Desarrollo Local

1. **Opción A - Archivo de credenciales:**
   ```bash
   # Descargar credenciales desde Firebase Console
   # Guardar como firebase-credentials.json
   export FIREBASE_CREDENTIALS_PATH="./firebase-credentials.json"
   ```

2. **Opción B - Variable de entorno:**
   ```bash
   # Copiar contenido del archivo JSON
   export FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
   ```

### Docker Local

```bash
# En .env
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"procesos-inted",...}

# O usando archivo
FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json
```

## 🚨 Mejores Prácticas de Seguridad

### ✅ DO (Hacer)

- **Usar variables de entorno** para credenciales en producción
- **Rotar credenciales** regularmente
- **Usar principio de menor privilegio** en permisos de Firebase
- **Monitorear accesos** en Firebase Console
- **Mantener `.gitignore` actualizado** para excluir credenciales
- **Usar diferentes credenciales** para diferentes entornos

### ❌ DON'T (No Hacer)

- **Nunca hardcodear** credenciales en el código
- **Nunca commitear** archivos de credenciales al repositorio
- **No compartir** credenciales por email o chat
- **No usar credenciales de producción** en desarrollo
- **No exponer credenciales** en logs o mensajes de error

## 🔍 Verificación de Configuración

### Script de Verificación

```bash
# Ejecutar verificación de Firebase
python pipeline_licitaciones/firebase_config.py
```

### Logs de Diagnóstico

El sistema registra información de diagnóstico (sin exponer secretos):

```
INFO: Intentando autenticación Firebase con variable de entorno JSON
INFO: Firebase inicializado correctamente con credenciales de entorno
```

## 🆘 Troubleshooting

### Error: "No se pudo inicializar Firebase"

**Posibles causas:**
1. Variable `FIREBASE_CREDENTIALS_JSON` mal formateada
2. Archivo de credenciales no encontrado
3. Permisos insuficientes en Firebase

**Soluciones:**
1. Verificar formato JSON válido
2. Comprobar ruta del archivo
3. Revisar permisos en Firebase Console

### Error: "Invalid JSON in FIREBASE_CREDENTIALS_JSON"

**Causa:** JSON mal formateado en la variable de entorno

**Solución:**
```bash
# Validar JSON antes de configurar
echo $FIREBASE_CREDENTIALS_JSON | python -m json.tool
```

### Error: "Permission denied"

**Causa:** Credenciales sin permisos suficientes

**Solución:**
1. Ir a Firebase Console → Project Settings → Service Accounts
2. Verificar roles asignados a la cuenta de servicio
3. Asegurar permisos de Firestore Database User

## 📋 Checklist de Seguridad

- [ ] Credenciales configuradas como variables de entorno
- [ ] Archivos de credenciales excluidos en `.gitignore`
- [ ] Historia de Git limpia (sin credenciales)
- [ ] Permisos mínimos necesarios en Firebase
- [ ] Monitoreo de accesos configurado
- [ ] Credenciales diferentes por entorno
- [ ] Rotación de credenciales programada
- [ ] Logs sin exposición de secretos

## 📞 Contacto de Seguridad

Para reportar problemas de seguridad o consultas sobre credenciales:
1. Revisar logs del contenedor
2. Verificar configuración de variables de entorno
3. Consultar Firebase Console para permisos
4. Contactar al administrador del proyecto