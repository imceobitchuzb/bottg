import sys
import os
import time
import subprocess
import logging
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("watchdog.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("watchdog")

def run_supervisor():
    """
    24/7 Сторожевой таймер (Watchdog Supervisor) для торгового бота.
    Гарантирует безостановочную работу: при любом падении, сбое сети или
    перезапуске процесса автоматически поднимает бота обратно.
    """
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(__file__), "run.py")
    restart_count = 0
    start_time = datetime.now()

    logger.info("=" * 65)
    logger.info("🛡️  XAUUSD 24/7 WATCHDOG SUPERVISOR ЗАПУЩЕН")
    logger.info(f"Target script: {script_path}")
    logger.info(f"Python: {python_exe}")
    logger.info("=" * 65)

    while True:
        try:
            logger.info(f"🚀 Запуск основного процесса бота (попытка #{restart_count + 1})...")
            
            # Запускаем run.py
            process = subprocess.Popen([python_exe, script_path])
            
            # Ожидаем завершения
            return_code = process.wait()
            
            restart_count += 1
            uptime = datetime.now() - start_time
            logger.warning(
                f"⚠️ Процесс завершился с кодом {return_code}. "
                f"Общее время работы: {uptime}. Рестартов: {restart_count}"
            )
            
        except KeyboardInterrupt:
            logger.info("Остановка сторожевого таймера по сигналу пользователя (Ctrl+C).")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            logger.error(f"Неожиданная ошибка супервизора: {e}")

        logger.info("⏳ Перезапуск бота через 5 секунд...")
        time.sleep(5)

if __name__ == "__main__":
    run_supervisor()
