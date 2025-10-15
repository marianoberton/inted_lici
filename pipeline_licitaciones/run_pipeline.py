import subprocess
import sys
import os

def run_script(script_name):
    """Ejecuta un script de Python y maneja los errores."""
    try:
        print(f"--- Ejecutando {script_name} ---")
        # Detectar si estamos en Docker o local
        if os.path.exists("/app/pipeline_licitaciones"):
            # Estamos en Docker
            script_path = os.path.join("/app/pipeline_licitaciones", script_name)
        else:
            # Estamos en local
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, script_name)
        
        process = subprocess.Popen(["python", "-u", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        # Stream de salida en tiempo real
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, script_path)
        print(f"--- {script_name} finalizado exitosamente ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando {script_name}:")
        print(e.stdout)
        print(e.stderr)
        print(f"--- {script_name} falló ---")
        return False

def main():
    """Orquesta la ejecución de todo el pipeline."""
    
    # Lista de scripts a ejecutar en orden
    scripts = [
        "descargar_excels.py",
        "extraccion_caba.py",
        "enviar_novedades.py",
        "procesar_documentos.py"
    ]
    
    all_success = True
    for script in scripts:
        if not run_script(script):
            all_success = False
            print(f"El pipeline se detuvo debido a un error en {script}.")
            break
            
    if all_success:
        print("\n¡El pipeline se completó exitosamente!")
    else:
        print("\nEl pipeline finalizó con errores.")
        sys.exit(1)

if __name__ == "__main__":
    main()