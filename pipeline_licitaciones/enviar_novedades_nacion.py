import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import os
import requests
import pytz
import json
import time
import sys

# Path to the credentials file - usando ruta relativa
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
LAST_TIMESTAMP_FILE = os.path.join(script_dir, 'last_extraction_timestamp_nacion.txt')

# Inicializar Firestore
cred = credentials.Certificate(cred_path)
# Use a unique app name if running multiple initializations from the same process, otherwise default is fine.
try:
    firebase_admin.get_app(name='nacion_sender')
except ValueError:
    firebase_admin.initialize_app(cred, name='nacion_sender')

app_instance = firebase_admin.get_app(name='nacion_sender')
db = firestore.client(app=app_instance)

# Configurar el token y el chat ID de Telegram
# TODO: Reemplazar con el TOKEN del NUEVO BOT para NACION si es diferente.
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_NACION')
TELEGRAM_CHAT_IDS = [1880232778, 439570532, 8029466525] # Mismos CHAT IDs

def enviar_mensaje_telegram(mensaje, chat_ids):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
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
                    print(f"Mensaje NACION enviado correctamente a {chat_id}")
                    break
                else:
                    print(f"Error al enviar mensaje NACION a {chat_id}: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Intento {intento + 1} - Error de conexión al enviar mensaje NACION: {e}")
                time.sleep(2)  # Esperar 2 segundos antes de reintentar

def obtener_ultimo_timestamp():
    if os.path.exists(LAST_TIMESTAMP_FILE):
        with open(LAST_TIMESTAMP_FILE, 'r') as f:
            timestamp_str = f.read().strip()
            if timestamp_str:
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
                    return timestamp
                except ValueError as e:
                    print(f"Error al parsear el timestamp del archivo ({LAST_TIMESTAMP_FILE}): {e}")
                    return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

def guardar_ultimo_timestamp(timestamp):
    with open(LAST_TIMESTAMP_FILE, 'w') as f:
        f.write(timestamp.isoformat())

def obtener_nuevos_documentos():
    ultimo_timestamp = obtener_ultimo_timestamp()
    print(f"Último timestamp procesado para NACION (desde {LAST_TIMESTAMP_FILE}): {ultimo_timestamp.isoformat()}")

    docs_query = db.collection('procesos-nacion').order_by('timestamp_extraccion').where(filter=firestore.FieldFilter('timestamp_extraccion', '>', ultimo_timestamp.isoformat()))
    nuevos_documentos_data = []
    
    # Obtener fecha actual
    fecha_actual = datetime.datetime.now(pytz.UTC)
    
    for doc in docs_query.stream():
        data = doc.to_dict()
        data['firestore_doc_id'] = doc.id  # Incluir el ID del documento de Firestore
        timestamp_str = data.get('timestamp_extraccion')
        if not timestamp_str: # Si no hay timestamp, no podemos procesar
            print(f"Documento {data['firestore_doc_id']} no tiene timestamp_extraccion. Omitiendo.")
            continue

        try:
            # No es necesario re-parsear el timestamp_dt aquí si la query ya lo usa.
            # Pero lo mantenemos por si se quiere añadir lógica de filtro adicional en Python.
            datetime.datetime.fromisoformat(timestamp_str) # Solo para validar formato
        except ValueError:
            print(f"Formato de timestamp_extraccion inválido para el documento {data['firestore_doc_id']}: {timestamp_str}")
            continue
        
        # FILTRO NUEVO: Verificar que la fecha de apertura sea posterior a la fecha actual
        try:
            cronograma_str = data.get('cronograma', '{}')
            cronograma = json.loads(cronograma_str)
            fecha_apertura_str = cronograma.get('fecha_acto_apertura')
            
            if fecha_apertura_str:
                # Parsear la fecha de apertura - manejar formato DD/MM/YYYY HH:MM Hrs.
                try:
                    # Limpiar el formato: remover " Hrs." y parsear DD/MM/YYYY HH:MM
                    fecha_limpia = fecha_apertura_str.replace(' Hrs.', '').strip()
                    fecha_apertura = datetime.datetime.strptime(fecha_limpia, '%d/%m/%Y %H:%M')
                    # Asignar timezone UTC si no tiene
                    if fecha_apertura.tzinfo is None:
                        fecha_apertura = fecha_apertura.replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    # Si falla el formato DD/MM/YYYY HH:MM, intentar formato ISO
                    try:
                        fecha_apertura = datetime.datetime.fromisoformat(fecha_apertura_str)
                        if fecha_apertura.tzinfo is None:
                            fecha_apertura = fecha_apertura.replace(tzinfo=datetime.timezone.utc)
                    except ValueError:
                        print(f"Formato de fecha no reconocido para documento {data['firestore_doc_id']}: {fecha_apertura_str}")
                        continue
                
                # Solo incluir si la fecha de apertura es posterior a la fecha actual
                if fecha_apertura > fecha_actual:
                    nuevos_documentos_data.append(data)
                    print(f"Documento {data['firestore_doc_id']} incluido - fecha apertura: {fecha_apertura_str}")
                else:
                    print(f"Documento {data['firestore_doc_id']} omitido - fecha apertura anterior: {fecha_apertura_str}")
            else:
                print(f"Documento {data['firestore_doc_id']} omitido - sin fecha de apertura")
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error procesando fecha de apertura para documento {data['firestore_doc_id']}: {e}")
            # Si no se puede procesar la fecha, omitir el documento
            continue
        
        # Comentando el filtro de codigo_reparticion como se discutió
        # codigo_reparticion = data.get('codigo_reparticion')
        # if codigo_reparticion:
        #     # Lógica de filtro específica para NACION si es necesaria
        #     pass

    if nuevos_documentos_data:
        # El timestamp en NACION es 'timestamp_extraccion', que es un string ISO
        # Encontrar el timestamp más reciente entre los nuevos documentos para guardarlo
        nuevo_ultimo_timestamp_str = max(d['timestamp_extraccion'] for d in nuevos_documentos_data if 'timestamp_extraccion' in d)
        if nuevo_ultimo_timestamp_str:
            nuevo_ultimo_timestamp_dt = datetime.datetime.fromisoformat(nuevo_ultimo_timestamp_str)
            if nuevo_ultimo_timestamp_dt.tzinfo is None:
                nuevo_ultimo_timestamp_dt = nuevo_ultimo_timestamp_dt.replace(tzinfo=datetime.timezone.utc)
            guardar_ultimo_timestamp(nuevo_ultimo_timestamp_dt)
            print(f"Guardado nuevo último timestamp para NACION en {LAST_TIMESTAMP_FILE}: {nuevo_ultimo_timestamp_dt.isoformat()}")

    return nuevos_documentos_data

