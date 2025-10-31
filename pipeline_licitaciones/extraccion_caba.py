import firebase_admin
print("--- extraccion_caba.py: Inicio del script ---")
from firebase_admin import credentials, firestore
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import pandas as pd
import json
import os
import glob
import pdfplumber
from datetime import datetime
import pytz
import sys

procesos_fallidos = []

print("--- extraccion_caba.py: Antes de inicializar Firebase ---")
# Inicializar Firebase de manera segura
from firebase_config import get_firestore_client
db = get_firestore_client()
print("--- extraccion_caba.py: Después de inicializar Firebase ---")

# Define the directory where CSV files are located (compatible Docker/local)
if os.path.exists("/app/pipeline_licitaciones"):
    # Estamos en Docker
    csv_directory = '/app/pipeline_licitaciones/excels/caba/'
else:
    # Estamos en local
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

print("--- extraccion_caba.py: Antes de leer el archivo CSV ---")
try:
    # Load the CSV file and ensure 'numero_proceso' is a string
    data = pd.read_csv(csv_path)
    data.rename(columns={'Número de proceso': 'numero_proceso'}, inplace=True)
    data['numero_proceso'] = data['numero_proceso'].astype(str)
    print("--- extraccion_caba.py: Después de leer el archivo CSV ---")
except Exception as e:
    print(f"Error al cargar el archivo CSV: {e}")
    sys.exit(1)

download_directory = csv_directory  # Use the same directory for downloads


def obtener_numeros_proceso_firestore():
    numeros_proceso_firestore = set()
    try:
        docs = db.collection("procesos-bac").stream()
        for doc in docs:
            data = doc.to_dict()
            numero_proceso = data.get('numero_proceso', None)
            if numero_proceso:
                numeros_proceso_firestore.add(numero_proceso)
        return numeros_proceso_firestore
    except Exception as e:
        print(f"Error al obtener los números de proceso de Firestore: {e}")
        return set()


def proceso_existe_en_firestore(numero_proceso):
    try:
        query = db.collection("procesos-bac").where("numero_proceso", "==", numero_proceso)
        resultados = query.stream()
        resultados_list = list(resultados)
        print(f"Buscando proceso {numero_proceso}: Encontrados {len(resultados_list)} documentos.")
        return len(resultados_list) > 0
    except Exception as e:
        print(f"Error al verificar si el proceso existe en Firestore: {e}")
        return False

def guardar_en_firestore(info_proceso):
    try:
        doc_ref = db.collection("procesos-bac").document()
        doc_ref.set(info_proceso)
        print(f"Datos guardados en Firestore para el proceso {info_proceso['numero_proceso']}")
    except Exception as e:
        print(f"Error al guardar en Firestore para el proceso {info_proceso['numero_proceso']}: {e}")



