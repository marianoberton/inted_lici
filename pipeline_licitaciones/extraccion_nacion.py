import firebase_admin
from firebase_admin import credentials, firestore
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import json
import os
import glob
import pdfplumber
from datetime import datetime
import pytz
import sys
import time

procesos_fallidos = []
ERROR_PLACEHOLDER = "Error al extraer texto"
# The following lists are not strictly necessary if _extraer_campo_con_espera generalises its debug output
# CABECERA_FIELDS_TO_DEBUG = [] 
# CRITICAL_INFO_BASICA_FIELDS = [] 
# CRITICAL_CRONOGRAMA_FIELDS = [] 

# Initialize Firebase Admin SDK
try:
    # Asumimos que el JSON de credenciales está en la raíz del proyecto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cred_path = os.path.join(script_dir, 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("SDK de Firebase inicializado correctamente.")
except Exception as e_firebase_init:
    print(f"Error al inicializar Firebase Admin SDK: {e_firebase_init}")
    print("Asegúrate de que el archivo 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json' esté en la raíz del proyecto y sea válido.")
    db = None # Para que el script no falle si Firestore no se puede usar
    # sys.exit(1) # Podrías descomentar esto si Firestore es absolutamente esencial para continuar

# Define the directory where CSV files are located
csv_directory = 'pipeline_licitaciones/excels/nacion/' # Ajustado para Windows
#csv_directory = 'C:\\projects\\licitaciones\\pipeline_licitaciones\\excels\\nacion\\' # RUTA LOCAL PARA PRUEBAS


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
    # Asegurarse que la columna se llame 'numero_proceso', si en el CSV de Nación tiene otro nombre, ajustar aquí.
    # Si ya se llama 'Número de proceso' como en CABA, este rename es correcto.
    data.rename(columns={'Número de proceso': 'numero_proceso'}, inplace=True)
    data['numero_proceso'] = data['numero_proceso'].astype(str)
except Exception as e:
    print(f"Error al cargar el archivo CSV: {e}")
    print(f"Verifique que el archivo {csv_path} exista y que la columna 'Número de proceso' (o su equivalente) esté presente.")
    sys.exit(1)

# download_directory = csv_directory  # Use the same directory for downloads - Ajustar si es necesario para PDFs de Nación
download_directory = os.path.join(os.path.dirname(csv_directory), "pdfs_temp") # Directorio temporal para PDFs de Nación
os.makedirs(download_directory, exist_ok=True)


# --- FUNCIONES DE FIRESTORE (Ahora descomentadas y ajustadas) ---
def obtener_numeros_proceso_firestore():
    if not db:
        print("Firestore no está inicializado. No se pueden obtener IDs existentes.")
        return set()

    numeros_proceso_firestore = set()
    try:
        print("Obteniendo números de proceso existentes de Firestore (colección 'procesos-nacion')...")
        # Usar "procesos-nacion". Ajustar si el nombre de la colección es diferente.
        docs = db.collection("procesos-nacion").stream()
        for doc in docs:
            data_doc = doc.to_dict()
            numero_proceso_fb = data_doc.get('numero_proceso', None)
            if numero_proceso_fb: # Si existe y no es None
                cleaned_numero_proceso_fb = str(numero_proceso_fb).strip()
                if cleaned_numero_proceso_fb: # Si no es una cadena vacía después de strip
                    numeros_proceso_firestore.add(cleaned_numero_proceso_fb)
        print(f"Se encontraron {len(numeros_proceso_firestore)} procesos válidos y limpios existentes en Firestore.") # Mensaje actualizado
        return numeros_proceso_firestore
    except Exception as e:
        print(f"Error al obtener los números de proceso de Firestore: {e}")
        return set()

# La función proceso_existe_en_firestore() no es estrictamente necesaria si ya tenemos el set
# def proceso_existe_en_firestore(numero_proceso, set_existentes):
#     return str(numero_proceso) in set_existentes

def guardar_en_firestore(info_proceso):
    if not db:
        print("Firestore no está inicializado. No se puede guardar el documento.")
        return

    try:
        # Usar "procesos-nacion" como nombre de la colección.
        # El ID del documento será automático.
        doc_ref = db.collection("procesos-nacion").document()
        doc_ref.set(info_proceso)
        print(f"Datos guardados en Firestore (colección 'procesos-nacion') para el proceso {info_proceso.get('numero_proceso', 'DESCONOCIDO')}")
    except Exception as e:
        print(f"Error al guardar en Firestore para el proceso {info_proceso.get('numero_proceso', 'DESCONOCIDO')}: {e}")
# --- FIN FUNCIONES DE FIRESTORE ---


# --- FUNCIONES DE EXTRACCIÓN DE DATOS (ADAPTADAS PARA NACIÓN) ---

