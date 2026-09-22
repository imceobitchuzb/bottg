import time
import math
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
import requests
import numpy as np

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

from config import DEFAULT_SYMBOL, ALT_SYMBOLS, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH

logger = logging.getLogger("market_data")
logging.basicConfig(level=logging.INFO)

class MarketDataProvider:
    def __init__(self):
        self.mt5_initialized = False
        self.active_symbol = DEFAULT_SYMBOL
        self.last_cached_quote = {
            "symbol": "XAUUSD",
            "bid": 2734.50,
            "ask": 2734.80,
            "price": 2734.65,
            "spread": 0.30,
            "high": 2748.20,
            "low": 2721.40,
            "change_pct": 0.48,
            "source": "cache",
            "time": datetime.now(timezone.utc).isoformat()
        }
        self.init_mt5()

    def init_mt5(self) -> bool:
        """Попытка подключения к MT5"""
        if not MT5_AVAILABLE:
            logger.info("MetaTrader5 python module not available.")
            return False

        try:
            init_args = {}
            if MT5_PATH:
                init_args["path"] = MT5_PATH

            if mt5.initialize(**init_args):
                if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
                    logged_in = mt5.login(int(MT5_LOGIN), password=MT5_PASSWORD, server=MT5_SERVER)
                    if not logged_in:
                        logger.warning(f"MT5 login failed: {mt5.last_error()}")
                
                # Check symbol availability
                symbols = mt5.symbols_get()
                available_names = [s.name for s in symbols] if symbols else []
                for s in ALT_SYMBOLS:
                    if s in available_names:
                        self.active_symbol = s
                        mt5.symbol_select(s, True)
                        break

                self.mt5_initialized = True
                logger.info(f"MT5 successfully connected. Symbol: {self.active_symbol}")
                return True
            else:
                logger.info(f"MT5 initialization skipped (terminal not running): {mt5.last_error()}")
                return False
        except Exception as e:
            logger.warning(f"MT5 connection error: {e}")
            self.mt5_initialized = False
            return False

    def login_account(self, login: int, password: str, server: str) -> dict:
        """Авторизация в торговом счете брокера через MetaTrader 5"""
        if not MT5_AVAILABLE:
            return {"success": False, "message": "Модуль MetaTrader5 не установлен на сервере"}

        try:
            if not self.mt5_initialized:
                self.init_mt5()

            login_num = int(login)
            logged_in = mt5.login(login_num, password=str(password), server=str(server))
            if logged_in:
                acc = mt5.account_info()
                symbols = mt5.symbols_get()
                available_names = [s.name for s in symbols] if symbols else []
                for s in ALT_SYMBOLS:
                    if s in available_names:
                        self.active_symbol = s
                        mt5.symbol_select(s, True)
                        break

                self.mt5_initialized = True
                self._save_to_env(login_num, password, server)
                logger.info(f"MT5 Account successfully logged in: {login_num} @ {server}")

                return {
                    "success": True,
                    "login": login_num,
                    "server": str(server),
                    "balance": round(acc.balance, 2) if acc else 0.0,
                    "equity": round(acc.equity, 2) if acc else 0.0,
                    "currency": acc.currency if acc else "USD",
                    "company": acc.company if acc else "Broker",
                    "leverage": acc.leverage if acc else 100,
                    "name": acc.name if acc else "Trader"
                }
            else:
                err_code, err_msg = mt5.last_error()
                return {
                    "success": False,
                    "message": f"Ошибка авторизации брокера ({err_code}): {err_msg}. Проверьте правильность Логина, Пароля и Сервера."
                }
        except Exception as e:
            return {"success": False, "message": f"Ошибка подключения: {str(e)}"}

    def get_account_info(self) -> dict:
        """Получение информации о текущем подключенном счете MT5"""
        if MT5_AVAILABLE and self.mt5_initialized:
            try:
                acc = mt5.account_info()
                if acc and acc.login > 0:
                    return {
                        "connected": True,
                        "login": acc.login,
                        "server": acc.server,
                        "balance": round(acc.balance, 2),
                        "equity": round(acc.equity, 2),
                        "currency": acc.currency,
                        "company": acc.company,
                        "leverage": acc.leverage,
                        "name": acc.name
                    }
            except Exception:
                pass
        return {"connected": False, "balance": 0.0, "currency": "USD"}

    def _save_to_env(self, login, password, server):
        """Сохранение реквизитов в .env"""
        try:
            env_path = Path(__file__).resolve().parent.parent / ".env"
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8")
                content = re.sub(r"MT5_LOGIN=.*", f"MT5_LOGIN={login}", content)
                content = re.sub(r"MT5_PASSWORD=.*", f"MT5_PASSWORD={password}", content)
                content = re.sub(r"MT5_SERVER=.*", f"MT5_SERVER={server}", content)
                env_path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Error saving to .env: {e}")

    def get_live_quote(self) -> dict:
        """Получение живой котировки XAUUSD (MT5 -> Live Web API -> Fallback)"""
        if self.mt5_initialized:
            try:
                tick = mt5.symbol_info_tick(self.active_symbol)
                sym_info = mt5.symbol_info(self.active_symbol)
                if tick and sym_info:
                    digits = sym_info.digits or 2
                    spread = round(tick.ask - tick.bid, digits)
                    high = sym_info.askhigh if (hasattr(sym_info, 'askhigh') and sym_info.askhigh > 0) else round(tick.ask * 1.005, digits)
                    low = sym_info.bidlow if (hasattr(sym_info, 'bidlow') and sym_info.bidlow > 0) else round(tick.bid * 0.995, digits)
                    change = sym_info.price_change if hasattr(sym_info, 'price_change') else 0.0

                    quote = {
                        "symbol": "XAUUSD",
                        "broker_symbol": self.active_symbol,
                        "bid": round(tick.bid, digits),
                        "ask": round(tick.ask, digits),
                        "price": round((tick.bid + tick.ask) / 2.0, digits),
                        "spread": spread,
                        "high": high,
                        "low": low,
                        "change_pct": round(change, 2),
                        "source": "MetaTrader 5 (Direct)",
                        "time": datetime.now(timezone.utc).isoformat()
                    }
                    self.last_cached_quote = quote
                    return quote
            except Exception as e:
                logger.warning(f"Error reading MT5 tick: {e}")

        # Web Live API fallback (Binance PAXG / Gold spot / Forex API)
        web_quote = self._fetch_web_live_gold()
        if web_quote:
            self.last_cached_quote = web_quote
            return web_quote

        return self.last_cached_quote

    def _fetch_web_live_gold(self) -> dict:
        """Получение котировки через открытые финансовые API (PAXG / Yahoo / Crypto Gold)"""
        try:
            # PAXG / USDT на Binance дает непрерывную котировку тройской унции золота 24/7 с точностью до секунды
            resp = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=PAXGUSDT", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                last_price = float(data["lastPrice"])
                bid = float(data.get("bidPrice", last_price - 0.25))
                ask = float(data.get("askPrice", last_price + 0.25))
                high = float(data["highPrice"])
                low = float(data["lowPrice"])
                change_pct = float(data["priceChangePercent"])

                return {
                    "symbol": "XAUUSD",
                    "broker_symbol": "PAXG/Gold Spot",
                    "bid": round(bid, 2),
                    "ask": round(ask, 2),
                    "price": round(last_price, 2),
                    "spread": round(ask - bid, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "change_pct": round(change_pct, 2),
                    "source": "Gold Live Feed (24/7 Spot)",
                    "time": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.debug(f"PAXG feed error: {e}")

        try:
            # Альтернативный источник: Yahoo Finance Gold Futures (GC=F)
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d", headers=headers, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice", 2735.0)
                prev_close = meta.get("chartPreviousClose", price)
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)
                return {
                    "symbol": "XAUUSD",
                    "broker_symbol": "GC=F",
                    "bid": round(price - 0.15, 2),
                    "ask": round(price + 0.15, 2),
                    "price": round(price, 2),
                    "spread": 0.30,
                    "high": round(meta.get("regularMarketDayHigh", price * 1.004), 2),
                    "low": round(meta.get("regularMarketDayLow", price * 0.996), 2),
                    "change_pct": change_pct,
                    "source": "Yahoo Gold Live",
                    "time": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.debug(f"Yahoo feed error: {e}")

        return None

    def get_candles(self, timeframe: str = "M15", count: int = 100) -> list:
        """Получение свечей для заданного таймфрейма (MT5 -> Binance PAXG klines -> Synthetic)"""
        tf_map_mt5 = {
            "M1": mt5.TIMEFRAME_M1 if mt5 else 1,
            "M5": mt5.TIMEFRAME_M5 if mt5 else 5,
            "M15": mt5.TIMEFRAME_M15 if mt5 else 15,
            "M30": mt5.TIMEFRAME_M30 if mt5 else 30,
            "H1": mt5.TIMEFRAME_H1 if mt5 else 60,
            "H4": mt5.TIMEFRAME_H4 if mt5 else 240,
            "D1": mt5.TIMEFRAME_D1 if mt5 else 1440,
        }

        if self.mt5_initialized:
            try:
                mt5_tf = tf_map_mt5.get(timeframe.upper(), mt5.TIMEFRAME_M15)
                rates = mt5.copy_rates_from_pos(self.active_symbol, mt5_tf, 0, count)
                if rates is not None and len(rates) > 0:
                    candles = []
                    for r in rates:
                        candles.append({
                            "time": int(r["time"]),
                            "open": float(round(r["open"], 2)),
                            "high": float(round(r["high"], 2)),
                            "low": float(round(r["low"], 2)),
                            "close": float(round(r["close"], 2)),
                            "volume": float(r["tick_volume"])
                        })
                    return candles
            except Exception as e:
                logger.warning(f"Error reading MT5 candles: {e}")

        # Web API klines (Binance PAXG)
        interval_map = {
            "M1": "1m",
            "M5": "5m",
            "M15": "15m",
            "M30": "30m",
            "H1": "1h",
            "H4": "4h",
            "D1": "1d"
        }
        interval = interval_map.get(timeframe.upper(), "15m")
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={count}"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                raw_data = resp.json()
                candles = []
                for item in raw_data:
                    candles.append({
                        "time": int(item[0] // 1000),
                        "open": round(float(item[1]), 2),
                        "high": round(float(item[2]), 2),
                        "low": round(float(item[3]), 2),
                        "close": round(float(item[4]), 2),
                        "volume": round(float(item[5]), 2)
                    })
                return candles
        except Exception as e:
            logger.debug(f"Web klines error: {e}")

        # Fallback synthetic candles around current price
        base_price = self.last_cached_quote["price"]
        candles = []
        now_ts = int(time.time())
        step_sec = 60 * (15 if timeframe == "M15" else 5 if timeframe == "M5" else 60)
        curr = base_price - 8.0
        for i in range(count):
            t = now_ts - (count - i) * step_sec
            drift = np.sin(i / 5.0) * 2.5 + (np.random.random() - 0.48) * 3.0
            o = round(curr, 2)
            c = round(curr + drift, 2)
            h = round(max(o, c) + abs(np.random.random() * 1.8), 2)
            l = round(min(o, c) - abs(np.random.random() * 1.8), 2)
            curr = c
            candles.append({
                "time": t,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": int(150 + np.random.random() * 400)
            })
        return candles

market_data = MarketDataProvider()
