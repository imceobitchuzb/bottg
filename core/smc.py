import numpy as np

class SMCEngine:
    """
    Движок концепции умных денег (Smart Money Concepts - SMC) для золота (XAUUSD).
    Находит Fair Value Gaps (FVG), Order Blocks, Liquidity Sweeps и зоны смены характера (CHoCH/BOS).
    """

    @staticmethod
    def detect_fvg(candles: list) -> list:
        """Поиск неперекрытых имбалансов (Fair Value Gaps)"""
        if len(candles) < 4:
            return []

        fvgs = []
        # Проверяем последние 30 свечей
        start_idx = max(2, len(candles) - 30)
        current_price = candles[-1]["close"]

        for i in range(start_idx, len(candles) - 1):
            c1 = candles[i - 2]
            c2 = candles[i - 1]
            c3 = candles[i]

            # Бычий FVG: Low третьей свечи выше High первой свечи
            if c3["low"] > c1["high"]:
                gap_size = round(c3["low"] - c1["high"], 2)
                if gap_size >= 0.8: # Значимый гэп для золота
                    # Проверяем, не был ли он полностью перекрыт текущей ценой
                    is_mitigated = current_price < c1["high"]
                    fvgs.append({
                        "type": "BULLISH_FVG",
                        "top": round(c3["low"], 2),
                        "bottom": round(c1["high"], 2),
                        "size": gap_size,
                        "mitigated": is_mitigated,
                        "time": c2["time"]
                    })

            # Медвежий FVG: High третьей свечи ниже Low первой свечи
            elif c3["high"] < c1["low"]:
                gap_size = round(c1["low"] - c3["high"], 2)
                if gap_size >= 0.8:
                    is_mitigated = current_price > c1["low"]
                    fvgs.append({
                        "type": "BEARISH_FVG",
                        "top": round(c1["low"], 2),
                        "bottom": round(c3["high"], 2),
                        "size": gap_size,
                        "mitigated": is_mitigated,
                        "time": c2["time"]
                    })

        return fvgs[-5:] # возвращаем 5 самых свежих

    @staticmethod
    def detect_order_blocks(candles: list) -> list:
        """Поиск ордерблоков (Order Blocks) институциональных игроков"""
        if len(candles) < 10:
            return []

        obs = []
        closes = [c["close"] for c in candles]
        opens = [c["open"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        # Ищем резкие импульсные движения от противоположных свечей
        for i in range(len(candles) - 15, len(candles) - 2):
            if i < 2:
                continue

            # Бычий ордерблок: медвежья свеча перед сильным ростом
            is_bearish_candle = closes[i] < opens[i]
            strong_expansion_up = (closes[i+1] - opens[i+1] > 3.5) or (closes[i+2] - opens[i] > 6.0)
            if is_bearish_candle and strong_expansion_up:
                obs.append({
                    "type": "BULLISH_OB",
                    "top": round(highs[i], 2),
                    "bottom": round(lows[i], 2),
                    "strength": "HIGH",
                    "time": candles[i]["time"]
                })

            # Медвежий ордерблок: бычья свеча перед сильным падением
            is_bullish_candle = closes[i] > opens[i]
            strong_expansion_down = (opens[i+1] - closes[i+1] > 3.5) or (opens[i] - closes[i+2] > 6.0)
            if is_bullish_candle and strong_expansion_down:
                obs.append({
                    "type": "BEARISH_OB",
                    "top": round(highs[i], 2),
                    "bottom": round(lows[i], 2),
                    "strength": "HIGH",
                    "time": candles[i]["time"]
                })

        return obs[-4:]

    @staticmethod
    def detect_liquidity_and_structure(candles: list) -> dict:
        """Детекция уровней ликвидности (BSL / SSL) и смены структуры (BOS / CHoCH)"""
        if len(candles) < 20:
            return {"structure": "CONSOLIDATION", "bsl": 2745.0, "ssl": 2720.0, "sweeps": []}

        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        current_price = candles[-1]["close"]

        # Локальные свинги
        swing_high = max(highs[-20:-2])
        swing_low = min(lows[-20:-2])

        # Детекция свипа ликвидности на текущих свечах
        sweeps = []
        if candles[-1]["high"] > swing_high and candles[-1]["close"] < swing_high:
            sweeps.append({"type": "LIQUIDITY_SWEEP_BUY", "level": swing_high, "bias": "BEARISH_REVERSAL"})
        if candles[-1]["low"] < swing_low and candles[-1]["close"] > swing_low:
            sweeps.append({"type": "LIQUIDITY_SWEEP_SELL", "level": swing_low, "bias": "BULLISH_REVERSAL"})

        # Определение структуры
        last_high = candles[-1]["high"]
        last_low = candles[-1]["low"]
        if last_high > swing_high and current_price > swing_high:
            structure = "BOS_BULLISH (Слом сопротивления)"
        elif last_low < swing_low and current_price < swing_low:
            structure = "BOS_BEARISH (Слом поддержки)"
        else:
            structure = "RANGE_BOUND (Торговля внутри диапазона)"

        return {
            "structure": structure,
            "bsl_level": round(swing_high, 2),
            "ssl_level": round(swing_low, 2),
            "sweeps": sweeps
        }

    @staticmethod
    def calculate_dealing_range(candles: list) -> dict:
        """
        Расчет институционального диапазона (Dealing Range) и Эквилибриума (50% Equilibrium).
        Определяет зоны Premium (дорого / только продажи) и Discount (дешево / только покупки).
        """
        if len(candles) < 15:
            return {
                "range_high": 0.0,
                "range_low": 0.0,
                "equilibrium": 0.0,
                "position_pct": 50.0,
                "zone": "EQUILIBRIUM",
                "zone_ru": "Эквилибриум (50%)",
                "bias": "NEUTRAL"
            }

        period = min(len(candles), 40)
        highs = [c["high"] for c in candles[-period:]]
        lows = [c["low"] for c in candles[-period:]]
        current_price = candles[-1]["close"]

        range_high = max(highs)
        range_low = min(lows)
        range_span = range_high - range_low

        if range_span <= 0:
            range_span = 1.0

        equilibrium = round((range_high + range_low) / 2.0, 2)
        pos_pct = round(((current_price - range_low) / range_span) * 100.0, 1)

        if pos_pct < 25.0:
            zone = "DEEP_DISCOUNT"
            zone_ru = "Глубокий Дисконт (<25%) 🟢"
            bias = "STRONG_BUY_ZONE"
        elif pos_pct < 48.0:
            zone = "DISCOUNT"
            zone_ru = "Зона Дисконта (Покупки) 🟢"
            bias = "BUY_ZONE"
        elif pos_pct <= 52.0:
            zone = "EQUILIBRIUM"
            zone_ru = "Баланс / Эквилибриум (50%) ⚪"
            bias = "NEUTRAL"
        elif pos_pct <= 75.0:
            zone = "PREMIUM"
            zone_ru = "Зона Премиума (Продажи) 🔴"
            bias = "SELL_ZONE"
        else:
            zone = "DEEP_PREMIUM"
            zone_ru = "Глубокий Премиум (>75%) 🔴"
            bias = "STRONG_SELL_ZONE"

        return {
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
            "equilibrium": equilibrium,
            "position_pct": pos_pct,
            "zone": zone,
            "zone_ru": zone_ru,
            "bias": bias
        }

    @staticmethod
    def detect_session_sweeps(candles: list, utc_hour: int = 12) -> dict:
        """
        Детекция сессионной ликвидности и Judas Swing (манипуляции на открытии Лондона / Нью-Йорка).
        Азия: 00:00 - 06:00 UTC
        Лондон: 07:00 - 10:00 UTC
        Нью-Йорк: 12:00 - 15:00 UTC
        """
        if len(candles) < 24:
            return {"active_session": "LONDON", "judas_swing": None, "session_tag": "Active"}

        # Определяем текущую торговую сессию
        if 0 <= utc_hour < 7:
            session = "ASIA_ACCUMULATION"
            session_ru = "🌏 Азия (Накопление ликвидности)"
            is_killzone = False
        elif 7 <= utc_hour < 11:
            session = "LONDON_KILLZONE"
            session_ru = "🇬🇧 Лондонский Kill Zone (Атака ликвидности)"
            is_killzone = True
        elif 11 <= utc_hour < 12:
            session = "LONDON_LUNCH"
            session_ru = "☕ Лондонский ланч (Пауза)"
            is_killzone = False
        elif 12 <= utc_hour < 16:
            session = "NEW_YORK_KILLZONE"
            session_ru = "🇺🇸 Нью-Йорк Kill Zone (Максимальный объем)"
            is_killzone = True
        elif 16 <= utc_hour < 20:
            session = "NY_PM_SESSION"
            session_ru = "🌇 Закрытие Нью-Йорка / Ребалансировка"
            is_killzone = False
        else:
            session = "OFF_HOURS"
            session_ru = "🌙 Межсессионная пауза"
            is_killzone = False

        # Определение границ азиатской сессии из свечей
        highs = [c["high"] for c in candles[-24:]]
        lows = [c["low"] for c in candles[-24:]]
        current_candle = candles[-1]
        current_high = current_candle["high"]
        current_low = current_candle["low"]
        current_close = current_candle["close"]

        # Ищем Judas Swing на Лондоне или NY: снятие экстремума и закрытие обратно внутри
        judas = None
        swing_h = max(highs[:-2]) if len(highs) > 2 else current_high
        swing_l = min(lows[:-2]) if len(lows) > 2 else current_low

        if current_high > swing_h and current_close < swing_h:
            judas = {
                "type": "BEARISH_JUDAS_SWING",
                "text": "Манипуляция: сняли хай сессии и закрылись ниже (Ложный пробой)",
                "bias": "SELL"
            }
        elif current_low < swing_l and current_close > swing_l:
            judas = {
                "type": "BULLISH_JUDAS_SWING",
                "text": "Манипуляция: сняли лой сессии и закрылись выше (Ложный пробой)",
                "bias": "BUY"
            }

        return {
            "active_session": session,
            "session_ru": session_ru,
            "is_killzone": is_killzone,
            "judas_swing": judas
        }

    @classmethod
    def analyze_smc(cls, candles: list, utc_hour: int = 12) -> dict:
        fvgs = cls.detect_fvg(candles)
        obs = cls.detect_order_blocks(candles)
        structure = cls.detect_liquidity_and_structure(candles)
        dealing_range = cls.calculate_dealing_range(candles)
        session_info = cls.detect_session_sweeps(candles, utc_hour)

        # Вывод общего смещения SMC (Bias) с учетом диапазона и блоков
        bullish_score = sum(1 for f in fvgs if f["type"] == "BULLISH_FVG" and not f["mitigated"]) + \
                        sum(2 for o in obs if o["type"] == "BULLISH_OB")
        bearish_score = sum(1 for f in fvgs if f["type"] == "BEARISH_FVG" and not f["mitigated"]) + \
                        sum(2 for o in obs if o["type"] == "BEARISH_OB")

        if dealing_range["zone"] in ["DISCOUNT", "DEEP_DISCOUNT"]:
            bullish_score += 2
        elif dealing_range["zone"] in ["PREMIUM", "DEEP_PREMIUM"]:
            bearish_score += 2

        if session_info.get("judas_swing"):
            if session_info["judas_swing"]["bias"] == "BUY":
                bullish_score += 3
            elif session_info["judas_swing"]["bias"] == "SELL":
                bearish_score += 3

        if bullish_score > bearish_score + 1:
            smc_bias = "BULLISH"
        elif bearish_score > bullish_score + 1:
            smc_bias = "BEARISH"
        else:
            smc_bias = "NEUTRAL"

        return {
            "bias": smc_bias,
            "fvgs": fvgs,
            "order_blocks": obs,
            "structure": structure,
            "dealing_range": dealing_range,
            "session": session_info
        }

smc_engine = SMCEngine()

