import firebase_admin
from firebase_admin import credentials, firestore
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import os
import glob
import pdfplumber
from datetime import datetime
import pytz
import sys

procesos_fallidos = []

# Inicializar Firebase
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define the directory where CSV files are located (ajustado para Windows)
csv_directory = 'pipeline_licitaciones/excels/caba/'

# Function to get the most recent CSV file in the directory
def obtener_csv_mas_reciente(directorio):
    try:
        csv_files = glob.glob(os.path.join(directorio, '*.csv'))
        if not csv_files:
            print(f"No se encontraron archivos CSV en el directorio {directorio}")
            return None
        csv_files.sort(key=os.path.getmtime, reverse=True)
        return csv_files[0]
    except Exception as e:
        print(f"Error al obtener el archivo CSV más reciente: {e}")
        return None
    
# Get the path to the most recent CSV file
csv_path = obtener_csv_mas_reciente(csv_directory)
if csv_path is None:
    print("No se encontró el archivo CSV. Saliendo del script.")
    sys.exit(1)  # Exit if no CSV file is found

try:
    # Load the CSV file and ensure 'numero_proceso' is a string
    data = pd.read_csv(csv_path)
    data.rename(columns={'Número de proceso': 'numero_proceso'}, inplace=True)
    data['numero_proceso'] = data['numero_proceso'].astype(str)
except Exception as e:
    print(f"Error al cargar el archivo CSV: {e}")
    sys.exit(1)

# Check if there are existing processes in Firestore
try:
    docs = db.collection("procesos-bac").stream()
    existing_processes = set()
    for doc in docs:
        doc_data = doc.to_dict()
        if 'numero_proceso' in doc_data:
            existing_processes.add(doc_data['numero_proceso'])
    print(f"Procesos existentes en Firestore: {len(existing_processes)}")
except Exception as e:
    print(f"Error al obtener procesos existentes de Firestore: {e}")
    existing_processes = set()

# Filter out existing processes
new_processes = data[~data['numero_proceso'].isin(existing_processes)]
print(f"Procesos nuevos a procesar: {len(new_processes)}")

if len(new_processes) == 0:
    print("No hay procesos nuevos para procesar.")
    sys.exit(0)

# Function to check if the process already exists in Firestore
def proceso_existe_en_firestore(numero_proceso):
    try:
        query = db.collection("procesos-bac").where("numero_proceso", "==", numero_proceso)
        resultados = query.stream()
        for doc in resultados:
            return True
        return False
    except Exception as e:
        print(f"Error al verificar si el proceso existe en Firestore: {e}")
        return False

# Function to save data to Firestore
def guardar_en_firestore(info_proceso):
    try:
        doc_ref = db.collection("procesos-bac").document()
        doc_ref.set(info_proceso)
        print(f"Datos guardados en Firestore para el proceso {info_proceso['numero_proceso']}")
    except Exception as e:
        print(f"Error al guardar en Firestore: {e}")

