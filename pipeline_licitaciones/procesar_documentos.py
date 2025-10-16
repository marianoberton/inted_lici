import firebase_admin
from firebase_admin import credentials, firestore
import json
import time
import os
from google import genai
import pandas as pd
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Inicializar Firebase de manera segura
from firebase_config import get_firestore_client
db = get_firestore_client()

# Configurar la API de Gemini
API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')  
if not API_KEY:
    raise ValueError("La clave de API de Gemini no está configurada. Por favor, configura GOOGLE_GEMINI_API_KEY en las variables de entorno.")

# Crear cliente de Gemini
client = genai.Client(api_key=API_KEY)

# Modelos de Gemini actualizados (2025)
MODELO_PRINCIPAL = "gemini-2.5-flash"
MODELO_RESPALDO = "gemini-2.0-flash"
modelo_actual = MODELO_PRINCIPAL

# Opciones de categorías generales
categoria_general_options = [
    "Tecnología e Infraestructura IT",
    "Servicios Generales",
    "Infraestructura y Construcción",
    "Gastronomía y Eventos",
    "Concesiones y Predios",
    "Educación y Capacitación",
    "Marketing y Comercialización",
    "Salud y Bienestar",
    "Sin Clasificación"
]

def cambiar_a_modelo_respaldo():
    """Cambia al modelo de respaldo si se ha excedido la cuota del modelo principal."""
    global modelo_actual
    if modelo_actual == MODELO_PRINCIPAL:
        print("Excedida la cuota del modelo principal. Cambiando al modelo de respaldo...")
        modelo_actual = MODELO_RESPALDO
    else:
        print("Ya estamos usando el modelo de respaldo, no hay más cambios disponibles.")

def obtener_documentos():
    # Obtener IDs de documentos ya procesados en procesos-bac-dashboard
    dashboard_docs = db.collection('procesos-bac-dashboard').stream()
    documentos_procesados = set()
    for doc in dashboard_docs:
        documentos_procesados.add(doc.id)
    
    print(f"Documentos ya procesados en dashboard: {len(documentos_procesados)}")
    
    # Obtener documentos de procesos-bac
    docs = db.collection('procesos-bac').stream()
    documentos = []
    documentos_omitidos_codigo = 0
    documentos_ya_procesados = 0
    
    for doc in docs:
        data = doc.to_dict()
        
        # Filtro 1: Omitir si ya está procesado
        if doc.id in documentos_procesados:
            documentos_ya_procesados += 1
            continue
            
        # Filtro 2: Omitir códigos de repartición 400-499
        codigo_reparticion = data.get('codigo_reparticion')
        if codigo_reparticion:
            try:
                codigo_reparticion_num = int(codigo_reparticion)
                if 400 <= codigo_reparticion_num <= 499:
                    documentos_omitidos_codigo += 1
                    continue
            except ValueError:
                print(f"Error en el formato de codigo_reparticion para el documento {doc.id}")

        documentos.append((doc.id, data))
    
    print(f"Documentos omitidos por código 400-499: {documentos_omitidos_codigo}")
    print(f"Documentos ya procesados: {documentos_ya_procesados}")
    print(f"Documentos nuevos a procesar: {len(documentos)}")
    
    return documentos

def preparar_prompt(data):
    detalle_productos = data.get('detalle_productos', '')
    informacion_basica = data.get('informacion_basica')

    nombre_proceso = ''
    if informacion_basica:
        try:
            info_basica_json = json.loads(informacion_basica)
            nombre_proceso = info_basica_json.get('nombre_proceso', '')
        except json.JSONDecodeError:
            print(f"Error al decodificar informacion_basica para el documento: {data}")

    contenido_prompt = f"Nombre del Proceso: {nombre_proceso}\nDetalle de Productos: {detalle_productos}"
    return contenido_prompt

def crear_prompt_rubro(contenido_prompt):
    prompt = (
        "Por favor, determina el rubro más adecuado para el siguiente proceso de compra, "
        "basándote en el nombre del proceso y el detalle de productos. "
        "Proporciona solo el nombre del rubro en una sola palabra o frase corta.\n\n"
        f"{contenido_prompt}"
    )
    return prompt