def _extraer_campo_con_espera(page, campo_nombre, selector, seccion_nombre, timeout_espera=7000):
    """Función helper para extraer un campo esperando su visibilidad."""
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout_espera)
        elemento = page.query_selector(selector) 
        if elemento:
            valor_extraido = elemento.text_content().strip()
            # Simplified debug logging - print for all fields or specific important ones
            # For example, always print if it's a known key field, or reduce verbosity generally
            # print(f"  INFO ({seccion_nombre} - {campo_nombre}): Selector '{selector}' encontrado. Texto: '{valor_extraido[:100]}...'")
            
            if valor_extraido == "":
                 # General warning for any empty field, can be made more specific if needed
                 print(f"  ADVERTENCIA ({seccion_nombre}): Campo '{campo_nombre}' (selector '{selector}') encontrado visible pero texto extraido es VACIO.")
            return valor_extraido
        else:
            # This case (selector visible by wait_for_selector but None by query_selector) is unusual but kept for safety.
            print(f"  ADVERTENCIA GRAVE ({seccion_nombre}): Selector '{selector}' para '{campo_nombre}' reportado visible, pero query_selector devolvio None.")
            return "Error: Selector visible pero elemento None"
    except PlaywrightTimeoutError:
        print(f"  ERROR ({seccion_nombre}): Timeout ({timeout_espera/1000}s) esperando selector VISIBLE para '{campo_nombre}': {selector}")
        # Optionally, check if element exists but is not visible for more detailed diagnosis
        # el_existe = page.query_selector(selector)
        # print(f"    DEBUG ({seccion_nombre} - {campo_nombre}): En Timeout. Selector '{selector}' existe? {'Sí' if el_existe else 'No'}. Visible ahora? {el_existe.is_visible() if el_existe else 'N/A'}")
        return f"Error: Timeout selector ({selector})"
    except Exception as e:
        print(f"  ERROR ({seccion_nombre}): Excepcion al extraer '{campo_nombre}' (selector '{selector}'): {e}")
        return ERROR_PLACEHOLDER

def extraer_info_basica(page):
    """
    Extrae la información básica del proceso de Compr.AR.
    """
    print("Extrayendo Información Básica...")
    informacion_basica = {}

    # Esperar que el campo de número de proceso en la cabecera tenga texto
    selector_num_proceso_cab = "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblNumPliego"
    try:
        # print(f"  DEBUG (info_basica): Esperando que '{selector_num_proceso_cab}' tenga texto no vacío...") # Less verbose
        page.wait_for_function(
            f"selector => document.querySelector(selector) && document.querySelector(selector).textContent.trim() !== ''",
            selector_num_proceso_cab,
            timeout=10000 
        )
        # print(f"  DEBUG (info_basica): '{selector_num_proceso_cab}' ahora tiene texto o se alcanzó el timeout.") # Less verbose
    except PlaywrightTimeoutError:
        print(f"  INFO (info_basica): Timeout/Condición no cumplida esperando texto en '{selector_num_proceso_cab}'. Puede estar vacío.")
    except Exception as e_wait_text:
        print(f"  ERROR (info_basica): Excepcion en wait_for_function para '{selector_num_proceso_cab}': {e_wait_text}")

    # Esperar el panel principal de Información Básica
    panel_info_basica_selector = 'div.panel-default:has(div.panel-heading h4:has-text("Información básica del proceso")) div.panel-body'
    try:
        # print(f"  DEBUG (info_basica): Esperando el panel principal: {panel_info_basica_selector}") # Less verbose
        page.wait_for_selector(panel_info_basica_selector, state="visible", timeout=10000)
        print("  INFO (info_basica): Panel principal de Informacion Basica encontrado.")
    except PlaywrightTimeoutError:
        print(f"  ERROR (info_basica): Timeout esperando el panel principal '{panel_info_basica_selector}'. Campos podrían faltar.")
        informacion_basica["error_panel_info_basica"] = f"Timeout esperando panel principal info basica: {panel_info_basica_selector}"
    
    # Mapeo de nombres de campo a selectores ID para Nación
    campos = {
        # Campos de la primera sección (panel-body bg-info)
        "numero_proceso_cabecera": "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblNumPliego",
        "numero_expediente": "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblNumExpediente",
        "nombre_proceso_cabecera": "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblNomPliego",
        "unidad_operativa": "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblUnidadOperativa",
        
        # Campos de la sección "Información básica del proceso" (panel-body)
        "numero_proceso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblNumeroProceso",
        "nombre_proceso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblNombreProceso",
        "objeto_contratacion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblObjetoContratacion",
        "procedimiento_seleccion": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblProcedimientoSeleccion",
        "etapa": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblEtapa",
        "modalidad": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblModalidad",
        "alcance": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblAlcance",
        "moneda": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblMoneda",
        "encuadre_legal": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblEncuadreLegal",
        "tipo_cotizacion_cantidad": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoCotizacionCantidad",
        "tipo_cotizacion_linea": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoCotizacionLinea",
        "tipo_adjudicacion_cantidad": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoAdjudicacionCantidad",
        "tipo_adjudicacion_linea": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoAdjudicacionLinea",
        "tipo_documento_genera_proceso": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblTipoProcesoGen",
        "lugar_recepcion_fisica": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblLugarRecepcionFisica",
        "plazo_mantenimiento_oferta": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblPlazoMantenimientoOferta",
        "requiere_pago": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblRequierePago",
        "genera_recursos": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_GeneraRecursos",
        "financiamiento_externo": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_FinanciamientoExterno",
        "acepta_prorroga": "#ctl00_CPH1_UCVistaPreviaPliego_UC_InformacionBasica_lblAceptaProrroga"
    }

    for campo, selector in campos.items():
        informacion_basica[campo] = _extraer_campo_con_espera(page, campo, selector, "info_basica")

    return informacion_basica