def extraer_info_basica(page):
    try:
        info_basica = {}
        campos = {
            "objeto": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblObjeto",
            "organismo": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblOrganismo",
            "reparticion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblReparticion",
            "unidad_operativa": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblUnidadOperativa",
            "categoria": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblCategoria",
            "procedimiento": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblProcedimiento",
            "modalidad": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblModalidad",
            "estado": "#ctl00_CPH1_UCVistaPreviaPliego_UC_DatosBasicos_lblEstado"
        }

        for campo, selector in campos.items():
            elemento = page.query_selector(selector)
            info_basica[campo] = elemento.inner_text() if elemento else ""

        return json.dumps(info_basica, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer la información básica: {e}")
        return None

def extraer_cronograma(page):
    try:
        cronograma = {}
        campos = {
            "fecha_publicacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaPublicacion",
            "fecha_apertura_ofertas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaAperturaOfertas",
            "fecha_vencimiento_consultas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaVencimientoConsultas",
            "fecha_respuesta_consultas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaRespuestaConsultas",
            "fecha_acto_apertura": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaActoApertura",
            "lugar_acto_apertura": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblLugarActoApertura"
        }

        for campo, selector in campos.items():
            elemento = page.query_selector(selector)
            cronograma[campo] = elemento.inner_text() if elemento else ""

        return json.dumps(cronograma, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer el cronograma: {e}")
        return None

def extraer_detalle_productos(page):
    try:
        productos = []
        filas = page.query_selector_all("#ctl00_CPH1_UCVistaPreviaPliego_UC_DetalleProductos_gvDetalleProductos tbody tr")
        
        for fila in filas:
            celdas = fila.query_selector_all("td")
            if len(celdas) >= 4:
                producto = {
                    "codigo": celdas[0].inner_text().strip(),
                    "descripcion": celdas[1].inner_text().strip(),
                    "cantidad": celdas[2].inner_text().strip(),
                    "unidad_medida": celdas[3].inner_text().strip()
                }
                productos.append(producto)

        return json.dumps(productos, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer el detalle de productos: {e}")
        return None

def extraer_monto_duracion(page):
    try:
        monto_duracion = {}
        campos = {
            "monto": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionMonto",
            "moneda": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionMoneda",
            "periodicidad_recepcion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblPeriodicidadRecepcion",
            "fecha_inicio_contrato": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionFechaInicioContrato",
            "duracion_contrato": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionDuracionContrato"
        }

        for campo, selector in campos.items():
            elemento = page.query_selector(selector)
            monto_duracion[campo] = elemento.inner_text() if elemento else ""

        return json.dumps(monto_duracion, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer el monto y la duración del contrato: {e}")
        return None

def extraer_requisitos(page):
    """
    Función para extraer los requisitos mínimos de participación, capturando los encabezados
    y las tablas de requisitos correspondientes, y retornarlos en formato JSON.
    """
    try:
        requisitos_data = []

        # Seleccionar todas las secciones de requisitos dentro del contenedor principal
        secciones_requisitos = page.query_selector_all(".list-group-item")

        # Iterar sobre cada sección para extraer el encabezado y los requisitos
        for seccion in secciones_requisitos:
            encabezado_elemento = seccion.query_selector("h5 span")
            encabezado = encabezado_elemento.inner_text() if encabezado_elemento else "Encabezado desconocido"

            # Inicializar el diccionario de la sección con el encabezado
            requisitos_seccion = {
                "encabezado": encabezado,
                "requisitos": []
            }

            # Extraer cada fila de requisitos dentro de la tabla de la sección actual
            filas_requisitos = seccion.query_selector_all("tbody tr")
            for fila in filas_requisitos:
                num_requisito = fila.query_selector("span[id*='Label']").inner_text() if fila.query_selector("span[id*='Label']") else "N/A"
                descripcion = fila.query_selector("span[id*='Label1']").inner_text() if fila.query_selector("span[id*='Label1']") else "No disponible"
                tipo_documento = fila.query_selector("span[id*='TipoDocumento']").inner_text() if fila.query_selector("span[id*='TipoDocumento']") else "No especificado"

                # Agregar el requisito a la lista de requisitos de la sección actual
                requisitos_seccion["requisitos"].append({
                    "numero": num_requisito,
                    "descripcion": descripcion,
                    "tipo_documento": tipo_documento
                })

            # Agregar la sección al resultado final
            requisitos_data.append(requisitos_seccion)

        # Convertir a JSON y retornar
        return json.dumps(requisitos_data, ensure_ascii=False)

    except Exception as e:
        print(f"Error al extraer los requisitos: {e}")
        return None

def volver_a_lista(page):
    try:
        volver_selector = "#ctl00_CPH1_lnkVolver"
        page.wait_for_selector(volver_selector, timeout=15000)
        page.click(volver_selector)
        page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"Error al hacer clic en el botón 'Volver': {e}")
        try:
            page.reload()
            page.wait_for_load_state("networkidle")
        except Exception as reload_exception:
            print(f"Error al recargar la página: {reload_exception}")

def extraer_info_proceso(page, numero_proceso):
    try:
        numero_proceso = str(numero_proceso)
        
        input_selector = "#ctl00_CPH1_txtNumeroProceso"
        page.wait_for_selector(input_selector, timeout=5000)
        page.fill(input_selector, numero_proceso)

        boton_busqueda_selector = "#ctl00_CPH1_btnListarPliegoNumero"
        page.wait_for_selector(boton_busqueda_selector, timeout=5000)
        page.click(boton_busqueda_selector)
        page.wait_for_load_state("networkidle")

        enlace_proceso_selector = "#ctl00_CPH1_GridListaPliegos_ctl02_lnkNumeroProceso"
        page.wait_for_selector(enlace_proceso_selector, timeout=5000)
        page.click(enlace_proceso_selector)
        page.wait_for_load_state("networkidle")

        # Wait for any loading overlays to disappear
        loading_overlay_selector = "#ctl00_CPH1_updPgsAjaxPanelProgreso"
        page.wait_for_selector(loading_overlay_selector, state='hidden', timeout=15000)

        # Extract data (SIN PLIEGOS - OPTIMIZADO)
        informacion_basica_json = extraer_info_basica(page)
        cronograma_json = extraer_cronograma(page)
        detalle_productos_json = extraer_detalle_productos(page)
        monto_duracion_json = extraer_monto_duracion(page)
        requisitos_json = extraer_requisitos(page)

        # Add timestamp
        timestamp = datetime.now(pytz.UTC).isoformat()

        # Extraer codigo_reparticion
        codigo_reparticion = numero_proceso.split('-')[0] if '-' in numero_proceso else ''

        info_proceso = {
            "numero_proceso": numero_proceso,
            "codigo_reparticion": codigo_reparticion,
            "informacion_basica": informacion_basica_json,
            "cronograma": cronograma_json,
            "detalle_productos": detalle_productos_json,
            "monto_duracion": monto_duracion_json,
            "requisitos": requisitos_json,
            "timestamp": timestamp
            # NOTA: pliego_particular y pliego_tecnico REMOVIDOS para optimización
        }

        print(f"Información guardada para el proceso {numero_proceso} con timestamp {timestamp}")
        return info_proceso

    except Exception as e:
        print(f"Error al extraer información del proceso {numero_proceso}: {e}")
        procesos_fallidos.append(numero_proceso)
        return None

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto("https://www.buenosaires.gob.ar/contrataciones/vista-previa-pliego")
            page.wait_for_load_state("networkidle")

            for index, row in new_processes.iterrows():
                numero_proceso = row['numero_proceso']
                
                if proceso_existe_en_firestore(numero_proceso):
                    print(f"El proceso {numero_proceso} ya existe en Firestore. Saltando...")
                    continue

                print(f"Procesando: {numero_proceso}")
                
                info_proceso = extraer_info_proceso(page, numero_proceso)
                
                if info_proceso:
                    guardar_en_firestore(info_proceso)
                    volver_a_lista(page)
                else:
                    print(f"No se pudo extraer información para el proceso {numero_proceso}")
                    volver_a_lista(page)

        except Exception as e:
            print(f"Error general en el script: {e}")
        finally:
            browser.close()

    if procesos_fallidos:
        print(f"Procesos que fallaron: {procesos_fallidos}")
    else:
        print("Todos los procesos se procesaron exitosamente.")

if __name__ == "__main__":
    main()