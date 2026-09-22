import time
import math
import logging
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

from core.market_data import market_data
from core.performance_tracker import tracker

logger = logging.getLogger("execution_engine")

class ExecutionEngine:
    """
    Движок исполнения торговых приказов в MetaTrader 5 в 1 клик
    с расчетом лота от риска и автоматическим сопровождением (Breakeven).
    """

    def __init__(self):
        self.magic_number = 777001
        self.default_risk_pct = 2.0

    def calculate_lot_size(self, balance: float, risk_pct: float, sl_distance_pips: float) -> float:
        """
        Расчет безопасного объема лота в зависимости от размера стоп-лосса и риска депозита.
        Для XAUUSD: 1 лот = 100 oz. 1 пип ($0.10) = $10 на 1 лот (или $0.10 на 0.01 лота).
        """
        if balance <= 0:
            balance = 1000.0
        if sl_distance_pips <= 0:
            sl_distance_pips = 25.0

        risk_dollars = balance * (risk_pct / 100.0)
        # Стоимость 1 пипса на 1 стандартный лот = $10.00
        lot = risk_dollars / (sl_distance_pips * 10.0)

        # Ограничения брокера
        lot = max(0.01, min(lot, 10.0))
        return round(lot, 2)

    def execute_trade(self, direction: str, volume: float = None, risk_pct: float = None, sl: float = None, tp: float = None, comment: str = "XAUUSD AI PRO") -> dict:
        """
        Открытие позиции в MetaTrader 5 по рынку в 1 клик
        """
        direction = direction.upper()
        is_buy = direction == "BUY"
        symbol = market_data.active_symbol

        quote = market_data.get_live_quote()
        current_price = quote["price"]

        # Расчет цен по умолчанию, если не переданы
        if is_buy:
            sl = sl or round(current_price - 2.5, 2)
            tp = tp or round(current_price + 4.5, 2)
            order_type_str = "BUY"
        else:
            sl = sl or round(current_price + 2.5, 2)
            tp = tp or round(current_price - 4.5, 2)
            order_type_str = "SELL"

        sl_distance = abs(current_price - sl) * 10

        # Определение баланса счета
        account_balance = 1000.0
        if MT5_AVAILABLE and market_data.mt5_initialized:
            try:
                acc = mt5.account_info()
                if acc and acc.balance > 0:
                    account_balance = acc.balance
            except Exception:
                pass

        if not volume:
            risk = risk_pct or self.default_risk_pct
            volume = self.calculate_lot_size(account_balance, risk, sl_distance)

        # 1. Попытка реального исполнения через MetaTrader 5 API
        if MT5_AVAILABLE and market_data.mt5_initialized:
            try:
                tick = mt5.symbol_info_tick(symbol)
                sym_info = mt5.symbol_info(symbol)
                if tick and sym_info:
                    price = tick.ask if is_buy else tick.bid
                    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

                    # Пробуем различные режимы заполнения (Fillings)
                    filling_modes = [
                        mt5.ORDER_FILLING_IOC,
                        mt5.ORDER_FILLING_FOK,
                        mt5.ORDER_FILLING_RETURN
                    ]

                    res = None
                    last_error = ""

                    for filling in filling_modes:
                        request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": symbol,
                            "volume": volume,
                            "type": order_type,
                            "price": price,
                            "sl": sl,
                            "tp": tp,
                            "deviation": 20,
                            "magic": self.magic_number,
                            "comment": comment,
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": filling,
                        }
                        res = mt5.order_send(request)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            break
                        else:
                            last_error = res.comment if res else str(mt5.last_error())

                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"MT5 LIVE ORDER EXECUTED! Ticket: {res.order}, Volume: {volume}")
                        # Логируем сделку в трекер
                        tracker.log_signal(
                            direction=order_type_str,
                            timeframe="M5",
                            entry_price=price,
                            sl=sl,
                            tp1=tp,
                            tp2=round(price + (6.5 if is_buy else -6.5), 2),
                            tp3=round(price + (15.0 if is_buy else -15.0), 2)
                        )
                        return {
                            "success": True,
                            "mode": "MT5_LIVE",
                            "ticket": res.order,
                            "symbol": symbol,
                            "direction": order_type_str,
                            "volume": volume,
                            "price": res.price or price,
                            "sl": sl,
                            "tp": tp,
                            "message": f"Ордер #{res.order} успешно исполнен в MetaTrader 5!"
                        }
                    else:
                        logger.warning(f"MT5 order_send rejected ({last_error}). Falling back to simulation ticket.")
            except Exception as ex:
                logger.warning(f"MT5 execution exception: {ex}")

        # 2. Симуляция / Демо-исполнение (если Algo Trading выключен в MT5 или демо-счет)
        sim_ticket = int(time.time() * 1000) % 10000000
        tracker.log_signal(
            direction=order_type_str,
            timeframe="M5",
            entry_price=current_price,
            sl=sl,
            tp1=tp,
            tp2=round(current_price + (6.5 if is_buy else -6.5), 2),
            tp3=round(current_price + (15.0 if is_buy else -15.0), 2)
        )

        return {
            "success": True,
            "mode": "PAPER_PRO",
            "ticket": sim_ticket,
            "symbol": "XAUUSD",
            "direction": order_type_str,
            "volume": volume,
            "price": current_price,
            "sl": sl,
            "tp": tp,
            "message": f"Сделка #{sim_ticket} зарегистрирована и сопровождается ИИ-модулем!"
        }

    def get_open_positions(self) -> list:
        """Получение списка открытых позиций из MT5"""
        if MT5_AVAILABLE and market_data.mt5_initialized:
            try:
                positions = mt5.positions_get(symbol=market_data.active_symbol)
                if positions:
                    return [
                        {
                            "ticket": p.ticket,
                            "time": p.time,
                            "type": "BUY" if p.type == 0 else "SELL",
                            "volume": p.volume,
                            "price_open": p.price_open,
                            "price_current": p.price_current,
                            "sl": p.sl,
                            "tp": p.tp,
                            "profit": p.profit,
                            "magic": p.magic
                        }
                        for p in positions
                    ]
            except Exception as e:
                logger.warning(f"Error fetching open positions: {e}")
        return []

    def check_and_apply_breakeven(self) -> list:
        """
        Проверка открытых позиций: при достижении профита +25 pips
        Stop-Loss переносится в безубыток (+5 pips).
        """
        moved = []
        positions = self.get_open_positions()
        for pos in positions:
            is_buy = pos["type"] == "BUY"
            open_p = pos["price_open"]
            cur_p = pos["price_current"]
            sl = pos["sl"]
            ticket = pos["ticket"]

            if is_buy:
                profit_pips = (cur_p - open_p) * 10
                be_sl = round(open_p + 0.5, 2)  # +5 pips
                if profit_pips >= 25.0 and sl < be_sl:
                    if self.modify_sl(ticket, be_sl, pos["tp"]):
                        moved.append({"ticket": ticket, "type": "BUY", "new_sl": be_sl})
            else:
                profit_pips = (open_p - cur_p) * 10
                be_sl = round(open_p - 0.5, 2)  # +5 pips
                if profit_pips >= 25.0 and (sl == 0 or sl > be_sl):
                    if self.modify_sl(ticket, be_sl, pos["tp"]):
                        moved.append({"ticket": ticket, "type": "SELL", "new_sl": be_sl})

        return moved

    def modify_sl(self, ticket: int, new_sl: float, tp: float) -> bool:
        if not (MT5_AVAILABLE and market_data.mt5_initialized):
            return True
        try:
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl,
                "tp": tp,
            }
            res = mt5.order_send(req)
            return res and res.retcode == mt5.TRADE_RETCODE_DONE
        except Exception as e:
            logger.warning(f"Modify SL error: {e}")
            return False

execution_engine = ExecutionEngine()
