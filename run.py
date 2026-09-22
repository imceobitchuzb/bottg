import sys
import os
import re
import time
import asyncio
import logging
import threading
import subprocess
import uvicorn

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

import config
from config import HOST, PORT, TELEGRAM_BOT_TOKEN, WEBAPP_URL, set_webapp_url
from backend.app import app as fastapi_app
from bot.telegram_bot import create_bot_app
from core.auto_scanner import auto_scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("master_runner")

def run_fastapi():
    """Запуск FastAPI сервера в отдельном потоке с автоматическим перезапуском"""
    while True:
        try:
            logger.info(f"Starting FastAPI server on http://{HOST}:{PORT}")
            uv_config = uvicorn.Config(
                fastapi_app,
                host=HOST,
                port=PORT,
                log_level="warning",
                access_log=False
            )
            server = uvicorn.Server(uv_config)
            server.run()
        except Exception as e:
            logger.error(f"FastAPI server crashed: {e}. Перезапуск через 3 сек...")
            time.sleep(3)

def ensure_cloudflared():
    """Проверяет наличие cloudflared.exe и автоматически скачивает при необходимости"""
    cf_path = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    if os.path.exists(cf_path):
        return cf_path
    
    logger.info("cloudflared.exe не найден. Автоматическая загрузка официального бинарника Cloudflare...")
    try:
        import urllib.request
        download_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        urllib.request.urlretrieve(download_url, cf_path)
        logger.info(f"cloudflared.exe успешно загружен в {cf_path}")
        return cf_path
    except Exception as e:
        logger.warning(f"Не удалось автоматически загрузить cloudflared.exe: {e}")
        return None

def start_tunnel():
    """Запуск Cloudflare Tunnel с автоматическим переподключением при обрыве связи"""
    cf_path = ensure_cloudflared()
    if not cf_path or not os.path.exists(cf_path):
        logger.warning("cloudflared.exe не найден. Запуск только с локальным URL.")
        return

    while True:
        try:
            logger.info("Запуск Cloudflare HTTPS туннеля для Telegram Mini App...")
            proc = subprocess.Popen(
                [cf_path, "tunnel", "--url", f"http://localhost:{PORT}"],
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for line in proc.stderr:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    tunnel_url = m.group(0)
                    set_webapp_url(tunnel_url)
                    logger.info(f"✨ PUBLIC HTTPS TELEGRAM MINI APP URL: {tunnel_url}")
                    print("=" * 65, flush=True)
                    print(f"✨ PUBLIC HTTPS MINI APP URL: {tunnel_url}", flush=True)
                    print("=" * 65, flush=True)

                    # Автоматически обновляем кнопку Menu Button на серверах Telegram
                    try:
                        import requests
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatMenuButton",
                            json={
                                "menu_button": {
                                    "type": "web_app",
                                    "text": "🚀 ИИ Терминал",
                                    "web_app": {"url": tunnel_url}
                                }
                            },
                            timeout=5
                        )
                        logger.info("Telegram Bot menu button automatically synchronized!")
                    except Exception as ex:
                        logger.warning(f"Could not sync menu button: {ex}")
            proc.wait()
            logger.warning("Cloudflare tunnel процесс завершился. Переподключение через 5 сек...")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Tunnel restart loop error: {e}. Переподключение через 5 сек...")
            time.sleep(5)

def main():
    print("=" * 65, flush=True)
    print("🚀  XAUUSD AI PRO TRADER 100/100 — TELEGRAM BOT & MINI APP", flush=True)
    print("=" * 65, flush=True)
    print(f"🤖 Bot Token:  {TELEGRAM_BOT_TOKEN[:10]}...{TELEGRAM_BOT_TOKEN[-5:]}", flush=True)
    print(f"⚡ Local Web Terminal: http://localhost:{PORT}", flush=True)
    print("=" * 65, flush=True)

    # 1. Запуск веб-сервера FastAPI (раздает Mini App и API)
    web_thread = threading.Thread(target=run_fastapi, daemon=True)
    web_thread.start()

    # 2. Запуск Cloudflare Tunnel для HTTPS
    tunnel_thread = threading.Thread(target=start_tunnel, daemon=True)
    tunnel_thread.start()

    # 3. Запуск 24/5 Авто-сканера рынка и Trade Manager (Breakeven)
    auto_scanner.start()

    # Небольшая пауза для инициализации туннеля
    time.sleep(3)

    # 4. Бесконечный цикл запуска Telegram Бота с авто-восстановлением
    while True:
        try:
            bot_app = create_bot_app()
            logger.info("Starting Telegram Bot long-polling...")
            bot_app.run_polling(drop_pending_updates=True)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Бот остановлен пользователем.")
            break
        except Exception as e:
            logger.error(f"Сбой Telegram Bot long-polling: {e}. Перезапуск через 5 сек...")
            time.sleep(5)

if __name__ == "__main__":
    main()
