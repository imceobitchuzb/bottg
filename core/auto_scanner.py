import time
import logging
import threading
from datetime import datetime, timezone
import requests

from config import TELEGRAM_BOT_TOKEN
from core.market_data import market_data
from core.signal_engine import signal_engine
from core.performance_tracker import tracker
from core.execution_engine import execution_engine

logger = logging.getLogger("auto_scanner")

class AutoScanner:
    """
    24/5 Автономный фоновый сканер рынка XAUUSD.
    Непрерывно сканирует рынок на предмет идеальных точек входа,
    сопровождает открытые сделки (перенос в безубыток) и
    рассылает автоматические Push-сигналы в Telegram.
    """

    def __init__(self):
        self.running = False
        self.thread = None
        self.last_alert_time = {"BUY": 0, "SELL": 0}
        self.alert_cooldown_seconds = 900  # 15 минут кулдаун между алертом одного направления
        self.check_interval_seconds = 20   # Проверка каждые 20 секунд

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()
        logger.info("24/5 Auto-Scanner and Position Manager started successfully.")

    def stop(self):
        self.running = False

    def _scan_loop(self):
        while self.running:
            try:
                self._check_market_and_alerts()
            except Exception as e:
                logger.error(f"Error in auto_scanner loop: {e}")
            time.sleep(self.check_interval_seconds)

    def _check_market_and_alerts(self):
        quote = market_data.get_live_quote()
        current_price = quote["price"]

        # 1. Проверка исходов активных сигналов (достижение TP / SL)
        resolved_signals = tracker.check_and_update_active_signals(current_price)
        for res in resolved_signals:
            outcome = res.get("outcome", "")
            pips = res.get("pips", 0)
            sign = "+" if pips > 0 else ""
            msg = ""
            if "TP" in outcome:
                tp_num = outcome.replace("_HIT", "")
                msg = (
                    f"🎯 <b>СИГНАЛ XAUUSD ВЗЯЛ ЦЕЛЬ {tp_num}!</b>\n"
                    f"Направление: <b>{res['direction']}</b>\n"
                    f"Результат: <b>{sign}{pips} pips 🟢</b>\n"
                    f"Цена закрытия: <code>${current_price:.2f}</code>"
                )
            elif "SL" in outcome:
                msg = (
                    f"🛑 <b>СИГНАЛ XAUUSD ЗАКРЫЛСЯ ПО СТОПУ:</b>\n"
                    f"Направление: <b>{res['direction']}</b> | Результат: <b>{pips} pips 🔴</b>\n"
                    f"<i>Сработал риск-менеджмент. Ждем следующий идеальный сетап.</i>"
                )
            if msg:
                self._broadcast_message(msg)

        # 2. Проверка открытых позиций в MT5 на авто-безубыток (Breakeven)
        moved_positions = execution_engine.check_and_apply_breakeven()
        for pos in moved_positions:
            msg = (
                f"🛡️ <b>АВТОМАТИЧЕСКИЙ БЕЗУБЫТОК MT5!</b>\n"
                f"Позиция #{pos['ticket']} ({pos['type']}) переведена в безубыток!\n"
                f"Новый Stop-Loss: <code>{pos['new_sl']}</code> (+5 pips).\n"
                f"<i>Риск закрыт в ноль — сделка теперь 100% бесплатная!</i>"
            )
            self._broadcast_message(msg)

        # 3. Сканирование на новые точки входа (M5 / M15)
        signal = signal_engine.generate_signal(timeframe="M5")
        direction = signal["direction"]
        confidence_num = int(signal["confidence"].replace("%", ""))

        now_ts = time.time()
        time_since_last = now_ts - self.last_alert_time.get(direction, 0)

        # Критерии для авто-алерта:
        # Уверенность >= 86%, прошло более 15 минут с прошлого алерта
        if confidence_num >= 86 and time_since_last >= self.alert_cooldown_seconds:
            self.last_alert_time[direction] = now_ts
            logger.info(f"🚨 AUTO-SCANNER TRIGGERED NEW SETUP: {direction} @ {current_price}")

            # Логируем сигнал в трекер
            tracker.log_signal(
                direction=direction,
                timeframe="M5",
                entry_price=current_price,
                sl=signal["stop_loss"],
                tp1=signal["take_profit_1"],
                tp2=signal["take_profit_2"],
                tp3=signal["take_profit_3"]
            )

            is_buy = direction == "BUY"
            icon = "🟢" if is_buy else "🔴"
            action_text = "ПОКУПКА (LONG)" if is_buy else "ПРОДАЖА (SHORT)"

            alert_text = (
                f"🚨 <b>АВТО-СИГНАЛ XAUUSD — НАЙДЕНА ТОЧКА ВХОДА!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{icon} <b>Действие:</b> <b>{action_text}</b>\n"
                f"📍 <b>Зона входа:</b> <code>{signal['entry_zone']}</code>\n"
                f"🛑 <b>Stop-Loss:</b> <code>{signal['stop_loss']}</code> (-25 pips)\n"
                f"💎 <b>TP 1:</b> <code>{signal['take_profit_1']}</code> (+35 pips)\n"
                f"💎 <b>TP 2:</b> <code>{signal['take_profit_2']}</code> (+65 pips)\n"
                f"💎 <b>TP 3:</b> <code>{signal['take_profit_3']}</code> (+150 pips)\n\n"
                f"⚖️ <b>Risk/Reward:</b> {signal['risk_reward']}\n"
                f"🛡️ <b>Вероятность:</b> {signal['confidence']}\n"
                f"🏛️ <b>SMC:</b> {signal['smc']['structure']}\n\n"
                f"💡 <i>{signal['rationale']}</i>"
            )

            # Отправка с инлайн-кнопкой открытия в MT5
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": f"⚡ Открыть {direction} в MT5 в 1 клик",
                            "callback_data": f"btn_exec_market_{direction.lower()}"
                        }
                    ],
                    [
                        {
                            "text": "📊 Посмотреть в ИИ Терминале",
                            "callback_data": "btn_signal"
                        }
                    ]
                ]
            }

            self._broadcast_message(alert_text, reply_markup=keyboard)

    def _broadcast_message(self, text: str, reply_markup: dict = None):
        """Рассылка сообщения всем активным подписчикам бота"""
        subscribers = tracker.get_all_active_subscribers()
        if not subscribers:
            return

        for chat_id in subscribers:
            try:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup

                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json=payload,
                    timeout=4
                )
            except Exception as e:
                logger.warning(f"Error broadcasting alert to {chat_id}: {e}")

auto_scanner = AutoScanner()