def extraer_cronograma(page):
    """
    Extrae la información del cronograma de Compr.AR.
    """
    print("Extrayendo Cronograma...")
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
        cronograma[campo] = _extraer_campo_con_espera(page, campo, selector, "cronograma")
        
    return cronograma

def extraer_detalle_productos(page):
    """
    Extrae el detalle de productos o servicios de Compr.AR.
    """
    print("Extrayendo Detalle de Productos...")
    productos = []
    tabla_selector_principal = "#ctl00_CPH1_UCVistaPreviaPliego_UC_DetalleProductos_gvLineaPliego"
    tabla_selector_alt = "table[id*='gvLineaPliego']" # Alternative selector

    try:
        # Wait for the table to be visible
        try:
            page.wait_for_selector(f"{tabla_selector_principal}, {tabla_selector_alt}", state="visible", timeout=10000)
            # print(f"  DEBUG (productos): Tabla de productos encontrada.") # Less verbose
        except PlaywrightTimeoutError:
            print("  ADVERTENCIA (productos): Tabla de productos no encontrada/visible.")
            return [{"error": "Tabla de productos no visible/encontrada"}] # Return error if table not found

        # Query for rows using the principal selector first
        filas = page.query_selector_all(f"{tabla_selector_principal} tbody tr")
        if not filas:
             # If no rows with principal, try alternative selector
             filas = page.query_selector_all(f"{tabla_selector_alt} tbody tr")
             if filas:
                 print(f"  DEBUG (productos): Filas encontradas con selector alternativo '{tabla_selector_alt}'.")

        if not filas:
            print("  INFO (productos): No se encontraron filas en la tabla de productos.")
            return [] # Return empty list if no rows
        
        print(f"Encontradas {len(filas)} filas en la tabla de productos.")

        for i, fila in enumerate(filas):
            try:
                # Wait for the first cell to be visible to ensure row is ready
                fila.wait_for_selector("td:nth-child(1)", state="visible", timeout=2000)
                
                num_renglon_elem = fila.query_selector("td:nth-child(1)")
                obj_gasto_elem = fila.query_selector("td:nth-child(2)")
                cod_item_elem = fila.query_selector("td:nth-child(3)")
                desc_elem_span = fila.query_selector("td:nth-child(4) span[id*='lblDescripcion']")
                desc_fallback_elem = fila.query_selector("td:nth-child(4)")
                cant_elem_span = fila.query_selector("td:nth-child(5) span[id*='lblCantidad']")
                cant_fallback_elem = fila.query_selector("td:nth-child(5)")

                num_renglon = num_renglon_elem.text_content().strip() if num_renglon_elem else ERROR_PLACEHOLDER
                obj_gasto = obj_gasto_elem.text_content().strip() if obj_gasto_elem else ERROR_PLACEHOLDER
                cod_item = cod_item_elem.text_content().strip() if cod_item_elem else ERROR_PLACEHOLDER
                
                desc = ERROR_PLACEHOLDER
                if desc_elem_span and desc_elem_span.is_visible():
                    desc = desc_elem_span.text_content().strip()
                elif desc_fallback_elem:
                    desc = desc_fallback_elem.text_content().strip()
                
                cant = ERROR_PLACEHOLDER
                if cant_elem_span and cant_elem_span.is_visible():
                    cant = cant_elem_span.text_content().strip()
                elif cant_fallback_elem:
                    cant = cant_fallback_elem.text_content().strip()
                
                productos.append({
                    "numero_renglon": num_renglon,
                    "objeto_gasto": obj_gasto,
                    "codigo_item": cod_item,
                    "descripcion": desc,
                    "cantidad": cant
                })
            except PlaywrightTimeoutError:
                 print(f"  ERROR (productos): Timeout esperando celda en fila {i+1}.")
                 productos.append({"error": f"Error timeout celda fila {i+1}", "numero_renglon_parcial": i+1})
            except Exception as e_fila:
                 print(f"Error procesando fila {i+1} de productos: {e_fila}")
                 productos.append({"error": f"Error procesando fila {i+1}: {str(e_fila)}", "numero_renglon_parcial": i+1})

    except Exception as e:
        print(f"Error general al extraer el detalle de productos: {e}")
        return [{ "error": f"Error general tabla productos: {str(e)}" }]
    
    return productos

def extraer_info_contrato(page):
    """
    Extrae la información del contrato (fecha inicio, duración) de Compr.AR.
    """
    print("Extrayendo Información del Contrato...")
    info_contrato = {}
    campos = {
        "fecha_inicio_contrato": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionFechaInicioContrato",
        "duracion_contrato": "#ctl00_CPH1_UCVistaPreviaPliego_UC_MontoDuracion_lblMontoDuracionDuracionContrato"
    }

    for campo, selector in campos.items():
        info_contrato[campo] = _extraer_campo_con_espera(page, campo, selector, "info_contrato")

    return info_contrato

