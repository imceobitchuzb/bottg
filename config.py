import os
from pathlib import Path
from dotenv import load_dotenv
import logging

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8620337805:AAH8ULnPoA4CXcyck2m7mQRMvPlkiLM4l1w")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WEBAPP_URL = os.getenv("WEBAPP_URL", f"http://localhost:{PORT}")

def set_webapp_url(url: str):
    global WEBAPP_URL
    WEBAPP_URL = url
    logger_cfg = logging.getLogger("config")
    logger_cfg.info(f"Updated WEBAPP_URL to: {WEBAPP_URL}")

# MetaTrader 5
MT5_LOGIN = os.getenv("MT5_LOGIN", "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "")

# XAUUSD Symbol Settings
DEFAULT_SYMBOL = "XAUUSD"
ALT_SYMBOLS = ["XAUUSD", "GOLD", "XAUUSDm", "XAUUSD.a", "XAU_USD"]

# Analysis Timeframes
TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
FORECAST_HORIZONS = ["5m", "10m", "15m", "30m", "1h", "1d"]
