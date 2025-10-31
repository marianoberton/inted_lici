import os
import subprocess
import platform
import requests
from datetime import datetime, timedelta


def _read_last_lines(path, lines=50):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            data = f.readlines()
            return ''.join(data[-lines:]).strip()
    except Exception:
        return ""


def _file_age_seconds(path):
    try:
        mtime = os.path.getmtime(path)
        return int(datetime.now().timestamp() - mtime)
    except Exception:
        return None


def _cron_running():
    try:
        result = subprocess.run(["pgrep", "-x", "cron"], capture_output=True)
        return result.returncode == 0
    except Exception:
        # Si pgrep no está disponible, intentar con ps
        try:
            ps = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            return ' cron ' in ps.stdout or ' CRON ' in ps.stdout
        except Exception:
            return False


def _build_report(context: str, exit_code: int | None):
    tz = os.getenv('TZ', 'Desconocido')
    now = datetime.now()
    cron_file = '/etc/cron.d/pipeline'
    heartbeat_path = '/app/data/logs/cron-heartbeat.log'
    pipeline_log_path = '/app/data/logs/cron-pipeline.log'
    debug_log_path = '/app/data/logs/cron-debug.log'

    cron_ok = _cron_running()
    heartbeat_age = _file_age_seconds(heartbeat_path)
    heartbeat_last = _read_last_lines(heartbeat_path, lines=3)
    pipeline_tail = _read_last_lines(pipeline_log_path, lines=40)
    debug_tail = _read_last_lines(debug_log_path, lines=10)

    cron_schedule = "(no disponible)"
    if os.path.isfile(cron_file):
        try:
            with open(cron_file, 'r', encoding='utf-8', errors='ignore') as f:
                cron_schedule = f.read().strip()
        except Exception:
            pass

    # Determinar estado del último pipeline por heurística del log
    pipeline_status = "desconocido"
    if pipeline_tail:
        if "¡El pipeline se completó exitosamente!" in pipeline_tail:
            pipeline_status = "exitoso"
        elif "El pipeline finalizó con errores." in pipeline_tail:
            pipeline_status = "con errores"

    hb_str = "sin datos"
    hb_state = "N/A"
    if heartbeat_age is not None:
        td = timedelta(seconds=heartbeat_age)
        hb_str = f"hace {td}"
        hb_state = "OK" if heartbeat_age < 600 else "STALE (>10m)"

    # Info de plataforma
    host_info = platform.platform()

    report_lines = [
        f"🧩 Estado del Servicio (contexto: {context})",
        f"🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} TZ={tz}",
        f"⚙️ Cron en ejecución: {'sí' if cron_ok else 'no'}",
        f"📄 /etc/cron.d/pipeline:",
        f"{cron_schedule}",
        f"❤️ Heartbeat: {hb_state} (última actualización {hb_str})",
    ]

    if exit_code is not None:
        report_lines.append(f"🚥 Última ejecución exit code: {exit_code}")
    report_lines.append(f"📦 Host: {host_info}")

    # Resumen de pipeline
    report_lines.append(f"📋 Pipeline último estado: {pipeline_status}")
    if pipeline_tail:
        report_lines.append("🔎 Últimas líneas de cron-pipeline.log:")
        # Limitar tamaño para Telegram
        tail_preview = pipeline_tail[-1200:]
        report_lines.append(tail_preview)

    if debug_tail:
        report_lines.append("🧪 Debug env (parcial):")
        report_lines.append(debug_tail)

    return "\n".join(report_lines)


def send_telegram(mensaje: str):
    # DEBUG: Usar cualquier token disponible, priorizando TELEGRAM_TOKEN_CABA
    token = os.getenv('TELEGRAM_TOKEN_CABA') or os.getenv('TELEGRAM_TOKEN') or os.getenv('TELEGRAM_TOKEN_NACION')
    
    # DEBUG: Siempre usar chat personal de Mariano
    chat_ids = [1880232778]

    if not token:
        print("⚠️ Sin TELEGRAM_TOKEN disponible, no se enviará reporte")
        print("🔍 Tokens disponibles:")
        print(f"  TELEGRAM_TOKEN_CABA: {'✓' if os.getenv('TELEGRAM_TOKEN_CABA') else '✗'}")
        print(f"  TELEGRAM_TOKEN: {'✓' if os.getenv('TELEGRAM_TOKEN') else '✗'}")
        print(f"  TELEGRAM_TOKEN_NACION: {'✓' if os.getenv('TELEGRAM_TOKEN_NACION') else '✗'}")
        return

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    for cid in chat_ids:
        try:
            resp = requests.post(url, data={
                'chat_id': cid,
                'text': mensaje,
                'disable_web_page_preview': True
            }, timeout=20)
            print(f"Telegram status -> {cid}: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Telegram error response: {resp.text}")
        except Exception as e:
            print(f"Error enviando a {cid}: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enviar reporte de estado del servicio por Telegram')
    parser.add_argument('--context', default=os.getenv('RUN_CONTEXT', 'manual'))
    parser.add_argument('--exit-code', type=int, default=None)
    args = parser.parse_args()

    msg = _build_report(args.context, args.exit_code)
    send_telegram(msg)


if __name__ == '__main__':
    main()