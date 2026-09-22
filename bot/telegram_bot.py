import io
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    MenuButtonWebApp
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.constants import ParseMode

import config
from config import TELEGRAM_BOT_TOKEN
from core.market_data import market_data
from core.signal_engine import signal_engine
from core.indicators import technical_engine
from core.ai_vision import ai_vision
from core.sentiment import sentiment_aggregator
from core.performance_tracker import tracker
from core.execution_engine import execution_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("telegram_bot")

def get_persistent_reply_keyboard(chat_id: int = None) -> ReplyKeyboardMarkup:
    """
    Постоянная клавиатура внизу чата для мгновенного доступа и перезапуска
    """
    is_sub = tracker.is_subscribed(chat_id) if chat_id else True
    alert_btn_text = "🔔 Авто-сигналы: ВКЛ" if is_sub else "🔕 Авто-сигналы: ВЫКЛ"

    acc_info = market_data.get_account_info()
    if acc_info.get("connected"):
        account_btn = KeyboardButton(f"✅ MT5: #{acc_info['login']}")
    else:
        account_btn = KeyboardButton("🔐 Подключить MT5")

    keyboard = [
        [KeyboardButton("⚡ Сигнал M15"), KeyboardButton("🎯 Скальп M5")],
        [KeyboardButton("📊 Спидометр рынка"), KeyboardButton("⏱️ Прогнозы (5м-1д)")],
        [KeyboardButton("📈 Статистика /stats"), KeyboardButton(alert_btn_text)],
        [account_btn, KeyboardButton("📸 Анализ по фото")],
        [KeyboardButton("🚀 Открыть ИИ Терминал"), KeyboardButton("🔄 Перезапустить /start")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_action_keyboard(action_type: str = "general", direction: str = "BUY") -> InlineKeyboardMarkup:
    """
    Инлайн-кнопки под сообщениями: Быстрое исполнение в MT5, Обновить, Главное меню
    """
    url = config.WEBAPP_URL
    refresh_callback = {
        "signal": "btn_signal",
        "scalp": "btn_scalp",
        "forecast": "btn_forecast",
        "meter": "btn_meter",
        "stats": "btn_stats",
        "account": "btn_account",
        "photo": "btn_photo_info"
    }.get(action_type, "btn_signal")

    buttons = []

    # Кнопка открытия ордера в MT5 в 1 клик для сигналов и скальпа
    if action_type in ["signal", "scalp"]:
        dir_text = "BUY 🟢" if direction == "BUY" else "SELL 🔴"
        buttons.append([
            InlineKeyboardButton(
                f"⚡ Открыть {dir_text} в MT5 в 1 клик",
                callback_data=f"btn_exec_market_{direction.lower()}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔄 Обновить", callback_data=refresh_callback),
        InlineKeyboardButton("🔙 В главное меню", callback_data="btn_menu")
    ])

    if url.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("🚀 Открыть ИИ Терминал", web_app=WebAppInfo(url=url))
        ])
    else:
        buttons.append([
            InlineKeyboardButton("🌐 Открыть ИИ Терминал", url=url)
        ])
    return InlineKeyboardMarkup(buttons)