def descargar_y_leer_pliego_particular(page, numero_proceso):
    """Descarga y lee el PDF de Cláusulas Particulares de Compr.AR."""
    print("Intentando descargar y leer Pliego Particular...")
    pdf_texto = None
    pdf_selector = "#ctl00_CPH1_UCVistaPreviaPliego_UC_Clausulas_gvActosAdministrativos_ctl02_btnVer"
    pdf_descargado_path = None # Para asegurarnos de borrarlo

    try:
        elemento_pdf = page.query_selector(pdf_selector)
        if not elemento_pdf:
            print(f"No se encontró el botón de descarga del pliego particular ({pdf_selector}).")
            return None

        with page.expect_download(timeout=60000) as download_info:
            print(f"Click en botón descarga pliego particular ({pdf_selector})...")
            elemento_pdf.click()
        
        download = download_info.value
        # Usar nombre sugerido o uno genérico
        filename = download.suggested_filename or f"{numero_proceso}_pliego_particular.pdf"
        pdf_descargado_path = os.path.join(download_directory, filename)
        print(f"Descargando pliego particular como: {pdf_descargado_path}")
        download.save_as(pdf_descargado_path)
        print("Pliego particular descargado.")

        print("Extrayendo texto del PDF...")
        with pdfplumber.open(pdf_descargado_path) as pdf:
            texto_completo = []
            for i, page_pdf in enumerate(pdf.pages):
                texto = page_pdf.extract_text()
                if texto:
                    texto_completo.append(texto)
            pdf_texto = "\n".join(texto_completo).strip()
        print("Texto del PDF extraído.")

    except Exception as e:
        print(f"Error al descargar o leer el pliego particular para {numero_proceso}: {e}")
        pdf_texto = f"Error al procesar PDF: {e}" # Devolver el error en lugar de None
    finally:
        # Asegurarse de eliminar el archivo PDF descargado si existe
        if pdf_descargado_path and os.path.exists(pdf_descargado_path):
            try:
                os.remove(pdf_descargado_path)
                print(f"Archivo PDF temporal eliminado: {pdf_descargado_path}")
            except Exception as e_remove:
                print(f"Error al eliminar el archivo PDF temporal {pdf_descargado_path}: {e_remove}")
        
    return pdf_texto

def extraer_requisitos(page):
    """
    Extrae los requisitos técnicos y administrativos de Compr.AR.
    """
    print("Extrayendo Requisitos...")
    requisitos_data = {
        "economicos_financieros": [],
        "tecnicos": [],
        "administrativos": []
    }
    
    try:
        # Wait for the main container of requirements to be visible
        page.wait_for_selector("div.list-group", state="visible", timeout=10000)
        secciones = page.query_selector_all("div.list-group-item")
        
        if not secciones:
            print("  INFO (requisitos): No se encontraron secciones de requisitos (list-group-item).")
            return requisitos_data # Return empty if no sections found

        for seccion_idx, seccion in enumerate(secciones):
            titulo_elem = seccion.query_selector("h5 span")
            if not titulo_elem or not titulo_elem.is_visible(): # Check visibility
                print(f"  ADVERTENCIA (requisitos): Titulo no encontrado o no visible para seccion {seccion_idx}.")
                continue 
            
            titulo_seccion = titulo_elem.text_content().strip().lower()
            lista_target = None

            if "económicos y financieros" in titulo_seccion:
                lista_target = requisitos_data["economicos_financieros"]
                no_hay_eco_elem_selector = "span#ctl00_CPH1_UCVistaPreviaPliego_UC_Requistos_noHayRequisitoEco"
                no_hay_eco_elem = seccion.query_selector(no_hay_eco_elem_selector)
                if no_hay_eco_elem and no_hay_eco_elem.is_visible():
                     lista_target.append({"info": no_hay_eco_elem.text_content().strip()})
                     continue 
            elif "requisitos técnicos" in titulo_seccion:
                lista_target = requisitos_data["tecnicos"]
            elif "requisitos administrativos" in titulo_seccion:
                lista_target = requisitos_data["administrativos"]
            else:
                continue 

            tabla_en_seccion = seccion.query_selector("table")
            if not tabla_en_seccion or not tabla_en_seccion.is_visible(): # Check visibility
                print(f"  INFO (requisitos): No se encontro tabla visible en seccion '{titulo_seccion}'.")
                continue

            filas_requisitos = tabla_en_seccion.query_selector_all("tbody tr") # Query from table, not section directly
            if not filas_requisitos:
                 print(f"  INFO (requisitos): No se encontraron filas en tabla de seccion '{titulo_seccion}'.")
                 continue

            for fila_idx, fila in enumerate(filas_requisitos):
                try:
                    # Wait for the first cell to be visible to ensure row is ready
                    fila.wait_for_selector("td:nth-child(1)", state="visible", timeout=1000)

                    num_req_elem = fila.query_selector("td:nth-child(1)")
                    desc_elem_span = fila.query_selector("td:nth-child(2) span[id*='Label1']") 
                    desc_fallback_elem = fila.query_selector("td:nth-child(2)")
                    tipo_doc_elem_span = fila.query_selector("td:nth-child(3) span[id*='TipoDocumento']")
                    tipo_doc_fallback_elem = fila.query_selector("td:nth-child(3)")

                    num_req = num_req_elem.text_content().strip() if num_req_elem else ERROR_PLACEHOLDER
                    
                    desc = ERROR_PLACEHOLDER
                    if desc_elem_span and desc_elem_span.is_visible():
                        desc = desc_elem_span.text_content().strip()
                    elif desc_fallback_elem:
                        desc = desc_fallback_elem.text_content().strip()
                    
                    tipo_doc = ERROR_PLACEHOLDER
                    if tipo_doc_elem_span and tipo_doc_elem_span.is_visible():
                        tipo_doc = tipo_doc_elem_span.text_content().strip()
                    elif tipo_doc_fallback_elem:
                        tipo_doc = tipo_doc_fallback_elem.text_content().strip()
                    
                    lista_target.append({
                        "numero": num_req,
                        "descripcion": desc,
                        "tipo_documento": tipo_doc
                    })
                except PlaywrightTimeoutError:
                    print(f"  ERROR (requisitos): Timeout celda en seccion '{titulo_seccion}', fila {fila_idx+1}.")
                    lista_target.append({"error": f"Timeout celda requisito en '{titulo_seccion}'", "fila_parcial": fila_idx+1})
                except Exception as e_fila_req:
                    print(f"Error procesando fila de requisito en sección '{titulo_seccion}': {e_fila_req}")
                    lista_target.append({"error": f"Error fila requisito en '{titulo_seccion}': {str(e_fila_req)}", "fila_parcial": fila_idx+1})

    except PlaywrightTimeoutError:
        print("  ERROR (requisitos): Timeout esperando contenedor principal de requisitos (div.list-group).")
        requisitos_data["error_general"] = "Timeout contenedor requisitos"
    except Exception as e:
        print(f"Error general al extraer los requisitos: {e}")
        requisitos_data["error_general"] = f"Error general al extraer requisitos: {str(e)}"

    return requisitos_data

