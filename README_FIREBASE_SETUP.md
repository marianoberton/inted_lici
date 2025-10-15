# Configuración de Firebase

## Problema

Error de autenticación con Firebase en contenedores Docker que no pueden usar Application Default Credentials (ADC).

## Solución

### Variables de Entorno

El sistema soporta autenticación mediante Service Account Key:

#### Opción 1: JSON como string (Recomendado)
```bash
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project",...}
```

#### Opción 2: Ruta al archivo
```bash
FIREBASE_CREDENTIALS_PATH=/path/to/credentials.json
```

### Configuración

1. **Obtener credenciales:**
   - Acceder a Firebase Console
   - Ir a Configuración del proyecto > Cuentas de servicio
   - Generar nueva clave privada
   - Descargar archivo JSON

2. **Configurar variables:**
   - Copiar `.env.example` a `.env`
   - Reemplazar `FIREBASE_CREDENTIALS_JSON` con el contenido del archivo
   - El JSON debe estar en una sola línea

### Orden de Autenticación

1. `FIREBASE_CREDENTIALS_JSON` (variable de entorno)
2. `FIREBASE_CREDENTIALS_PATH` (archivo)
3. Ubicaciones conocidas de archivos
4. Google Cloud default credentials

### Verificación

```bash
# Probar conexión
docker-compose exec pipeline python -c "from pipeline_licitaciones.firebase_config import get_firestore_client; client = get_firestore_client(); print('Conexión exitosa')"
```

### Troubleshooting

- **Error de credenciales**: Verificar formato JSON
- **Error de permisos**: Verificar roles en Firebase Console
- **Error de conexión**: Verificar conectividad de red

## Seguridad

- Usar variables de entorno para credenciales
- No incluir credenciales en código
- Verificar que `.env` esté en `.gitignore`