# Función para extraer la información básica y guardarla como JSON
def extraer_info_basica(page):
    """
    Función para extraer la información básica del proceso y retornarla en formato JSON.
    """
    try:
        page.wait_for_selector("#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblNumeroProceso", timeout=10000)

        informacion_basica = {}
        campos = {
            "numero_proceso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblNumeroProceso",
            "nombre_proceso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblNombreProceso",
            "objeto_contratacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblObjetoContratacion",
            "procedimiento_seleccion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblProcedimientoSeleccion",
            "etapa": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblEtapa",
            "modalidad": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblModalidad",
            "alcance": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblAlcance",
            "moneda": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_rptMonedasPliego_ctl00_lblMonedaPliego",
            "tipo_cotizacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoCotizacionCantidad",
            "tipo_adjudicacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoAdjudicacionCantidad",
            "cantidad_ofertas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblCantidadOferta",
            "lugar_recepcion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblLugarRecepcionFisica",
            "plazo_mantenimiento": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblPlazoMantenimientoOferta",
            "telefono_contacto": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTelefonoContactoUOA",
            "encuadre_legal": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblEncuadreLegal",
            "acepta_redeterminacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblAceptaRedeterminacion",
            "requiere_pago": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblRequierePago",
            "inciso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblInciso",
            "acepta_prorroga": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblAceptaProrroga",
            "valor_unidad_compra": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblUnidadCompra"
        }

        for campo, selector in campos.items():
            try:
                page.wait_for_selector(selector, timeout=5000)
                elemento = page.query_selector(selector)
                informacion_basica[campo] = elemento.inner_text() if elemento else ""
            except Exception as e:
                informacion_basica[campo] = ""
                print(f"Error al extraer el campo {campo}: {e}")

        return json.dumps(informacion_basica, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer la información básica: {e}")
        return None

def extraer_cronograma(page):
    """
    Función para extraer la información del cronograma y retornarla en formato JSON.
    """
    try:
        # Lista de campos y sus selectores
        cronograma = {}
        campos = {
            "fecha_publicacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaPublicacion",
            "fecha_inicio_consultas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaInicioConsultas",
            "fecha_final_consultas": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaFinalConsultas",
            "fecha_inicio_recepcion_documentos": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaInicioRecepcionDocumentos",
            "fecha_fin_recepcion_documentos": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaFinRecepcionDocumentos",
            "fecha_acto_apertura": "#ctl00_CPH1_UCVistaPreviaPliego_UC_Cronograma_lblFechaActoApertura"
        }

        for campo, selector in campos.items():
            elemento = page.query_selector(selector)
            cronograma[campo] = elemento.inner_text() if elemento else ""

        return json.dumps(cronograma, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer el cronograma: {e}")
        return None

def extraer_detalle_productos(page):
    """
    Función para extraer el detalle de productos o servicios y retornarlo en formato JSON.
    """
    try:
        # Seleccionar todas las filas de la tabla de productos/servicios
        filas = page.query_selector_all("#ctl00_CPH1_UCVistaPreviaPliego_UC_DetalleProductos_gvLineaPliego tbody tr")

        productos = []
        for fila in filas:
            numero_renglon = fila.query_selector("td:nth-child(1)").inner_text()
            objeto_gasto = fila.query_selector("td:nth-child(2)").inner_text()
            codigo_item = fila.query_selector("td:nth-child(3)").inner_text()
            descripcion = fila.query_selector("td:nth-child(4)").inner_text()
            cantidad = fila.query_selector("td:nth-child(5)").inner_text()

            # Añadir el producto/servicio al listado
            productos.append({
                "numero_renglon": numero_renglon,
                "objeto_gasto": objeto_gasto,
                "codigo_item": codigo_item,
                "descripcion": descripcion,
                "cantidad": cantidad
            })

        return json.dumps(productos, ensure_ascii=False)
    except Exception as e:
        print(f"Error al extraer el detalle de productos o servicios: {e}")
        return None

def extraer_monto_duracion(page):
    """
    Función para extraer el monto y la duración del contrato y retornarlo en formato JSON.
    """
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

def descargar_y_leer_pdf(page, numero_proceso):
    try:
        pdf_particular_selector = "#ctl00_CPH1_UCVistaPreviaPliego_UC_ActosAdministrativos_Clausulas_gvActosAdministrativos_ctl02_btnVer"
        page.wait_for_selector(pdf_particular_selector, timeout=10000)
        elemento_pdf = page.query_selector(pdf_particular_selector)
        if not elemento_pdf:
            print(f"No se encontró el PDF para el proceso {numero_proceso}.")
            return None

        with page.expect_download() as download_info:
            elemento_pdf.click()
        download = download_info.value

        pdf_path = os.path.join(download_directory, f"{numero_proceso}_pliego_particular.pdf")
        download.save_as(pdf_path)

        with pdfplumber.open(pdf_path) as pdf:
            texto_pdf = ""
            for page_pdf in pdf.pages:
                texto_pdf += page_pdf.extract_text()

        os.remove(pdf_path)

        return texto_pdf.strip()
    except Exception as e:
        print(f"Error al descargar o leer el PDF para el proceso {numero_proceso}: {e}")
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


def descargar_y_leer_pliego_tecnico(page, numero_proceso):
    try:
        pdf_tecnico_selector = "#ctl00_CPH1_UCVistaPreviaPliego_UC_ActosAdministrativos_PoseePliegoTecnico_gvActosAdministrativos_ctl02_btnVer"
        page.wait_for_selector(pdf_tecnico_selector, timeout=10000)
        elemento_pdf = page.query_selector(pdf_tecnico_selector)
        if not elemento_pdf:
            print(f"No se encontró el pliego técnico para el proceso {numero_proceso}.")
            return None

        with page.expect_download() as download_info:
            elemento_pdf.click()
        download = download_info.value

        pdf_path = os.path.join(download_directory, f"{numero_proceso}_pliego_tecnico.pdf")
        download.save_as(pdf_path)

        with pdfplumber.open(pdf_path) as pdf:
            texto_pdf = ""
            for page_pdf in pdf.pages:
                texto_pdf += page_pdf.extract_text()

        os.remove(pdf_path)

        return texto_pdf.strip()
    except Exception as e:
        print(f"Error al descargar o leer el pliego técnico para el proceso {numero_proceso}: {e}")
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

# Ensure all extraction functions use 'numero_proceso' where needed
# (Include your existing extraction functions here)

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

        # Extract data
        informacion_basica_json = extraer_info_basica(page)
        cronograma_json = extraer_cronograma(page)
        detalle_productos_json = extraer_detalle_productos(page)
        monto_duracion_json = extraer_monto_duracion(page)
        # pliego_particular = descargar_y_leer_pdf(page, numero_proceso)  # Comentado para mejorar performance
        # pliego_tecnico = descargar_y_leer_pliego_tecnico(page, numero_proceso)  # Comentado para mejorar performance
        pliego_particular = ""  # Valor vacío en lugar de descargar
        pliego_tecnico = ""     # Valor vacío en lugar de descargar
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
            "pliego_particular": pliego_particular,
            "pliego_tecnico": pliego_tecnico,
            "requisitos": requisitos_json,
            "timestamp": timestamp
        }
        # Save to Firestore
        guardar_en_firestore(info_proceso)

        print(f"Información guardada para el proceso {numero_proceso} con timestamp {timestamp}")

        volver_a_lista(page)

    except Exception as e:
        print(f"Error al procesar {numero_proceso}: {e}")
        procesos_fallidos.append(numero_proceso)
        try:
            volver_a_lista(page)
        except Exception as ex:
            print(f"Error al intentar volver a la lista: {ex}")

print("--- extraccion_caba.py: Antes de la función main() ---")
def main():
    try:
        print("--- extraccion_caba.py: Dentro de main(), antes de inicializar Playwright ---")
        # Inicializar Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(
                accept_downloads=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            stealth_sync(page)
            print("--- extraccion_caba.py: Playwright inicializado correctamente ---")

            print("--- extraccion_caba.py: Antes de page.goto() ---")
            page.goto("https://www.buenosairescompras.gob.ar/", timeout=120000)
            print("--- extraccion_caba.py: Después de page.goto() ---")

            try:
                boton_selector = "xpath=//*[@id='aspnetForm']/section/div/div[2]/div/div/a[2]"
                page.wait_for_selector(boton_selector, timeout=5000)
                page.click(boton_selector)
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"Error al hacer clic en el botón de acceso al buscador de procesos: {e}")

            for numero_proceso in data['numero_proceso']:
                if proceso_existe_en_firestore(numero_proceso):
                    print(f"El proceso {numero_proceso} ya existe en Firestore. Saltando.")
                    continue
                else:
                    extraer_info_proceso(page, numero_proceso)

            if procesos_fallidos:
                print("\nReintentando procesos fallidos...\n")
                for numero_proceso in procesos_fallidos.copy():
                    print(f"Reintentando el proceso {numero_proceso}")
                    try:
                        if proceso_existe_en_firestore(numero_proceso):
                            print(f"El proceso {numero_proceso} ya existe en Firestore. Saltando.")
                            procesos_fallidos.remove(numero_proceso)
                            continue
                        else:
                            extraer_info_proceso(page, numero_proceso)
                            procesos_fallidos.remove(numero_proceso)
                    except Exception as e:
                        print(f"Error al reintentar el proceso {numero_proceso}: {e}")

            # Verificación final
            numeros_proceso_csv = set(data['numero_proceso'])
            numeros_proceso_firestore = obtener_numeros_proceso_firestore()

            procesos_faltantes = numeros_proceso_csv - numeros_proceso_firestore

            if procesos_faltantes:
                print("\nProcesos que no se han guardado en Firestore:")
                for numero_proceso in procesos_faltantes:
                    print(numero_proceso)
            else:
                print("\nTodos los procesos se han guardado correctamente en Firestore.")

            if procesos_faltantes:
                print("\nReintentando procesos faltantes...\n")
                for numero_proceso in procesos_faltantes.copy():
                    print(f"Reintentando el proceso {numero_proceso}")
                    try:
                        if proceso_existe_en_firestore(numero_proceso):
                            print(f"El proceso {numero_proceso} ya existe en Firestore. Saltando.")
                            procesos_faltantes.remove(numero_proceso)
                            continue
                        else:
                            extraer_info_proceso(page, numero_proceso)
                            procesos_faltantes.remove(numero_proceso)
                    except Exception as e:
                        print(f"Error al reintentar el proceso {numero_proceso}: {e}")

            # Cerrar el navegador y el contexto si aún están abiertos
            try:
                if 'context' in locals() and context:
                    context.close()
                if 'browser' in locals() and browser:
                    browser.close()
            except Exception as e:
                print(f"Error al cerrar Playwright: {e}")

    except Exception as e:
        print(f"Error en el script principal: {e}")
        sys.exit(1)
        
        

if __name__ == '__main__':
    main()
    sys.exit(0)