# --- FIN FUNCIONES DE EXTRACCIÓN DE DATOS ---


# REPLACED FUNCTION volver_a_pagina_busqueda
def volver_a_pagina_busqueda(page):
    """
    Intenta navegar a la pagina de busqueda de procesos de Compr.AR.
    Retorna True si tiene exito, False en caso contrario.
    (Adaptado de reextracción_debug_nacion.py)
    """
    max_retries = 2
    input_selector_busqueda = "input#ctl00_CPH1_txtNumeroProceso" 

    for attempt in range(max_retries):
        try:
            print(f"Volviendo a la pagina de busqueda 'BuscarAvanzado.aspx' (Intento {attempt + 1}/{max_retries})...") # MODIFICADO AQUÍ
           
            if page.is_visible(input_selector_busqueda) and "BuscarAvanzado.aspx" in page.url: # MODIFICADO AQUÍ
                print("  Ya estamos en la pagina de busqueda 'BuscarAvanzado.aspx'.") # MODIFICADO AQUÍ
                return True

            print("  Navegando a la pagina principal (Default.aspx) para asegurar un estado limpio...")
            page.goto("https://comprar.gob.ar/Default.aspx", timeout=60000, wait_until="domcontentloaded")
           
            search_button_selector = "a#ctl00_CPH1_CtrlBusquedasHome_btnBusquedaProcesos"
            print(f"  Esperando el boton de busqueda en Default.aspx: {search_button_selector}")
            page.wait_for_selector(search_button_selector, timeout=45000, state="visible")
            print("  Haciendo clic en el boton de busqueda de procesos.")
            page.click(search_button_selector)
           
            print(f"  Esperando a que cargue la pagina de busqueda 'BuscarAvanzado.aspx' (elemento: {input_selector_busqueda})...") # MODIFICADO AQUÍ
            page.wait_for_selector(input_selector_busqueda, timeout=60000, state="visible")

            if "BuscarAvanzado.aspx" in page.url or page.is_visible(input_selector_busqueda): # MODIFICADO AQUÍ
                print("Exito: En pagina de busqueda de procesos 'BuscarAvanzado.aspx'.") # MODIFICADO AQUÍ
                return True
            else:
                # This case should ideally not be hit if wait_for_selector for input_selector_busqueda passed
                print(f"  ADVERTENCIA: Elemento de busqueda '{input_selector_busqueda}' visible, pero URL no es BuscarAvanzado.aspx: {page.url}. Considerado exito parcial.")
                return True # Still, if the input is there, we might be okay.
        except Exception as e:
            print(f"  ERROR (Intento {attempt + 1}/{max_retries}) al volver a la pagina de busqueda: {e}")
            current_url_on_error = page.url
            print(f"    URL actual en el momento del error: {current_url_on_error}")
            if attempt < max_retries - 1:
                print("    Reintentando en 3 segundos...")
                time.sleep(3) # time module needs to be imported: import time
            else:
                print("  ERROR CRITICO: Fallaron todos los intentos para volver a la pagina de busqueda.")
                # Optional: Try a final page reload as a last resort if critical
                try:
                    print("    Fallback final: Intentando recargar la pagina actual.")
                    page.reload(wait_until="networkidle", timeout=60000)
                    if page.is_visible(input_selector_busqueda):
                        print("    Recarga parece haber llevado a la pagina de busqueda. Continuando.")
                        return True
                except Exception as ex_fallback:
                    print(f"    ERROR en fallback de recarga: {ex_fallback}")
    return False

