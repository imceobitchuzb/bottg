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

    @classmethod
    def analyze_smc(cls, candles: list) -> dict:
        fvgs = cls.detect_fvg(candles)
        obs = cls.detect_order_blocks(candles)
        structure = cls.detect_liquidity_and_structure(candles)

        # Вывод общего смещения SMC (Bias)
        bullish_weights = sum(1 for f in fvgs if f["type"] == "BULLISH_FVG" and not f["mitigated"]) + \
                          sum(2 for o in obs if o["type"] == "BULLISH_OB")
        bearish_weights = sum(1 for f in fvgs if f["type"] == "BEARISH_FVG" and not f["mitigated"]) + \
                          sum(2 for o in obs if o["type"] == "BEARISH_OB")

        if bullish_weights > bearish_weights + 1:
            smc_bias = "BULLISH"
        elif bearish_weights > bullish_weights + 1:
            smc_bias = "BEARISH"
        else:
            smc_bias = "NEUTRAL"

        return {
            "bias": smc_bias,
            "fvgs": fvgs,
            "order_blocks": obs,
            "structure": structure
        }

smc_engine = SMCEngine()
