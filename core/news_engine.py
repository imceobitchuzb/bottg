from datetime import datetime, timezone

class NewsMacroEngine:
    """
    Движок мировых экономических новостей и макроэкономических факторов,
    влияющих на котировки золота (XAUUSD), с указанием времени, силы влияния
    и сценариев движения цены (BUY или SELL).
    """

    @staticmethod
    def get_upcoming_news() -> list:
        """
        Календарь ключевых мировых новостей с торговыми сценариями BUY/SELL
        """
        news = [
            {
                "id": "cpi_us",
                "time_utc": "13:30 UTC",
                "currency": "USD",
                "event": "Базовый индекс потребительских цен (CPI / Инфляция США)",
                "impact": "КРИТИЧЕСКИЙ (±200-350 pips)",
                "forecast": "3.1% YoY",
                "previous": "3.2% YoY",
                "scenarios": {
                    "buy": "Если CPI НИЖЕ прогноза (менее 3.1%) ➡️ Падение доллара DXY ➡️ ЗОЛОТО РАКЕТА ВВЕРХ (STRONG BUY 🟢)",
                    "sell": "Если CPI ВЫШЕ прогноза (более 3.1%) ➡️ Рост доллара DXY ➡️ ЗОЛОТО ДАМП ВНИЗ (STRONG SELL 🔴)"
                },
                "trading_advice": "За 10 минут до новости закрыть скальп-позиции или выставить безубыток. Входить на ретесте первой импульсной 5-минутной свечи."
            },
            {
                "id": "fomc_rate",
                "time_utc": "19:00 UTC",
                "currency": "USD",
                "event": "Решение ФРС США по процентной ставке (FOMC Rate Decision)",
                "impact": "МАКСИМАЛЬНЫЙ (±300-500 pips)",
                "forecast": "Снижение на 25 bps",
                "previous": "5.50%",
                "scenarios": {
                    "buy": "Снижение ставки или мягкая риторика Пауэлла ➡️ Девальвация доходностей трежерис ➡️ СИЛЬНЕЙШИЙ BUY ПО ЗОЛОТУ 🟢",
                    "sell": "Сохранение жесткой ДКП / пауза в снижении ➡️ Укрепление доллара ➡️ SELL ПО ЗОЛОТУ 🔴"
                },
                "trading_advice": "Торговать строго после выхода пресс-конференции ФРС через 30 минут по направлению установившегося тренда."
            },
            {
                "id": "nfp_us",
                "time_utc": "13:30 UTC (Пятница)",
                "currency": "USD",
                "event": "Non-Farm Payrolls (Количество рабочих мест вне с/х сектора США)",
                "impact": "КРИТИЧЕСКИЙ (±250-400 pips)",
                "forecast": "165K",
                "previous": "142K",
                "scenarios": {
                    "buy": "NFP ниже 150K (Слабый рынок труда) ➡️ Ожидание снижения ставок ➡️ ВЗЛЕТ ЗОЛОТА (BUY 🟢)",
                    "sell": "NFP выше 180K (Сильный рынок труда) ➡️ Рост доллара ➡️ ПАДЕНИЕ ЗОЛОТА (SELL 🔴)"
                },
                "trading_advice": "Искать снятие ликвидности с азиатских максимумов/минимумов перед разворотом."
            },
            {
                "id": "cb_gold_demand",
                "time_utc": "Постоянно",
                "currency": "GLOBAL",
                "event": "Закупки золота мировыми Центробанками (Китай PBOC, Индия, Польша)",
                "impact": "СТРАТЕГИЧЕСКИЙ (Фундаментальный)",
                "forecast": "Рекордные закупки",
                "previous": "Накопление 1000+ тонн/год",
                "scenarios": {
                    "buy": "Центробанки продолжают дедолларизацию резервов ➡️ Защита от инфляции ➡️ ГЛОБАЛЬНЫЙ BUY НА ДНЕВНОМ ГРАФИКЕ D1 🟢",
                    "sell": "Временная пауза в покупках ЦБ Китая может вызвать краткосрочную коррекцию (SELL для отката 🔴)"
                },
                "trading_advice": "Любые глубокие просадки по золоту выкупаются институциональными фондами."
            },
            {
                "id": "geopolitics",
                "time_utc": "24/7 Мониторинг",
                "currency": "GLOBAL",
                "event": "Геополитическая напряженность на Ближнем Востоке и в мире",
                "impact": "ВНЕЗАПНЫЙ ИМПУЛЬС (±100-300 pips)",
                "forecast": "Премия за риск",
                "previous": "Высокая",
                "scenarios": {
                    "buy": "Эскалация конфликтов ➡️ Бегство инвесторов в защитное золото ➡️ РЕЗКИЙ BUY 🟢",
                    "sell": "Мирные переговоры / деэскалация ➡️ Снятие военной премии ➡️ КОРРЕКЦИЯ SELL 🔴"
                },
                "trading_advice": "Использовать стоп-лосс не более 35-40 pips для защиты от резких гэпов."
            }
        ]
        return news

    @classmethod
    def get_news_summary(cls) -> dict:
        news_list = cls.get_upcoming_news()
        blackout = cls.check_news_blackout()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": "XAUUSD",
            "blackout": blackout,
            "active_drivers": [
                "1. Снижение процентных ставок мировыми ЦБ (Бычий драйвер для Золота)",
                "2. Индекс доллара DXY тестирует уровень поддержки 102.80",
                "3. Высокий спрос азиатских покупателей и дедолларизация центробанков"
            ],
            "news": news_list
        }

    @classmethod
    def check_news_blackout(cls, minutes_window: int = 15) -> dict:
        """
        Проверка 'Окна Блэкаута' (News Blackout Window).
        За 15 минут до и 15 минут после критических новостей США (13:30 UTC и 18:00-19:00 UTC)
        спреды брокеров расширяются до 50-100 пунктов. Робот блокирует вход для защиты депозита.
        """
        now = datetime.now(timezone.utc)
        current_minute_of_day = now.hour * 60 + now.minute
        weekday = now.weekday() # 0 = Понедельник, 4 = Пятница

        # Выходные дни
        if weekday in [5, 6]:
            return {
                "is_blackout": True,
                "reason": "Рынок XAUUSD закрыт на выходные",
                "advice": "Торги возобновятся в понедельник 00:00 UTC"
            }

        # Окно 1: 13:30 UTC (Американская статистика: CPI / NFP / PPI / Retail Sales) -> 13:15 - 13:45
        target_1330 = 13 * 60 + 30
        if abs(current_minute_of_day - target_1330) <= minutes_window:
            return {
                "is_blackout": True,
                "reason": "🔴 ВЫХОД МАКРОСТАТИСТИКИ США (13:30 UTC)",
                "advice": "Высокий риск раздвижения спреда! Новые входы временно заморожены."
            }

        # Окно 2: 19:00 UTC (Решение FOMC / Процентная ставка ФРС) -> 18:45 - 19:20
        target_1900 = 19 * 60
        if abs(current_minute_of_day - target_1900) <= minutes_window:
            return {
                "is_blackout": True,
                "reason": "🔴 СТАВКА ФРС / ПРЕСС-КОНФЕРЕНЦИЯ FOMC",
                "advice": "Аномальная волатильность! Защита капитала: режим ожидания."
            }

        return {
            "is_blackout": False,
            "reason": "Рыночный фон стабилен",
            "advice": "Спреды в норме, условия для входа благоприятные"
        }

news_engine = NewsMacroEngine()
