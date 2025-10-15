import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import os
import requests
import pytz
import json
import time
import sys
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Inicializar Firestore
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
cred_path = os.path.join(script_dir, 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
if not os.path.exists(cred_path):
    # Intentar ruta alternativa
    cred_path = os.path.join('pipeline_licitaciones', 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
cred = credentials.Certificate(cred_path)

# Verificar si Firebase ya está inicializado
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
else:
    print("Firebase ya está inicializado, usando la instancia existente")

db = firestore.client()

# ---------------------------
# Configuración del Bot Original (CABA - Excluye código repartición 400-499)
# ---------------------------
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_CABA')
TELEGRAM_CHAT_IDS = [-4815571002]  # Chat ID correcto con signo negativo para grupos

# ---------------------------
# Configuración del Bot Salud Nuevo (Procesos Salud - Código repartición 400-499)
# ---------------------------
SALUD_NUEVO_TELEGRAM_TOKEN = '7841576758:AAFx8WgMUopKFKeJJ_HlepqGN-BRxP4kwtE'
SALUD_NUEVO_TELEGRAM_CHAT_IDS = [-4815571002]  # Solo el grupo principal

# ---------------------------
# Configuración del Bot Salud Segundo (Insumos Específicos)
# ---------------------------
SALUD_SEGUNDO_TELEGRAM_TOKEN = '8198330250:AAGaJhK0YxHPrCwU8gAbRveBrLHSNmTzt6Q'
SALUD_SEGUNDO_TELEGRAM_CHAT_IDS = [-4815571002]  # Solo el grupo principal

# Prefijos a buscar en codigo_item para el bot segundo de salud
SALUD_TARGET_PREFIXES = [
    "33.11.001.",
    "33.11.003.",
    "35.01.001.",
]

# Ruta al archivo donde almacenaremos el último timestamp procesado (ajustado para Windows)
LAST_TIMESTAMP_FILE = 'pipeline_licitaciones/last_extraction_timestamp.txt'

def enviar_mensaje_telegram(mensaje, chat_ids, token=None):
    """Función genérica para enviar mensajes a Telegram"""
    if token is None:
        token = TELEGRAM_TOKEN
    
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    for chat_id in chat_ids:
        payload = {
            'chat_id': chat_id,
            'text': mensaje,
            'parse_mode': 'Markdown'
        }
        for intento in range(3):  # Intentar enviar hasta 3 veces
            try:
                response = requests.post(url, data=payload)
                if response.status_code == 200:
                    print(f"Mensaje enviado correctamente a {chat_id}")
                    time.sleep(1)  # Pausa de 1 segundo para no saturar la API
                    break
                else:
                    print(f"Error al enviar mensaje a {chat_id}: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Intento {intento + 1} - Error de conexión al enviar mensaje: {e}")
                time.sleep(2)  # Esperar 2 segundos antes de reintentar

def enviar_mensaje_salud_nuevo(mensaje):
    """Envía mensaje al bot de Salud Nuevo"""
    enviar_mensaje_telegram(mensaje, SALUD_NUEVO_TELEGRAM_CHAT_IDS, SALUD_NUEVO_TELEGRAM_TOKEN)

def enviar_mensaje_salud_segundo(mensaje):
    """Envía mensaje al bot de Salud Segundo"""
    enviar_mensaje_telegram(mensaje, SALUD_SEGUNDO_TELEGRAM_CHAT_IDS, SALUD_SEGUNDO_TELEGRAM_TOKEN)

def obtener_ultimo_timestamp():
    """Obtiene el último timestamp desde Firebase"""
    try:
        # Intentar obtener desde Firebase primero
        config_ref = db.collection('config').document('last_timestamp')
        config_doc = config_ref.get()
        
        if config_doc.exists:
            data = config_doc.to_dict()
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Convertir a zona horaria de Argentina para mostrar
                    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
                    timestamp_argentina = timestamp.astimezone(argentina_tz)
                    print(f"Timestamp obtenido de Firebase: {timestamp} (Argentina: {timestamp_argentina.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                    return timestamp
                except ValueError as e:
                    print(f"Error al parsear timestamp de Firebase: {e}")
        
        # Fallback al archivo local si Firebase no tiene datos
        if os.path.exists(LAST_TIMESTAMP_FILE):
            with open(LAST_TIMESTAMP_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                if timestamp_str:
                    try:
                        timestamp = datetime.datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
                        # Convertir a zona horaria de Argentina para mostrar
                        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
                        timestamp_argentina = timestamp.astimezone(argentina_tz)
                        print(f"Timestamp obtenido del archivo: {timestamp} (Argentina: {timestamp_argentina.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                        return timestamp
                    except ValueError as e:
                        print(f"Error al parsear el timestamp del archivo: {e}")
        
        print("No se encontró timestamp, usando fecha por defecto")
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        
    except Exception as e:
        print(f"Error obteniendo timestamp: {e}")
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

def guardar_ultimo_timestamp(timestamp):
    """Guarda el timestamp tanto en Firebase como en archivo local"""
    try:
        # Convertir a zona horaria de Argentina
        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        timestamp_argentina = timestamp.astimezone(argentina_tz)
        # Usar el timestamp en zona horaria de Argentina para guardar
        timestamp_str = timestamp_argentina.isoformat()
        
        # Guardar en Firebase
        config_ref = db.collection('config').document('last_timestamp')
        config_ref.set({
            'timestamp': timestamp_str,
            'updated_at': datetime.datetime.now(argentina_tz).isoformat(),
            'source': 'enviar_novedades_caba'
        })
        print(f"Timestamp guardado en Firebase: {timestamp_str} (Argentina: {timestamp_argentina.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        
        # Guardar en archivo local como backup
        with open(LAST_TIMESTAMP_FILE, 'w') as f:
            f.write(timestamp_str)
        print(f"Timestamp guardado en archivo: {timestamp_str}")
        
    except Exception as e:
        print(f"Error guardando timestamp: {e}")
        # Intentar guardar solo en archivo si Firebase falla
        try:
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            timestamp_argentina = timestamp.astimezone(argentina_tz)
            with open(LAST_TIMESTAMP_FILE, 'w') as f:
                f.write(timestamp_argentina.isoformat())
            print(f"Timestamp guardado solo en archivo como fallback")
        except Exception as e2:
            print(f"Error guardando timestamp en archivo: {e2}")

def obtener_y_clasificar_nuevos_documentos():
    """
    Obtiene y clasifica los nuevos documentos para cada bot:
    - Bot Original (CABA): documentos que NO tienen código repartición 400-499
    - Bot Salud Nuevo: documentos con código repartición 400-499
    - Bot Salud Segundo: documentos con código repartición 400-499 Y que tienen códigos de item específicos
    """
    ultimo_timestamp = obtener_ultimo_timestamp()
    print(f"Último timestamp procesado: {ultimo_timestamp}")

    # Obtener todos los documentos ordenados por timestamp
    docs = db.collection('procesos-bac').order_by('timestamp').stream()
    documentos_clasificados = {
        "docs_caba": [],
        "docs_salud_nuevo": [],
        "docs_salud_segundo": []
    }
    documentos_procesados = []  # Para trackear todos los documentos procesados
    
    for doc in docs:
        data = doc.to_dict()
        timestamp_str = data.get('timestamp')
        
        # Intentar parsear el timestamp
        if isinstance(timestamp_str, str):
            try:
                timestamp_dt = datetime.datetime.fromisoformat(timestamp_str)
                if timestamp_dt.tzinfo is None:
                    # Añadir zona horaria UTC si falta
                    timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                print(f"Formato de timestamp inválido para el documento {doc.id}: {timestamp_str}")
                continue
        elif isinstance(timestamp_str, datetime.datetime):
            timestamp_dt = timestamp_str
            if timestamp_dt.tzinfo is None:
                timestamp_dt = timestamp_dt.replace(tzinfo=datetime.timezone.utc)
        else:
            print(f"Tipo de timestamp no válido para el documento {doc.id}: {type(timestamp_str)}")
            continue

        # Solo procesar documentos nuevos
        if timestamp_dt > ultimo_timestamp:
            # Agregar a documentos procesados para actualizar timestamp
            documentos_procesados.append(data)
            
            # Verificar codigo_reparticion para clasificación
            codigo_reparticion = data.get('codigo_reparticion')
            es_salud = False
            
            if codigo_reparticion:
                try:
                    codigo_reparticion_num = int(codigo_reparticion)
                    if 400 <= codigo_reparticion_num <= 499:
                        es_salud = True
                        # Agregar a documentos de salud nuevo
                        documentos_clasificados["docs_salud_nuevo"].append(data)
                        print(f"Documento {doc.id} clasificado para Bot Salud Nuevo (Repartición: {codigo_reparticion_num})")
                        
                        # Verificar si también aplica para el bot segundo de salud
                        detalle_productos_json = data.get('detalle_productos')
                        if detalle_productos_json and isinstance(detalle_productos_json, str):
                            try:
                                detalle_productos_list = json.loads(detalle_productos_json)
                                if isinstance(detalle_productos_list, list):
                                    match_segundo = False
                                    for item in detalle_productos_list:
                                        if isinstance(item, dict):
                                            codigo_item = item.get('codigo_item')
                                            if codigo_item and isinstance(codigo_item, str):
                                                for prefix in SALUD_TARGET_PREFIXES:
                                                    if codigo_item.startswith(prefix):
                                                        print(f"Doc {doc.id} - Coincidencia encontrada: '{codigo_item}' con prefijo '{prefix}'")
                                                        match_segundo = True
                                                        break
                                                if match_segundo:
                                                    break
                                    
                                    if match_segundo:
                                        documentos_clasificados["docs_salud_segundo"].append(data)
                                        print(f"Documento {doc.id} también clasificado para Bot Salud Segundo")
                            except json.JSONDecodeError:
                                print(f"Error al decodificar JSON detalle_productos en documento {doc.id}")
                    else:
                        # No es salud, agregar a CABA
                        documentos_clasificados["docs_caba"].append(data)
                        print(f"Documento {doc.id} clasificado para Bot CABA (Repartición: {codigo_reparticion_num})")
                except ValueError:
                    print(f"codigo_reparticion no es un número válido en el documento {doc.id}")
                    # Si no se puede parsear, agregar a CABA por defecto
                    documentos_clasificados["docs_caba"].append(data)
            else:
                print(f"No se encontró codigo_reparticion en el documento {doc.id}")
                # Sin código de repartición, agregar a CABA por defecto
                documentos_clasificados["docs_caba"].append(data)

    # Actualizar el último timestamp si hay documentos procesados
    if documentos_procesados:
        nuevo_ultimo_timestamp = max(
            datetime.datetime.fromisoformat(doc['timestamp'])
            if isinstance(doc['timestamp'], str) else doc['timestamp']
            for doc in documentos_procesados
        )
        if nuevo_ultimo_timestamp.tzinfo is None:
            nuevo_ultimo_timestamp = nuevo_ultimo_timestamp.replace(tzinfo=datetime.timezone.utc)
        guardar_ultimo_timestamp(nuevo_ultimo_timestamp)

    return documentos_clasificados

def generar_mensaje(doc):
    """
    Construye un mensaje formateado en Markdown utilizando la información 
    contenida en los campos 'informacion_basica', 'monto_duracion' y 'cronograma'.
    """
    mensaje = "*Nuevo Proceso Agregado*\n\n"
    
    try:
        # Información básica
        info_basica_json = doc.get('informacion_basica', '{}')
        info_basica = json.loads(info_basica_json if info_basica_json else '{}')
        if not isinstance(info_basica, dict):
            info_basica = {}
    except json.JSONDecodeError:
        info_basica = {}
    
    mensaje += f"*N° de proceso:* `{info_basica.get('numero_proceso', 'N/A')}`\n"
    mensaje += f"*Nombre de proceso:* {info_basica.get('nombre_proceso', 'N/A')}\n"
    mensaje += f"*Objeto del proceso:* {info_basica.get('objeto_contratacion', 'N/A')}\n"
    mensaje += f"*Procedimiento:* {info_basica.get('procedimiento_seleccion', 'N/A')}\n"
    mensaje += f"*Modalidad:* {info_basica.get('modalidad', 'N/A')}\n\n"

    try:
        # Monto y duración
        monto_duracion_json = doc.get('monto_duracion', '{}')
        monto_duracion = json.loads(monto_duracion_json if monto_duracion_json else '{}')
        if not isinstance(monto_duracion, dict):
            monto_duracion = {}
    except json.JSONDecodeError:
        monto_duracion = {}

    mensaje += f"*Monto:* {monto_duracion.get('monto', 'N/A')}\n"
    mensaje += f"*Duración:* {monto_duracion.get('duracion_contrato', 'N/A')}\n\n"

    try:
        # Cronograma
        cronograma_json = doc.get('cronograma', '{}')
        cronograma = json.loads(cronograma_json if cronograma_json else '{}')
        if not isinstance(cronograma, dict):
            cronograma = {}
    except json.JSONDecodeError:
        cronograma = {}

    mensaje += f"*Publicación:* {cronograma.get('fecha_publicacion', 'N/A')}\n"
    mensaje += f"*Inicio Consultas:* {cronograma.get('fecha_inicio_consultas', 'N/A')}\n"
    mensaje += f"*Fin Consultas:* {cronograma.get('fecha_final_consultas', 'N/A')}\n"
    mensaje += f"*Apertura:* {cronograma.get('fecha_acto_apertura', 'N/A')}\n"

    # Limitar longitud del mensaje si es necesario (Telegram tiene límites)
    max_len = 4096
    if len(mensaje) > max_len:
        mensaje = mensaje[:max_len - 4] + "..."

    return mensaje

def generar_mensaje_salud_segundo(doc):
    """
    Construye un mensaje especial y llamativo para el Bot Salud Segundo (Insumos Específicos)
    con emojis y formato más colorido ya que es menos habitual.
    """
    mensaje = "🚨🚨 *¡ALERTA INSUMOS ESPECÍFICOS!* 🚨🚨\n"
    mensaje += "🏥💊 *PROCESO DE SALUD PRIORITARIO* 💊🏥\n\n"
    
    try:
        # Información básica
        info_basica_json = doc.get('informacion_basica', '{}')
        info_basica = json.loads(info_basica_json if info_basica_json else '{}')
        if not isinstance(info_basica, dict):
            info_basica = {}
    except json.JSONDecodeError:
        info_basica = {}
    
    mensaje += f"🔢 *N° de proceso:* `{info_basica.get('numero_proceso', 'N/A')}`\n"
    mensaje += f"📋 *Nombre de proceso:* {info_basica.get('nombre_proceso', 'N/A')}\n"
    mensaje += f"🎯 *Objeto del proceso:* {info_basica.get('objeto_contratacion', 'N/A')}\n"
    mensaje += f"⚙️ *Procedimiento:* {info_basica.get('procedimiento_seleccion', 'N/A')}\n"
    mensaje += f"📊 *Modalidad:* {info_basica.get('modalidad', 'N/A')}\n\n"

    try:
        # Monto y duración
        monto_duracion_json = doc.get('monto_duracion', '{}')
        monto_duracion = json.loads(monto_duracion_json if monto_duracion_json else '{}')
        if not isinstance(monto_duracion, dict):
            monto_duracion = {}
    except json.JSONDecodeError:
        monto_duracion = {}

    mensaje += f"💰 *Monto:* {monto_duracion.get('monto', 'N/A')}\n"
    mensaje += f"⏱️ *Duración:* {monto_duracion.get('duracion_contrato', 'N/A')}\n\n"

    try:
        # Cronograma
        cronograma_json = doc.get('cronograma', '{}')
        cronograma = json.loads(cronograma_json if cronograma_json else '{}')
        if not isinstance(cronograma, dict):
            cronograma = {}
    except json.JSONDecodeError:
        cronograma = {}

    mensaje += "📅 *FECHAS IMPORTANTES:*\n"
    mensaje += f"📢 *Publicación:* {cronograma.get('fecha_publicacion', 'N/A')}\n"
    mensaje += f"❓ *Inicio Consultas:* {cronograma.get('fecha_inicio_consultas', 'N/A')}\n"
    mensaje += f"⏰ *Fin Consultas:* {cronograma.get('fecha_final_consultas', 'N/A')}\n"
    mensaje += f"🔓 *Apertura:* {cronograma.get('fecha_acto_apertura', 'N/A')}\n\n"
    
    mensaje += "⚡ *¡ATENCIÓN ESPECIAL REQUERIDA!* ⚡\n"
    mensaje += "🎯 Este proceso incluye insumos específicos de salud"

    # Limitar longitud del mensaje si es necesario (Telegram tiene límites)
    max_len = 4096
    if len(mensaje) > max_len:
        mensaje = mensaje[:max_len - 4] + "..."

    return mensaje

def main():
    try:
        documentos_clasificados = obtener_y_clasificar_nuevos_documentos()
        docs_caba = documentos_clasificados.get("docs_caba", [])
        docs_salud_nuevo = documentos_clasificados.get("docs_salud_nuevo", [])
        docs_salud_segundo = documentos_clasificados.get("docs_salud_segundo", [])

        count_caba = 0
        count_salud_nuevo = 0
        count_salud_segundo = 0

        # Enviar mensajes para Bot CABA
        print(f"Enviando {len(docs_caba)} mensajes para Bot CABA...")
        if docs_caba:
            for doc in docs_caba:
                try:
                    mensaje = generar_mensaje(doc)
                    enviar_mensaje_telegram(mensaje, TELEGRAM_CHAT_IDS)
                    count_caba += 1
                except Exception as e:
                    print(f"Error al generar o enviar mensaje para Bot CABA: {e}")

        # Enviar mensajes para Bot Salud Nuevo
        print(f"Enviando {len(docs_salud_nuevo)} mensajes para Bot Salud Nuevo...")
        if docs_salud_nuevo:
            for doc in docs_salud_nuevo:
                try:
                    mensaje = generar_mensaje(doc)
                    enviar_mensaje_salud_nuevo(mensaje)
                    count_salud_nuevo += 1
                    time.sleep(1) # Pausa de 1 segundo entre mensajes
                except Exception as e:
                    print(f"Error al generar o enviar mensaje para Bot Salud Nuevo: {e}")

        # Enviar mensajes para Bot Salud Segundo
        print(f"Enviando {len(docs_salud_segundo)} mensajes para Bot Salud Segundo...")
        if docs_salud_segundo:
            for doc in docs_salud_segundo:
                try:
                    mensaje = generar_mensaje_salud_segundo(doc)  # Usar función especial con formato llamativo
                    enviar_mensaje_salud_segundo(mensaje)
                    count_salud_segundo += 1
                    time.sleep(1) # Pausa de 1 segundo entre mensajes
                except Exception as e:
                    print(f"Error al generar o enviar mensaje para Bot Salud Segundo: {e}")

        # Resumen
        total_procesados = count_caba + count_salud_nuevo + count_salud_segundo
        if total_procesados > 0:
            print(f"Procesamiento completado:")
            print(f"- Bot CABA: {count_caba} mensajes")
            print(f"- Bot Salud Nuevo: {count_salud_nuevo} mensajes")
            print(f"- Bot Salud Segundo: {count_salud_segundo} mensajes")
            print(f"- Total: {total_procesados} mensajes")
        else:
            print("No se encontraron nuevos documentos para ningún bot")
            
    except Exception as e:
        print(f"Error en enviar_novedades.py: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
    sys.exit(0)