def crear_prompt_clasificacion_completa(contenido_prompt, categoria_options):
    categorias_str = ', '.join(categoria_options)
    return f"""
Analiza el siguiente contenido de una licitación y clasifícalo en dos aspectos:

1. RUBRO: Identifica el rubro específico del proceso (ej: "Servicios de limpieza", "Equipamiento médico", "Software", etc.)
2. CATEGORIA_GENERAL: Selecciona UNA de estas categorías: {categorias_str}

Contenido a analizar:
{contenido_prompt}

Responde ÚNICAMENTE con un JSON válido en este formato exacto:
{{"rubro": "tu_clasificacion_de_rubro", "categoria_general": "categoria_seleccionada"}}

No agregues texto adicional, solo el JSON.
"""

def obtener_clasificacion_gemini(prompt):
    global modelo_actual
    max_retries = 3
    backoff_factor = 2
    wait_time = 0.5  # Reducido de 2 a 0.5 segundos

    for retry in range(max_retries):
        try:
            time.sleep(wait_time)
            response = client.models.generate_content(
                model=modelo_actual,
                contents=prompt
            )
            if hasattr(response, 'text'):
                response_text = response.text.strip()
                
                # Limpiar markdown si está presente
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                
                try:
                    # Intentar parsear como JSON
                    clasificacion = json.loads(response_text)
                    if 'rubro' in clasificacion and 'categoria_general' in clasificacion:
                        return clasificacion
                    else:
                        print(f"JSON incompleto: {response_text}")
                        return None
                except json.JSONDecodeError:
                    print(f"Respuesta no es JSON válido: {response_text}")
                    return None
            else:
                print(f"Respuesta inesperada de la API: {response}")
                return None
        except Exception as e:
            error_message = str(e).lower()
            print(f"Excepción al llamar a Gemini: {e}")
            if 'rate limit' in error_message or 'too many requests' in error_message or '429' in error_message:
                print(f"Rate limit excedido en {modelo_actual}. Esperando {wait_time} segundos antes de reintentar...")
                time.sleep(wait_time)
                wait_time *= backoff_factor
                if retry == max_retries - 1:
                    cambiar_a_modelo_respaldo()
            else:
                return None
        except Exception as e:
            print(f"Excepción inesperada al llamar a Gemini: {e}")
            return None
    return None

def procesar_documentos():
    documentos = obtener_documentos()
    nueva_coleccion = db.collection('procesos-bac-dashboard')

    for doc_id, data in documentos:
        print(f"Procesando documento: {doc_id}")

        contenido_prompt = preparar_prompt(data)

        # Obtener clasificación completa con una sola llamada
        prompt_clasificacion = crear_prompt_clasificacion_completa(contenido_prompt, categoria_general_options)
        clasificacion = obtener_clasificacion_gemini(prompt_clasificacion)
        
        if clasificacion:
            rubro = clasificacion.get('rubro', 'Sin clasificación')
            categoria_general = clasificacion.get('categoria_general', 'Sin Clasificación')
        else:
            # Fallback si falla la clasificación
            rubro = 'Sin clasificación'
            categoria_general = 'Sin Clasificación'
        
        # Validar que categoria_general esté en las opciones válidas
        if categoria_general not in categoria_general_options:
            categoria_general = 'Sin Clasificación'

        informacion_basica = data.get('informacion_basica')
        numero_proceso = ''
        if informacion_basica:
            try:
                info_basica_json = json.loads(informacion_basica)
                numero_proceso = info_basica_json.get('numero_proceso', '')
            except json.JSONDecodeError:
                print(f"Error al decodificar informacion_basica para el documento: {doc_id}")

        monto_duracion = data.get('monto_duracion', '')
        cronograma = data.get('cronograma', '')

        # IMPORTANTE: Mantener exactamente el mismo formato que antes
        formatted_data = {
            'nombre_proceso': data.get('nombre_proceso', ''),
            'detalle_productos': data.get('detalle_productos', ''),
            'rubro': rubro,
            'categoria_general': categoria_general,
            'numero_proceso': numero_proceso,
            'monto_duracion': monto_duracion,
            'cronograma': cronograma,
            'informacion_basica': informacion_basica,
            'codigo_reparticion': data.get('codigo_reparticion', ''),
        }

        nuevo_doc_ref = nueva_coleccion.document(doc_id)
        nuevo_doc_ref.set(formatted_data)
        print(f"Documento {doc_id} procesado y guardado con rubro: {rubro}, categoria_general: {categoria_general}.")

        time.sleep(0.5)  # Reducido de 2 a 0.5 segundos

    print("Procesamiento completado.")

if __name__ == "__main__":
    procesar_documentos()