# REFACTORED FUNCTION extraer_info_proceso_nacion
def extraer_info_proceso_nacion(page, numero_proceso_csv):
    info_proceso = { "numero_proceso_buscado": str(numero_proceso_csv) } # Ensure numero_proceso_csv is string
    print(f"\n--- Procesando NACIÓN: {numero_proceso_csv} ---")
    input_selector_busqueda = "input#ctl00_CPH1_txtNumeroProceso"

    try:
        # 1. Asegurarse de estar en la página de búsqueda correcta
        current_url = page.url
        # Check if we are NOT on the search page OR the search input is NOT visible
        if not ("BuscarAvanzado.aspx" in current_url and page.is_visible(input_selector_busqueda)):
            print(f"INFO: No en pagina de busqueda (URL: {current_url}). Intentando navegar...")
            if not volver_a_pagina_busqueda(page):
                print(f"  FALLO CRITICO: No se pudo volver a pagina de busqueda para {numero_proceso_csv}. Saltando.")
                procesos_fallidos.append(str(numero_proceso_csv))
                return None
            time.sleep(1) 

        # Verify again that the search input is visible after attempting to navigate/recover
        if not page.is_visible(input_selector_busqueda):
             print(f"  ADVERTENCIA: Campo de busqueda '{input_selector_busqueda}' no encontrado post-navegacion (URL: {page.url}) para {numero_proceso_csv}. Saltando.")
             procesos_fallidos.append(str(numero_proceso_csv))
             return None

        # 2. Poner el numero de proceso en el input y buscar
        print(f"Ingresando Nro Proceso: {numero_proceso_csv}")
        page.fill(input_selector_busqueda, str(numero_proceso_csv))
        
        buscar_proceso_btn_selector = "a#ctl00_CPH1_btnListarPliegoNumero"
        # print(f"Esperando botón buscar: {buscar_proceso_btn_selector}") # Less verbose
        page.wait_for_selector(buscar_proceso_btn_selector, timeout=30000, state="visible")
        print("Click en botón buscar proceso...")
        page.click(buscar_proceso_btn_selector)
        page.wait_for_load_state("networkidle", timeout=60000) 
        # print("Búsqueda realizada.") # Less verbose

        # 3. Clic en el resultado y cargar página de detalle
        enlace_proceso_selector = "a#ctl00_CPH1_GridListaPliegos_ctl02_lnkNumeroProceso"
        url_antes_del_detalle = page.url
        # print(f"Esperando enlace del proceso: {enlace_proceso_selector}") # Less verbose
        try:
            page.wait_for_selector(enlace_proceso_selector, timeout=20000) 
            print("Enlace del proceso encontrado. Haciendo clic...")
            page.click(enlace_proceso_selector)
            
            # Confirmar carga de página de detalle
            detalle_titulo_selector = "#ctl00_CPH1_UCVistaPreviaPliego_lblTitulo"
            # print(f"  Esperando elemento clave de la pagina de detalle: {detalle_titulo_selector}") # Less verbose
            page.wait_for_selector(detalle_titulo_selector, state="visible", timeout=45000)
            print(f"  Pagina de detalle cargada. URL: {page.url}")

            if url_antes_del_detalle == page.url:
                print(f"  ADVERTENCIA CRITICA: La URL no cambio tras clic en enlace del proceso ({page.url}) para {numero_proceso_csv}. Datos podrían ser incorrectos.")
                # Consider adding to fallidos here if this is a hard stop condition

            # 4. Esperar que el contenido clave de la cabecera cargue (MOVED HERE)
            selector_num_proceso_cab_header = "#ctl00_CPH1_UCVistaPreviaPliego_usrCabeceraPliego_lblNumPliego"
            try:
                # print(f"  DEBUG (detalle): Esperando que '{selector_num_proceso_cab_header}' tenga texto...") # Less verbose
                page.wait_for_function(
                    f"selector => document.querySelector(selector) && document.querySelector(selector).textContent.trim() !== ''",
                    selector_num_proceso_cab_header,
                    timeout=15000  
                )
                # print(f"  DEBUG (detalle): '{selector_num_proceso_cab_header}' ahora tiene texto o timeout.") # Less verbose
            except PlaywrightTimeoutError:
                print(f"  INFO (detalle): Timeout/Condición no cumplida esperando texto en '{selector_num_proceso_cab_header}'.")
            except Exception as e_wait_text:
                print(f"  ERROR (detalle): Excepcion en wait_for_function para '{selector_num_proceso_cab_header}': {e_wait_text}")

        except PlaywrightTimeoutError as e_enlace_o_detalle:
            print(f"ERROR: No se encontró enlace '{enlace_proceso_selector}' o falló carga de detalle para {numero_proceso_csv}. Error: {e_enlace_o_detalle}")
            procesos_fallidos.append(str(numero_proceso_csv))
            # No intentar volver aquí, el main loop llamará a volver_a_pagina_busqueda si es necesario o el próximo intento lo hará.
            return None 
        except Exception as e_click_detalle_inesperado:
            print(f"Error inesperado al hacer clic en enlace del proceso o al cargar detalle para {numero_proceso_csv}: {e_click_detalle_inesperado}")
            procesos_fallidos.append(str(numero_proceso_csv))
            return None

        # --- LLAMADAS A FUNCIONES DE EXTRACCIÓN --- 
        print("Extrayendo información...")
        # These functions now use _extraer_campo_con_espera and have internal waits
        informacion_basica_dict = extraer_info_basica(page)
        cronograma_dict = extraer_cronograma(page)
        detalle_productos_list = extraer_detalle_productos(page)
        info_contrato_dict = extraer_info_contrato(page)
        pliego_particular_texto = descargar_y_leer_pliego_particular(page, str(numero_proceso_csv))
        requisitos_dict = extraer_requisitos(page)

        timestamp = datetime.now(pytz.UTC).isoformat()

        # Consistent numero_proceso handling (simplified from debug script, can be enhanced if needed)
        np_basica = informacion_basica_dict.get("numero_proceso", "").strip()
        np_cabecera = informacion_basica_dict.get("numero_proceso_cabecera", "").strip()
        
        numero_proceso_real = np_basica or np_cabecera or str(numero_proceso_csv)
        if not np_basica and numero_proceso_real != str(numero_proceso_csv):
            informacion_basica_dict["numero_proceso"] = numero_proceso_real # Ensure it's set if derived from cabecera
        if not np_cabecera and numero_proceso_real != str(numero_proceso_csv):
            informacion_basica_dict["numero_proceso_cabecera"] = numero_proceso_real
        if numero_proceso_real == str(numero_proceso_csv) and (not np_basica or np_basica == ERROR_PLACEHOLDER):
            print(f"ADVERTENCIA: No se pudo extraer el número de proceso de la página para {numero_proceso_csv}. Usando el buscado.")
            if informacion_basica_dict.get("numero_proceso", "") == "" or informacion_basica_dict.get("numero_proceso") == ERROR_PLACEHOLDER : informacion_basica_dict["numero_proceso"] = numero_proceso_real
            if informacion_basica_dict.get("numero_proceso_cabecera", "") == "" or informacion_basica_dict.get("numero_proceso_cabecera") == ERROR_PLACEHOLDER : informacion_basica_dict["numero_proceso_cabecera"] = numero_proceso_real

        codigo_reparticion = numero_proceso_real.split('-')[0] if '-' in numero_proceso_real and numero_proceso_real != ERROR_PLACEHOLDER else ''
        
        info_proceso_final = {
            "numero_proceso": numero_proceso_real,
            "numero_proceso_buscado": str(numero_proceso_csv),
            "codigo_reparticion": codigo_reparticion, 
            "informacion_basica": json.dumps(informacion_basica_dict, ensure_ascii=False, indent=4),
            "cronograma": json.dumps(cronograma_dict, ensure_ascii=False, indent=4),
            "detalle_productos": json.dumps(detalle_productos_list, ensure_ascii=False, indent=4),
            "info_contrato": json.dumps(info_contrato_dict, ensure_ascii=False, indent=4),
            "pliego_particular_texto": pliego_particular_texto,
            "requisitos": json.dumps(requisitos_dict, ensure_ascii=False, indent=4),
            "timestamp_extraccion": timestamp,
            "fuente": "NACION"
        }
        
        guardar_en_firestore(info_proceso_final) 
        print(f"Extracción y guardado (intento) en Firestore completos para el proceso {numero_proceso_real}")

        # No es necesario llamar a volver_a_pagina_busqueda aquí explicitamente,
        # el inicio de la función o el bucle principal se encargarán de ello.
        return info_proceso_final

    except Exception as e:
        print(f"Error general al procesar NACIÓN {numero_proceso_csv}: {e}")
        procesos_fallidos.append(str(numero_proceso_csv))
        # No intentar volver a la página de búsqueda aquí; dejar que el bucle principal o la siguiente iteración lo manejen.
        return None


