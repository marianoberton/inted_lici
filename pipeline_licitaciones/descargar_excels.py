from playwright.sync_api import sync_playwright
import os
import shutil
from datetime import datetime
import pandas as pd
import time
import sys

# Definir la ruta base de descarga
base_download_directory = "pipeline_licitaciones/excels"

# Obtener la fecha actual en formato YYYY-MM-DD
fecha_actual = datetime.now().strftime("%Y-%m-%d")

def convertir_excel_a_csv(ruta_excel, ruta_csv):
    """
    Convierte un archivo Excel a CSV.
    """
    try:
        excel_data = pd.read_excel(ruta_excel)
        excel_data.to_csv(ruta_csv, index=False)
        print(f"Convertido: {ruta_excel} -> {ruta_csv}")
        return True
    except Exception as e:
        print(f"Error convirtiendo {ruta_excel} a CSV: {e}")
        return False

def descargar_archivo(page, url, click_selector_1, click_selector_2, nombre_archivo, subdirectorio):
    """
    Función genérica para navegar a una página y descargar un archivo Excel.
    """
    try:
        # Crear el directorio si no existe
        download_directory = os.path.join(base_download_directory, subdirectorio)
        os.makedirs(download_directory, exist_ok=True)
        
        # Limpiar el subdirectorio antes de descargar
        print(f"Limpiando directorio: {download_directory}")
        for filename in os.listdir(download_directory):
            file_path = os.path.join(download_directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"No se pudo eliminar el archivo {file_path}: {e}")
        
        print(f"Navegando a: {url}")
        page.goto(url, timeout=90000) 
        
        print(f"Click en selector 1: {click_selector_1}")
        page.click(click_selector_1, timeout=45000)
        
        print("Esperando a que el botón de descarga esté visible...")
        page.wait_for_selector(click_selector_2, state='visible', timeout=90000) 
        
        print(f"Click en selector 2 (descarga): {click_selector_2}")
        with page.expect_download(timeout=90000) as download_info: 
            page.click(click_selector_2, timeout=45000)
        
        download = download_info.value
        print(f"Descarga iniciada: {download.suggested_filename}")
        
        archivo_excel = os.path.join(download_directory, f"{nombre_archivo}_{fecha_actual}.xlsx")
        download.save_as(archivo_excel)
        print(f"Archivo guardado como: {archivo_excel}")
        
        archivo_csv = os.path.join(download_directory, f"{nombre_archivo}_{fecha_actual}.csv")
        
        if convertir_excel_a_csv(archivo_excel, archivo_csv):
            os.remove(archivo_excel)
            print(f"Archivo Excel original eliminado: {archivo_excel}")
        else:
            print(f"Conversión a CSV fallida para {archivo_excel}. El archivo Excel no se eliminó.")
            return False

        return True

    except Exception as e:
        print(f"Error descargando {nombre_archivo} desde {url}: {e}")
        return False

def run_download_task(p, browser_args, url, click_selector_1, click_selector_2, nombre_archivo, subdirectorio):
    browser = None
    try:
        browser = p.chromium.launch(headless=True, args=browser_args)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        success = descargar_archivo(page, url, click_selector_1, click_selector_2, nombre_archivo, subdirectorio)
        return success
    finally:
        if browser:
            browser.close()

# Argumentos para ejecutar Chromium en un entorno Docker/Linux
browser_args = [
    '--no-sandbox',
    '--disable-dev-shm-usage'
]

# Configurar reintentos
max_retries = 2
retry_delay = 60  # 1 minuto

all_success = True

with sync_playwright() as p:
    # --- Descarga CABA ---
    print("\n--- Iniciando descarga CABA ---")
    success_caba = False
    for attempt in range(1, max_retries + 1):
        print(f"Intento {attempt} de {max_retries} para descargar reporteCaba")
        success_caba = run_download_task(p, browser_args,
                                    "https://www.buenosairescompras.gob.ar/", 
                                    "//a[h4[contains(text(), 'Licitaciones de apertura próxima')]]", 
                                    'a#ctl00_CPH1_btnDescargarReporteExcel',
                                    "reporteCaba",
                                    "caba")
        if success_caba:
            print("Descarga CABA exitosa")
            break
        else:
            print(f"Descarga CABA fallida en el intento {attempt}")
            if attempt < max_retries:
                print(f"Esperando {retry_delay} segundos antes del próximo intento para CABA")
                time.sleep(retry_delay)
            else:
                print("Fallaron todos los intentos para CABA.")
                all_success = False

    # --- Descarga PBA ---
    print("\n--- Iniciando descarga PBA ---")
    success_pba = False
    for attempt in range(1, max_retries + 1):
        print(f"Intento {attempt} de {max_retries} para descargar reportePBA")
        success_pba = run_download_task(p, browser_args,
                                    "https://pbac.cgp.gba.gov.ar/",
                                    "a[href='ListarAperturaProxima.aspx']:has-text('Ver Todos')",
                                    "a#ctl00_CPH1_btnDescargarReporteExcel",
                                    "reportePBA",
                                    "pba")
        if success_pba:
            print("Descarga PBA exitosa")
            break
        else:
            print(f"Descarga PBA fallida en el intento {attempt}")
            if attempt < max_retries:
                print(f"Esperando {retry_delay} segundos antes del próximo intento para PBA")
                time.sleep(retry_delay)
            else:
                print("Fallaron todos los intentos para PBA.")
                all_success = False

    # --- Descarga Nación ---
    print("\n--- Iniciando descarga Nación ---")
    success_nacion = False
    for attempt in range(1, max_retries + 1):
        print(f"Intento {attempt} de {max_retries} para descargar reporteNacion")
        success_nacion = run_download_task(p, browser_args,
                                       "https://comprar.gob.ar/Default.aspx",
                                       "a#ctl00_CPH1_CtrlConsultasFrecuentes_lnkVerTodos",
                                       "a#ctl00_CPH1_btnDescargarReporteExcelAperturaProxima",
                                       "reporteNacion",
                                       "nacion")
        if success_nacion:
            print("Descarga Nación exitosa")
            break
        else:
            print(f"Descarga Nación fallida en el intento {attempt}")
            if attempt < max_retries:
                print(f"Esperando {retry_delay} segundos antes del próximo intento para Nación")
                time.sleep(retry_delay)
            else:
                print("Fallaron todos los intentos para Nación.")
                all_success = False

# Evaluar el resultado final - CABA es crítico, PBA y Nación son opcionales
if not success_caba:
    print("\nERROR CRÍTICO: La descarga de CABA falló. El pipeline no puede continuar sin los datos de CABA.")
    sys.exit(1)
else:
    print("\nDescarga de CABA exitosa - el pipeline puede continuar.")
    
    # Reportar el estado de las descargas opcionales
    if success_pba:
        print("✓ Descarga de PBA exitosa")
    else:
        print("⚠ Descarga de PBA falló - continuando sin estos datos")
    
    if success_nacion:
        print("✓ Descarga de Nación exitosa")
    else:
        print("⚠ Descarga de Nación falló - continuando sin estos datos")
    
    if all_success:
        print("\n🎉 Todas las descargas se completaron exitosamente.")
    else:
        print("\n✅ Pipeline continuará con los datos disponibles (CABA es suficiente para el funcionamiento básico).")

# Si el script llega aquí, significa que al menos CABA fue exitoso y el pipeline puede continuar
