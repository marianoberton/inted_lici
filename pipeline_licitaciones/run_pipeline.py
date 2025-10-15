import subprocess
import sys
import os
import requests
from datetime import datetime

# Configuración de Telegram (usando las mismas variables de entorno que los otros scripts)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_CABA')
TELEGRAM_CHAT_IDS = [int(chat_id) for chat_id in os.getenv('TELEGRAM_CHAT_IDS_CABA', '').split(',') if chat_id.strip()]

def enviar_mensaje_telegram(mensaje):
    """Envía un mensaje de confirmación a Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS:
        print("⚠️ Configuración de Telegram no disponible, saltando envío de mensaje")
        return
    
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {
            'chat_id': chat_id,
            'text': mensaje,
            'parse_mode': 'Markdown'
        }
        for intento in range(3):  # Intentar enviar hasta 3 veces
            try:
                response = requests.post(url, data=payload, timeout=10)
                if response.status_code == 200:
                    print(f"✅ Mensaje de confirmación enviado a {chat_id}")
                    break
                else:
                    print(f"❌ Error al enviar mensaje a {chat_id}: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Intento {intento + 1} - Error de conexión al enviar mensaje: {e}")
                if intento < 2:  # Solo esperar si no es el último intento
                    import time
                    time.sleep(2)

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
    
    inicio_ejecucion = datetime.now()
    print(f"🚀 Iniciando pipeline a las {inicio_ejecucion.strftime('%H:%M:%S del %d/%m/%Y')}")
    
    # Lista de scripts a ejecutar en orden
    scripts = [
        "descargar_excels.py",
        "extraccion_caba.py",
        "enviar_novedades.py",
        "procesar_documentos.py"
    ]
    
    all_success = True
    scripts_ejecutados = []
    scripts_fallidos = []
    
    for script in scripts:
        if run_script(script):
            scripts_ejecutados.append(script)
        else:
            scripts_fallidos.append(script)
            all_success = False
            print(f"El pipeline se detuvo debido a un error en {script}.")
            break
    
    fin_ejecucion = datetime.now()
    duracion = fin_ejecucion - inicio_ejecucion
    
    # Preparar mensaje de confirmación
    if all_success:
        print("\n¡El pipeline se completó exitosamente!")
        mensaje = f"✅ *Pipeline Ejecutado Exitosamente*\n\n"
        mensaje += f"🕐 *Hora:* {fin_ejecucion.strftime('%H:%M:%S del %d/%m/%Y')}\n"
        mensaje += f"⏱️ *Duración:* {str(duracion).split('.')[0]}\n"
        mensaje += f"📋 *Scripts ejecutados:* {len(scripts_ejecutados)}/{len(scripts)}\n\n"
        mensaje += "🔍 *Módulos procesados:*\n"
        for script in scripts_ejecutados:
            mensaje += f"• {script.replace('.py', '').replace('_', ' ').title()}\n"
        mensaje += "\n💡 *Estado:* Sin novedades detectadas"
    else:
        print("\nEl pipeline finalizó con errores.")
        mensaje = f"❌ *Pipeline Ejecutado con Errores*\n\n"
        mensaje += f"🕐 *Hora:* {fin_ejecucion.strftime('%H:%M:%S del %d/%m/%Y')}\n"
        mensaje += f"⏱️ *Duración:* {str(duracion).split('.')[0]}\n"
        mensaje += f"📋 *Scripts ejecutados:* {len(scripts_ejecutados)}/{len(scripts)}\n\n"
        if scripts_ejecutados:
            mensaje += "✅ *Módulos exitosos:*\n"
            for script in scripts_ejecutados:
                mensaje += f"• {script.replace('.py', '').replace('_', ' ').title()}\n"
        if scripts_fallidos:
            mensaje += f"\n❌ *Módulo fallido:* {scripts_fallidos[0].replace('.py', '').replace('_', ' ').title()}"
    
    # Enviar mensaje de confirmación
    enviar_mensaje_telegram(mensaje)
    
    if not all_success:
        sys.exit(1)

if __name__ == "__main__":
    main()