def main():
    print("Iniciando script de extracción para NACIÓN (MODO PRODUCCIÓN - TODOS LOS PROCESOS)...")
    
    # Cargar números de proceso existentes de Firestore
    procesos_existentes_firestore = obtener_numeros_proceso_firestore()
    
    # Cargar datos del CSV (esto ya estaba)
    csv_path = obtener_csv_mas_reciente(csv_directory)
    if csv_path is None:
        print("No se encontró el archivo CSV. Saliendo del script.")
        sys.exit(1)
    try:
        data = pd.read_csv(csv_path)
        data.rename(columns={'Número de proceso': 'numero_proceso'}, inplace=True)
        # Asegurar que todos los números de proceso sean strings y manejar NaN/None
        data['numero_proceso'] = data['numero_proceso'].fillna("").astype(str)
        # Filtrar filas donde numero_proceso quedó vacío después de la conversión
        data = data[data['numero_proceso'] != ""]
        print(f"Se encontraron {len(data)} procesos en el archivo CSV: {csv_path}")
    except Exception as e:
        print(f"Error al cargar o procesar el archivo CSV: {e}")
        sys.exit(1)

    if data.empty:
        print("El archivo CSV está vacío o no contiene números de proceso válidos.")
        sys.exit(0)
        
    # playwright.sync_api.Error should be PlaywrightTimeoutError or a more general playwright error
    # For now, we assume any exception from playwright is caught by broader Exception blocks.

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(45000) # Setting a default timeout for actions
            page.set_viewport_size({"width": 1920, "height": 1080})

            # REFACTORED Initial Navigation
            print("Navegando a la pagina inicial de Compr.AR (Default.aspx)...")
            try:
                page.goto("https://comprar.gob.ar/Default.aspx", timeout=120000, wait_until="domcontentloaded")
               
                search_button_selector = "a#ctl00_CPH1_CtrlBusquedasHome_btnBusquedaProcesos"
                # print(f"Esperando el boton de busqueda en Default.aspx: {search_button_selector}") # Less verbose
                page.wait_for_selector(search_button_selector, timeout=60000, state="visible")
                print("Haciendo clic en el boton de busqueda de procesos inicial.")
                page.click(search_button_selector)
               
                input_selector_busqueda_main = "input#ctl00_CPH1_txtNumeroProceso" 
                # print(f"Esperando a que cargue la pagina de busqueda inicial (elemento: {input_selector_busqueda_main})...") # Less verbose
                page.wait_for_selector(input_selector_busqueda_main, timeout=120000, state="visible")

                if "BuscarAvanzado.aspx" in page.url and page.is_visible(input_selector_busqueda_main):
                    print("Exito: En pagina de busqueda de procesos 'BuscarAvanzado.aspx'.")
                else:
                    # This exception will be caught by the outer try-except in main
                    raise Exception(f"Error critico: No se pudo llegar a la pagina de busqueda tras el click inicial. URL actual: {page.url}")

            except Exception as e_nav_inicial:
                print(f"ERROR CRITICO en la navegacion inicial: {e_nav_inicial}. Abortando.")
                if browser.is_connected(): browser.close()
                sys.exit(1)

            for index, row in data.iterrows():
                numero_proceso_actual_csv = str(row['numero_proceso']).strip() # Ensure string and stripped
                
                # Verificar si ya existe en Firestore (asegurarse que la comparación sea string vs string)
                if numero_proceso_actual_csv in procesos_existentes_firestore:
                    print(f"Proceso {numero_proceso_actual_csv} ya existe en Firestore. Omitiendo.")
                    continue # Pasar al siguiente proceso
                
                # Si no existe, extraer la información
                print(f"\nProcesando {numero_proceso_actual_csv} (no encontrado en Firestore)...")
                resultado_extraccion = extraer_info_proceso_nacion(page, numero_proceso_actual_csv)
                
                if resultado_extraccion:
                    # El guardado en Firestore ya se hace dentro de extraer_info_proceso_nacion
                    # Podríamos añadir el número de proceso a nuestro set local para evitar re-chequear si aparece duplicado en el mismo CSV
                    procesos_existentes_firestore.add(resultado_extraccion.get("numero_proceso", numero_proceso_actual_csv))
                    print(f"Procesamiento exitoso para {numero_proceso_actual_csv}.")
                else:
                    # La función extraer_info_proceso_nacion ya añade a procesos_fallidos si hay error
                    print(f"Procesamiento fallido para {numero_proceso_actual_csv}.")
                    # Aquí podrías añadir lógica adicional si falla, como reintentos o simplemente continuar.
                    # La función volver_a_pagina_busqueda se llama dentro de extraer_info_proceso_nacion
                    # para intentar recuperar la página de búsqueda tras un error.
            
            # Final del bucle
            print("\n--- Todos los procesos del CSV han sido procesados o revisados. ---")

            # Cerrar el navegador
            browser.close()
            print("Navegador cerrado.")

    except Exception as e_main:
        print(f"Error en el script principal de NACIÓN: {e_main}")
        if 'browser' in locals() and browser.is_connected():
            try:
                browser.close()
                print("Navegador cerrado en bloque de excepción.")
            except Exception as e_close:
                print(f"Error al intentar cerrar el navegador en el bloque de excepción principal: {e_close}")
    finally:
        # Imprimir los procesos que fallaron durante la ejecución
        if procesos_fallidos:
            print("\n--- Resumen de procesos fallidos ---")
            for pf in procesos_fallidos:
                print(f"- {pf}")
        else:
            print("\nNo hubo procesos fallidos durante la ejecución.")

if __name__ == '__main__':
    main()
    sys.exit(0)