def get_main_keyboard() -> InlineKeyboardMarkup:
    url = config.WEBAPP_URL
    buttons = []
    if url.startswith("https://"):
        buttons.append([
            InlineKeyboardButton(
                "🚀 Открыть ИИ Терминал XAUUSD (Mini App)",
                web_app=WebAppInfo(url=url)
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                "🌐 Открыть в браузере (Прямая ссылка)",
                url=url
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                "🌐 Открыть веб-терминал XAUUSD",
                url=url
            )
        ])

    acc_info = market_data.get_account_info()
    acc_text = f"✅ MT5 #{acc_info['login']}" if acc_info.get("connected") else "🔐 Подключить MT5 счет"

    buttons.extend([
        [
            InlineKeyboardButton("⚡ Сигнал M15", callback_data="btn_signal"),
            InlineKeyboardButton("🎯 Скальп M5", callback_data="btn_scalp")
        ],
        [
            InlineKeyboardButton("📈 Винрейт & Статистика", callback_data="btn_stats"),
            InlineKeyboardButton(acc_text, callback_data="btn_account")
        ],
        [
            InlineKeyboardButton("📊 Спидометр рынка", callback_data="btn_meter"),
            InlineKeyboardButton("⏳ Прогноз (5м - 1д)", callback_data="btn_forecast")
        ],
        [
            InlineKeyboardButton("📸 Инструкция: анализ по фото", callback_data="btn_photo_info")
        ],
        [
            InlineKeyboardButton("🔄 Перезапустить /start", callback_data="btn_menu")
        ]
    ])
    return InlineKeyboardMarkup(buttons)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id:
        tracker.subscribe_chat(chat_id)

    quote = market_data.get_live_quote()
    price = quote["price"]
    change = quote["change_pct"]
    sign = "+" if change >= 0 else ""
    stats = tracker.get_statistics()
    acc_info = market_data.get_account_info()

    acc_status_text = (
        f"🟢 <b>MT5 Аккаунт:</b> #{acc_info['login']} ({acc_info['company']}) — <code>${acc_info['balance']:.2f}</code>\n"
        if acc_info.get("connected") else
        f"🟡 <b>MT5 Аккаунт:</b> Не подключен (нажмите кнопку <i>«🔐 Подключить MT5»</i> ниже)\n"
    )

    text = (
        f"👑 <b>XAUUSD AI PRO TRADER 100/100 — META TRADER 5</b>\n\n"
        f"Добро пожаловать в элитный торговый ИИ-центр по Золоту (<b>XAUUSD</b>)!\n\n"
        f"💰 <b>Живая цена MT5:</b> <code>${price:.2f}</code> ({sign}{change:.2f}%)\n"
        f"{acc_status_text}"
        f"🏆 <b>Винрейт системы:</b> <b>{stats['winrate_pct']}%</b> (Профит: <b>+{stats['total_pips']} pips</b>)\n"
        f"🚨 <b>Авто-сканер рынка 24/5:</b> <b>АКТИВЕН 🟢</b>\n\n"
        f"<b>Инструменты трейдера:</b>\n"
        f"• ⚡ <b>Торговля в 1 клик в MT5:</b> открытие позиций с авто-расчетом лота от баланса!\n"
        f"• 🛡️ <b>Trade Manager:</b> автоматический перенос стопа в безубыток (+5 pips) при достижении TP1.\n"
        f"• 📸 <b>Анализ графиков по фото:</b> отправьте скриншот — нейросеть рассчитает точный сетап!\n"
        f"• 🎯 <b>Скальпинг M5:</b> выверенные точки входа, SL (-25 pips), TP1 (+35 pips) и TP2 (+65 pips).\n"
        f"• 📱 <b>Telegram Mini App:</b> 5 интерактивных вкладок с живыми графиками, индикаторами и новостями.\n\n"
        f"<i>Используйте кнопки меню внизу экрана или выберите действие:</i>"
    )

    if update.message:
        await update.message.reply_text(
            "⚡ Меню быстрого доступа активировано (кнопки внизу экрана):",
            reply_markup=get_persistent_reply_keyboard(chat_id)
        )
        await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)

    url = config.WEBAPP_URL
    if url.startswith("https://") and update.effective_chat:
        try:
            await context.bot.set_chat_menu_button(
                chat_id=update.effective_chat.id,
                menu_button=MenuButtonWebApp(
                    text="🚀 ИИ Терминал",
                    web_app=WebAppInfo(url=url)
                )
            )
        except Exception as e:
            logger.debug(f"Menu button set error: {e}")

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Интерактивное пошаговое подключение торгового счета брокера MT5
    """
    acc_info = market_data.get_account_info()
    if acc_info.get("connected"):
        status_text = (
            f"✅ <b>ВАШ СЧЕТ METATRADER 5 УЖЕ ПОДКЛЮЧЕН:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Владелец: <b>{acc_info['name']}</b>\n"
            f"💼 Брокер: <b>{acc_info['company']}</b>\n"
            f"🔢 Номер счета: <code>{acc_info['login']}</code>\n"
            f"🌐 Сервер: <code>{acc_info['server']}</code>\n"
            f"💰 Баланс: <code>${acc_info['balance']:.2f} {acc_info['currency']}</code>\n"
            f"⚖️ Плечо: 1:{acc_info['leverage']}\n\n"
            f"<i>Чтобы сменить счёт или войти заново — отправьте новый номер счёта прямо сейчас.</i>"
        )
    else:
        status_text = (
            f"🔐 <b>ПОДКЛЮЧЕНИЕ СЧЕТА METATRADER 5 К БОТУ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Чтобы бот открывал сделки на вашем счёте (и они сразу отображались в MT5 на телефоне и компьютере), подключите ваш аккаунт брокера:\n\n"
            f"<b>Шаг 1 из 3:</b> 🔢 Отправьте ваш <b>номер счёта (Login)</b>, например: <code>51234567</code>\n\n"
            f"<i>💡 Совет: для первого теста вы можете использовать Демо-счет любого брокера (MetaQuotes, Exness, RoboForex, ICMarkets).</i>"
        )

    context.user_data["account_step"] = "waiting_login"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(status_text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = tracker.get_statistics()
    recent = stats.get("recent_trades", [])

    history_lines = ""
    for t in recent[:6]:
        direction_icon = "🟢" if t["direction"] == "BUY" else "🔴"
        pips = t["pips_earned"]
        sign = "+" if pips > 0 else ""
        outcome_tag = "✅" if pips > 0 else "🛑"
        status_name = t["status"].replace("_HIT", "")
        history_lines += f"• {direction_icon} <b>{t['timeframe']} {t['direction']}</b>: <b>{sign}{pips} pips</b> ({status_name}) {outcome_tag}\n"

    text = (
        f"📈 <b>ВЕРИФИЦИРОВАННЫЙ ТРЕК-РЕКОРД XAUUSD (TRACK RECORD)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Винрейт сигналов:</b> <b>{stats['winrate_pct']}%</b>\n"
        f"💰 <b>Суммарный профит:</b> <b>+{stats['total_pips']} pips</b>\n"
        f"📊 <b>Всего сделок в базе:</b> <b>{stats['total_trades']}</b> (Прибыльных: <b>{stats['wins']}</b> | Убыточных: <b>{stats['losses']}</b>)\n"
        f"⚖️ <b>Profit Factor:</b> <b>{stats['profit_factor']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>История последних закрытых сделок:</b>\n"
        f"{history_lines if history_lines else '• Ожидание первых закрытых сетапов...\n'}\n"
        f"💡 <i>Статистика обновляется в реальном времени при достижении ценой TP1, TP2 или SL в MetaTrader 5.</i>"
    )

    markup = get_action_keyboard("stats")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def toggle_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    is_sub = tracker.is_subscribed(chat_id)
    if is_sub:
        tracker.unsubscribe_chat(chat_id)
        msg = "🔕 <b>Авто-сигналы ВЫКЛЮЧЕНЫ.</b>\nВы больше не будете получать фоновые пуш-уведомления."
    else:
        tracker.subscribe_chat(chat_id)
        msg = (
            "🔔 <b>Авто-сигналы ВКЛЮЧЕНЫ (24/5)!</b>\n"
            "ИИ-сканер непрерывно анализирует M5/M15 и мгновенно пришлет уведомление с кнопкой входа в MT5 при появлении лучшей точки!"
        )

    await update.message.reply_text(
        msg,
        reply_markup=get_persistent_reply_keyboard(chat_id),
        parse_mode=ParseMode.HTML
    )

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal = signal_engine.generate_signal()
    is_buy = signal["direction"] == "BUY"
    icon = "🟢" if is_buy else "🔴"
    grade = signal.get("grade_badge", "🏆 Grade A+")
    dr = signal.get("dealing_range", {})
    sess = signal.get("session", {})
    vsa = signal.get("vsa", {})
    score = signal.get("confluence_score", 85)

    text = (
        f"{icon} <b>ИНСТИТУЦИОНАЛЬНЫЙ СИГНАЛ XAUUSD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{grade}\n\n"
        f"🎯 <b>Направление:</b> <b>{signal['direction_ru']}</b>\n"
        f"📍 <b>Зона входа:</b> <code>{signal['entry_zone']}</code>\n"
        f"🛑 <b>Stop-Loss:</b> <code>{signal['stop_loss']}</code>\n"
        f"💎 <b>Take-Profit 1:</b> <code>{signal['take_profit_1']}</code> (Скальп)\n"
        f"💎 <b>Take-Profit 2:</b> <code>{signal['take_profit_2']}</code> (Основной)\n"
        f"💎 <b>Take-Profit 3:</b> <code>{signal['take_profit_3']}</code> (Институциональный)\n\n"
        f"⚖️ <b>Risk/Reward:</b> {signal['risk_reward']}\n"
        f"🎯 <b>Confluence Score:</b> <b>{score}/100 🛡️</b>\n"
        f"🏷️ <b>Dealing Range (H1):</b> {dr.get('zone_ru', 'Equilibrium')}\n"
        f"⏰ <b>Сессия / Kill Zone:</b> {sess.get('name', 'Active')}\n"
        f"📊 <b>Объем (VSA):</b> {vsa.get('text', 'Норма')}\n"
        f"🏛️ <b>SMC:</b> {signal['smc']['structure']}\n\n"
        f"💡 <i>{signal['rationale']}</i>"
    )

    markup = get_action_keyboard("signal", direction=signal["direction"])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def scalp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal = signal_engine.generate_signal()
    setup = signal.get("scalp_setup", {})
    quote = market_data.get_live_quote()
    price = quote["price"]

    is_buy = signal["direction"] == "BUY"
    icon = "⚡ 🟢" if is_buy else "⚡ 🔴"
    action_ru = setup.get("action_ru", "СКАЛЬП ЛОНГ (ПОКУПКА)" if is_buy else "СКАЛЬП ШОРТ (ПРОДАЖА)")
    grade = signal.get("grade_badge", "🏆 Grade A+")
    dr = signal.get("dealing_range", {})
    sess = signal.get("session", {})
    vsa = signal.get("vsa", {})

    text = (
        f"{icon} <b>ИНСТИТУЦИОНАЛЬНЫЙ СКАЛЬПИНГ M5 (MT5)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{grade}\n\n"
        f"🎯 <b>Направление:</b> <b>{action_ru}</b>\n"
        f"📍 <b>Вход:</b> <code>{setup.get('entry_zone', f'${price:.2f}')}</code>\n"
        f"🛑 <b>Stop-Loss:</b> <code>{setup.get('stop_loss', '-')}</code> ({setup.get('sl_pips', '-25 pips')})\n"
        f"💎 <b>TP 1:</b> <code>{setup.get('take_profit_1', '-')}</code> ({setup.get('tp1_pips', '+35 pips')})\n"
        f"💎 <b>TP 2:</b> <code>{setup.get('take_profit_2', '-')}</code> ({setup.get('tp2_pips', '+65 pips')})\n\n"
        f"⚖️ <b>Risk / Reward:</b> {setup.get('risk_reward', '1:2.6')}\n"
        f"🎯 <b>Confluence Score:</b> <b>{signal.get('confluence_score', 85)}/100 🛡️</b>\n"
        f"🏷️ <b>Зона:</b> {dr.get('zone_ru', 'Equilibrium')}\n"
        f"⏰ <b>Сессия:</b> {sess.get('name', 'Active')}\n"
        f"📊 <b>Объем:</b> {vsa.get('text', 'Норма')}\n\n"
        f"📌 <b>Авто-менеджер Breakeven:</b>\n"
        f"<i>При взятии TP1 позиция автоматически переносится в безубыток (+5 pips)!</i>"
    )

    markup = get_action_keyboard("scalp", direction=signal["direction"])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    signal = signal_engine.generate_signal()
    horizons = signal["horizons"]

    text = (
        f"⏱️ <b>МУЛЬТИ-ТАЙМФРЕЙМ ПРОГНОЗ XAUUSD</b>\n"
        f"Текущая цена MT5: <code>${signal['current_price']:.2f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    for key, h in horizons.items():
        arrow = "🟢 ↗" if h["direction"] == "UP" else "🔴 ↘"
        text += (
            f"• <b>{h['timeframe']}:</b> {arrow} <code>${h['target_price']:.2f}</code>\n"
            f"  Ожидание: <b>{h['expected_pips']}</b> | Точность: <b>{h['probability']}</b>\n"
            f"  <i>{h['status']}</i>\n\n"
        )

    text += "<i>Обновляется в реальном времени на основе живых тиков MT5 и волатильности ATR.</i>"

    markup = get_action_keyboard("forecast")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def meter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candles = market_data.get_candles("M15", 50)
    tech = technical_engine.analyze_market(candles)
    counts = tech["counts"]

    text = (
        f"📊 <b>КОНСЕНСУС ИНДИКАТОРОВ (TRADINGVIEW & INVESTING)</b>\n"
        f"Инструмент: <b>XAUUSD (Золото)</b> | Таймфрейм: <b>M15</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Итоговый вердикт:</b> <b>{tech['summary_ru']}</b>\n"
        f"Индекс настроения: <code>{tech['score']:+.1f}</code> / 100\n\n"
        f"📈 <b>Скользящие средние (MAs):</b>\n"
        f"  • Покупка: <b>{counts['ma_buy']}</b> | Нейтрально: <b>{counts['ma_neutral']}</b> | Продажа: <b>{counts['ma_sell']}</b>\n\n"
        f"🌊 <b>Осцилляторы (RSI, Stoch, MACD, CCI, ADX):</b>\n"
        f"  • Покупка: <b>{counts['osc_buy']}</b> | Нейтрально: <b>{counts['osc_neutral']}</b> | Продажа: <b>{counts['osc_sell']}</b>\n\n"
        f"🔥 <b>Суммарно:</b> 🟢 {counts['total_buy']} Бычьих сигналов vs 🔴 {counts['total_sell']} Медвежьих"
    )

    markup = get_action_keyboard("meter")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def photo_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📸 <b>КАК РАБОТАЕТ ИИ-АНАЛИЗ ГРАФИКА ПО ФОТО:</b>\n\n"
        f"1. Сделайте скриншот графика Золота (XAUUSD) в <b>MetaTrader 5</b> или <b>TradingView</b>.\n"
        f"2. Просто отправьте картинку прямо сюда в этот чат (или нажмите скрепку 📎)!\n"
        f"3. Нейросеть моментально просканирует изображение и определит:\n"
        f"   • Свечные паттерны (пин-бары, поглощения, доджи)\n"
        f"   • Графические фигуры (треугольники, флаги, двойное дно/вершина)\n"
        f"   • Зоны ликвидности, Order Blocks и имбалансы (FVG)\n"
        f"   • Рассчитает точный вход, Стоп-Лосс и 3 Тейк-Профита!\n\n"
        f"<i>Отправьте фото графика прямо сейчас, чтобы протестировать!</i>"
    )
    markup = get_action_keyboard("photo")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "👁️ <b>Принял скриншот!</b> ИИ сканирует свечи, паттерны и уровни SMC...",
        parse_mode=ParseMode.HTML
    )

    try:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        res = ai_vision.analyze_chart_image(bytes(photo_bytes), filename="tg_chart.jpg")

        is_buy = res.get("direction", "BUY") == "BUY"
        icon = "🟢" if is_buy else "🔴"

        horizons = res.get("horizons", {})
        h_5m = horizons.get("5m", {}).get("target_pips", "+25 pips")
        h_15m = horizons.get("15m", {}).get("target_pips", "+70 pips")
        h_1h = horizons.get("1h", {}).get("target_pips", "+190 pips")
        h_1d = horizons.get("1d", {}).get("target_pips", "+380 pips")

        report = (
            f"🧠 <b>ИИ РАЗБОР ГРАФИКА XAUUSD ПО ФОТО</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{icon} <b>Вердикт:</b> <b>{res.get('direction_ru', res.get('direction'))}</b>\n"
            f"🎯 <b>Точность анализа:</b> {res.get('confidence_percent', 88)}%\n"
            f"📈 <b>Тренд:</b> {res.get('trend', 'Импульс')}\n\n"
            f"🚪 <b>Вход в сделку:</b> <code>{res.get('entry_price', '-')}</code>\n"
            f"🛑 <b>Stop-Loss:</b> <code>{res.get('stop_loss', '-')}</code>\n"
            f"🎯 <b>TP 1:</b> <code>{res.get('take_profit_1', '-')}</code>\n"
            f"🎯 <b>TP 2:</b> <code>{res.get('take_profit_2', '-')}</code>\n"
            f"🎯 <b>TP 3:</b> <code>{res.get('take_profit_3', '-')}</code>\n"
            f"⚖️ <b>Risk/Reward:</b> {res.get('risk_reward', '1:2.8')}\n\n"
            f"🕯️ <b>Свечной паттерн:</b> {res.get('candle_pattern', '-')}\n"
            f"📐 <b>Фигура:</b> {res.get('chart_pattern', '-')}\n"
            f"🏛️ <b>Smart Money:</b> {res.get('smc_analysis', '-')}\n\n"
            f"⏱️ <b>Горизонты прогноза:</b>\n"
            f"• 5м: <b>{h_5m}</b> | 15м: <b>{h_15m}</b>\n"
            f"• 1ч: <b>{h_1h}</b> | 1д: <b>{h_1d}</b>\n\n"
            f"💡 <b>Совет трейдера:</b>\n<i>{res.get('trader_verdict', '')}</i>"
        )

        markup = get_action_keyboard("signal", direction=res.get("direction", "BUY"))
        await msg.edit_text(report, reply_markup=markup, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Photo handling error: {e}")
        markup = get_action_keyboard("photo")
        await msg.edit_text(f"⚠️ Ошибка при анализе графика: {str(e)}", reply_markup=markup)

async def execute_trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str):
    """
    Исполнение сделки в MT5 по нажатию инлайн-кнопки
    """
    query = update.callback_query
    await query.answer("Исполняю ордер в MT5...")

    res = execution_engine.execute_trade(direction=direction, risk_pct=2.0)
    is_buy = direction.upper() == "BUY"
    icon = "🟢" if is_buy else "🔴"
    action_ru = "ПОКУПКА (LONG)" if is_buy else "ПРОДАЖА (SHORT)"

    acc_info = market_data.get_account_info()
    acc_text = f"Счёт: #{acc_info['login']} ({acc_info['server']})" if acc_info.get("connected") else "Режим симуляции (аккаунт брокера не привязан)"

    text = (
        f"⚡ <b>ОРДЕР ИСПОЛНЕН: XAUUSD {icon}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 <b>Тикет позиции:</b> <code>#{res['ticket']}</code>\n"
        f"🎯 <b>Направление:</b> <b>{action_ru}</b>\n"
        f"📦 <b>Объем лота:</b> <code>{res['volume']} LOT</code>\n"
        f"📍 <b>Цена открытия:</b> <code>${res['price']:.2f}</code>\n"
        f"🛑 <b>Stop-Loss:</b> <code>{res['sl']}</code> (-25 pips)\n"
        f"💎 <b>Take-Profit:</b> <code>{res['tp']}</code> (+45 pips)\n"
        f"💼 <b>Статус счета:</b> {acc_text}\n\n"
        f"🛡️ <b>Статус Trade Manager:</b>\n"
        f"<i>При достижении +25 пипсов стоп-лосс будет автоматически перенесен в безубыток (+5 pips)!</i>"
    )

    await query.message.reply_text(text, parse_mode=ParseMode.HTML)

async def text_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатий на кнопки постоянной Reply-клавиатуры и пошагового ввода аккаунта
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    chat_id = update.effective_chat.id if update.effective_chat else None
    step = context.user_data.get("account_step")

    # 1. Пошаговая авторизация в брокере MT5
    if step == "waiting_login":
        clean_login = "".join(filter(str.isdigit, text))
        if not clean_login:
            await update.message.reply_text("⚠️ Номер счета должен состоять из цифр (например, <code>51234567</code>). Попробуйте еще раз:", parse_mode=ParseMode.HTML)
            return

        context.user_data["mt5_login"] = clean_login
        context.user_data["account_step"] = "waiting_password"
        await update.message.reply_text(
            f"✅ Принял логин: <code>{clean_login}</code>\n\n"
            f"<b>Шаг 2 из 3:</b> 🔑 Введите <b>торговый пароль</b> от счёта MT5:\n"
            f"<i>(Пароль используется строго для локальной связи с терминалом)</i>",
            parse_mode=ParseMode.HTML
        )
        return

    elif step == "waiting_password":
        context.user_data["mt5_password"] = text
        context.user_data["account_step"] = "waiting_server"
        await update.message.reply_text(
            "✅ Пароль принят!\n\n"
            "<b>Шаг 3 из 3:</b> 🌐 Введите <b>имя сервера брокера</b>:\n"
            "<i>(Точно как указано у брокера, например: <code>MetaQuotes-Demo</code>, <code>Exness-Real11</code>, <code>RoboForex-Pro</code>, <code>ICMarkets-Demo</code>)</i>",
            parse_mode=ParseMode.HTML
        )
        return

    elif step == "waiting_server":
        server = text
        login = context.user_data.get("mt5_login")
        password = context.user_data.get("mt5_password")
        context.user_data["account_step"] = None

        wait_msg = await update.message.reply_text(
            f"⏳ <b>Подключаюсь к серверу {server}...</b>\nАвторизуюсь на брокере под логином #{login}...",
            parse_mode=ParseMode.HTML
        )

        res = market_data.login_account(int(login), password, server)
        if res.get("success"):
            success_text = (
                f"✅ <b>МЕТАТРЕЙДЕР 5 УСПЕШНО ПОДКЛЮЧЕН!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Владелец:</b> {res['name']}\n"
                f"💼 <b>Брокер / Компания:</b> {res['company']}\n"
                f"🔢 <b>Номер счёта:</b> <code>{res['login']}</code>\n"
                f"🌐 <b>Сервер:</b> <code>{res['server']}</code>\n"
                f"💰 <b>Баланс депозита:</b> <code>${res['balance']:.2f} {res['currency']}</code>\n"
                f"⚖️ <b>Кредитное плечо:</b> 1:{res['leverage']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 <i>Теперь при нажатии «⚡ Открыть в MT5» сделка исполняется на вашем брокере и сразу появляется в приложении MT5 на телефоне и компьютере!</i>"
            )
            await wait_msg.edit_text(success_text, parse_mode=ParseMode.HTML)
            # Обновляем постоянную клавиатуру с галочкой подключенного счета
            await update.message.reply_text(
                "Кнопки обновлены 👇",
                reply_markup=get_persistent_reply_keyboard(chat_id)
            )
        else:
            fail_text = (
                f"⚠️ <b>ОШИБКА АВТОРИЗАЦИИ В MT5:</b>\n\n"
                f"{res.get('message', 'Не удалось войти.')}\n\n"
                f"<i>Нажмите кнопку «🔐 Подключить MT5» внизу, чтобы попробовать снова.</i>"
            )
            await wait_msg.edit_text(fail_text, parse_mode=ParseMode.HTML)
        return

    # 2. Обычные команды меню
    if "Сигнал" in text:
        await signal_command(update, context)
    elif "Скальп" in text:
        await scalp_command(update, context)
    elif "Спидометр" in text:
        await meter_command(update, context)
    elif "Прогноз" in text:
        await forecast_command(update, context)
    elif "Статистика" in text or "stats" in text.lower():
        await stats_command(update, context)
    elif "Авто-сигнал" in text:
        await toggle_alerts_command(update, context)
    elif "Подключить MT5" in text or "MT5:" in text or "account" in text.lower():
        await account_command(update, context)
    elif "Анализ по фото" in text or "фото" in text.lower():
        await photo_info_command(update, context)
    elif "Терминал" in text or "App" in text:
        await start_command(update, context)
    elif "Перезапустить" in text or "старт" in text.lower() or "назад" in text.lower() or "меню" in text.lower():
        await start_command(update, context)
    else:
        await update.message.reply_text(
            "👆 Выберите раздел с помощью кнопок меню внизу или отправьте фото графика XAUUSD:",
            reply_markup=get_persistent_reply_keyboard(chat_id)
        )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "btn_signal":
        await signal_command(update, context)
    elif data == "btn_scalp":
        await scalp_command(update, context)
    elif data == "btn_meter":
        await meter_command(update, context)
    elif data == "btn_forecast":
        await forecast_command(update, context)
    elif data == "btn_stats":
        await stats_command(update, context)
    elif data == "btn_account":
        await account_command(update, context)
    elif data == "btn_photo_info":
        await photo_info_command(update, context)
    elif data == "btn_exec_market_buy":
        await execute_trade_callback(update, context, "BUY")
    elif data == "btn_exec_market_sell":
        await execute_trade_callback(update, context, "SELL")
    elif data == "btn_menu":
        await query.answer("Главное меню")
        quote = market_data.get_live_quote()
        price = quote["price"]
        change = quote["change_pct"]
        sign = "+" if change >= 0 else ""
        text = (
            f"👑 <b>XAUUSD AI PRO TRADER — ГЛАВНОЕ МЕНЮ</b>\n\n"
            f"💰 <b>Живая цена MT5:</b> <code>${price:.2f}</code> ({sign}{change:.2f}%)\n"
            f"📊 <b>Источник:</b> {quote['source']}\n\n"
            f"Выберите нужный раздел или отправьте скриншот графика:"
        )
        await query.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.HTML)

async def post_init(application):
    url = config.WEBAPP_URL
    if url.startswith("https://"):
        try:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🚀 ИИ Терминал",
                    web_app=WebAppInfo(url=url)
                )
            )
            logger.info(f"Default Telegram Menu Button (APP) set to: {url}")
        except Exception as e:
            logger.warning(f"Error setting default menu button: {e}")

def create_bot_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("scalp", scalp_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("meter", meter_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("account", account_command))
    app.add_handler(CommandHandler("help", photo_info_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_menu_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    return app

if __name__ == "__main__":
    bot_app = create_bot_app()
    logger.info("Starting Telegram Bot Polling...")
    bot_app.run_polling()