def main():
    try:
        nuevos_documentos = obtener_nuevos_documentos()
        if nuevos_documentos:
            print(f"Se encontraron {len(nuevos_documentos)} nuevos documentos de NACION.")
            for doc_data in nuevos_documentos:
                mensaje = "*Nuevo Proceso NACIÓN Agregado*\n"
                doc_id_for_log = doc_data.get('firestore_doc_id', doc_data.get('numero_proceso_buscado', 'ID DESCONOCIDO'))
                
                try:
                    info_basica_str = doc_data.get('informacion_basica', '{}')
                    info_basica = json.loads(info_basica_str)
                except json.JSONDecodeError as e_json:
                    info_basica = {}
                    print(f"Error decodificando JSON para 'informacion_basica' en Doc ID: {doc_id_for_log}. Error: {e_json}. Contenido: '{info_basica_str[:200]}...'")

                try:
                    info_contrato_str = doc_data.get('info_contrato', '{}')
                    info_contrato = json.loads(info_contrato_str)
                except json.JSONDecodeError as e_json:
                    info_contrato = {}
                    print(f"Error decodificando JSON para 'info_contrato' en Doc ID: {doc_id_for_log}. Error: {e_json}. Contenido: '{info_contrato_str[:200]}...'")
                
                try:
                    cronograma_str = doc_data.get('cronograma', '{}')
                    cronograma = json.loads(cronograma_str)
                except json.JSONDecodeError as e_json:
                    cronograma = {}
                    print(f"Error decodificando JSON para 'cronograma' en Doc ID: {doc_id_for_log}. Error: {e_json}. Contenido: '{cronograma_str[:200]}...'")

                mensaje += f"*N° de proceso:* {info_basica.get('numero_proceso', doc_data.get('numero_proceso', 'N/A'))}\n"
                mensaje += f"*Nombre de proceso:* {info_basica.get('nombre_proceso', 'N/A')}\n"
                mensaje += f"*Objeto del proceso:* {info_basica.get('objeto_contratacion', 'N/A')}\n"
                mensaje += f"*Procedimiento de selección:* {info_basica.get('procedimiento_seleccion', 'N/A')}\n"
                mensaje += f"*Modalidad:* {info_basica.get('modalidad', 'N/A')}\n"
                mensaje += f"*Monto:* N/A\n" # Monto no presente en datos de NACION
                mensaje += f"*Duración del contrato:* {info_contrato.get('duracion_contrato', 'N/A')}\n"
                mensaje += f"*Fecha y hora final de consultas:* {cronograma.get('fecha_final_consultas', 'N/A')}\n"
                mensaje += f"*Fecha y hora acto de apertura:* {cronograma.get('fecha_acto_apertura', 'N/A')}\n"

                enviar_mensaje_telegram(mensaje, TELEGRAM_CHAT_IDS)
        else:
            print("No se encontraron nuevos documentos de NACION.")
    except Exception as e:
        print(f"Error en la función principal de enviar_novedades_nacion.py: {e}")
        # sys.exit(1) # Comentado para evitar salida abrupta si es parte de un flujo mayor
    # finally:
        # No es estrictamente necesario eliminar la app si se va a ejecutar como script individual y termina.
        # Si es parte de un proceso más largo donde se inicializan múltiples apps, podría ser útil.
        # try:
        #     app_instance = firebase_admin.get_app(name='nacion_sender')
        #     firebase_admin.delete_app(app_instance)
        #     print("Firebase app 'nacion_sender' eliminada.")
        # except ValueError:
        #     pass # App no existía o ya fue eliminada

if __name__ == '__main__':
    main()
    sys.exit(0)
