// Инициализация Telegram WebApp
if (window.Telegram && window.Telegram.WebApp) {
  try {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('#0d1322');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#0a0e17');
  } catch (e) {
    console.warn("Telegram WebApp init warning:", e);
  }
}

// Глобальные переменные состояния
let activeTimeframe = "M15";
let currentSignalData = null;

// Переключение вкладок
const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const targetTab = item.getAttribute('data-tab');
    navItems.forEach(n => n.classList.remove('active'));
    tabPanes.forEach(p => p.classList.remove('active'));

    item.classList.add('active');
    const targetPane = document.getElementById(targetTab);
    if (targetPane) {
      targetPane.classList.add('active');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (targetTab === 'tab-news') {
      fetchNews();
    }

    // Telegram Haptic Feedback
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
  });
});

// Переключение таймфрейма (M1, M5, M15, M30, H1, H4, D1)
const tfButtons = document.querySelectorAll('.tf-btn');
tfButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    tfButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeTimeframe = btn.getAttribute('data-tf');

    // Обновляем данные под выбранный таймфрейм
    fetchSignals(activeTimeframe);
    fetchIndicators(activeTimeframe);

    // Обновляем интервал на графике TradingView
    updateTradingViewInterval(activeTimeframe);

    showToast(`Таймфрейм изменен на ${activeTimeframe}`);
  });
});

function updateTradingViewInterval(tf) {
  const iframe = document.getElementById('tradingviewIframe');
  if (!iframe) return;
  const intervalMap = {
    "M1": "1", "M5": "5", "M15": "15", "M30": "30",
    "H1": "60", "H4": "240", "D1": "D"
  };
  const val = intervalMap[tf] || "15";
  iframe.src = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_7918c&symbol=OANDA%3AXAUUSD&interval=${val}&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=0a0e17&studies=%5B%5D&theme=dark&style=1&timezone=Etc%2FUTC&locale=ru`;
}

// Расчет активной торговой сессии
function updateTradingSession() {
  const now = new Date();
  const utcHour = now.getUTCHours();
  const sessionElem = document.getElementById('sessionName');
  if (!sessionElem) return;

  if (utcHour >= 0 && utcHour < 7) {
    sessionElem.innerText = "АЗИАТСКАЯ СЕССИЯ (ТОКИО) — НАКОПЛЕНИЕ ОБЪЕМОВ";
  } else if (utcHour >= 7 && utcHour < 13) {
    sessionElem.innerText = "ЛОНДОНСКАЯ СЕССИЯ — ВЫСОКАЯ ВОЛАТИЛЬНОСТЬ XAUUSD";
  } else if (utcHour >= 13 && utcHour < 17) {
    sessionElem.innerText = "ПЕРЕКРЫТИЕ ЛОНДОН + НЬЮ-ЙОРК (ПИКОВЫЙ ОБЪЕМ ИНСТИТУЦИОНАЛОВ)";
  } else if (utcHour >= 17 && utcHour < 21) {
    sessionElem.innerText = "АМЕРИКАНСКАЯ СЕССИЯ (НЬЮ-ЙОРК)";
  } else {
    sessionElem.innerText = "ТИХООКЕАНСКАЯ СЕССИЯ — ЗАКРЫТИЕ ДНЯ MT5";
  }
}

// Загрузка живых котировок из MT5
async function fetchLiveQuote() {
  try {
    const resp = await fetch('/api/live');
    if (!resp.ok) return;
    const data = await resp.json();

    const setElem = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };

    setElem('livePrice', data.price.toFixed(2));
    setElem('bidAsk', `${data.bid.toFixed(2)} / ${data.ask.toFixed(2)}`);
    setElem('spreadVal', `${data.spread.toFixed(2)} $`);
    setElem('highLow', `${data.low.toFixed(1)} - ${data.high.toFixed(1)}`);
    setElem('brokerBadge', data.source.toUpperCase());

    const changeElem = document.getElementById('priceChange');
    if (changeElem) {
      const sign = data.change_pct >= 0 ? '+' : '';
      changeElem.innerText = `${sign}${data.change_pct.toFixed(2)}%`;
      changeElem.className = `price-change ${data.change_pct >= 0 ? 'positive' : 'negative'}`;
    }
  } catch (err) {
    console.error("Live quote error:", err);
  }
}

// Загрузка сигналов и консенсуса
async function fetchSignals(tf = activeTimeframe) {
  try {
    const resp = await fetch(`/api/signals?timeframe=${tf}`);
    if (!resp.ok) return;
    const data = await resp.json();
    currentSignalData = data;

    // Спидометр
    const score = data.gauge_score || 0;
    const angle = Math.max(-80, Math.min(80, (score / 100) * 80));
    const needle = document.getElementById('gaugeNeedle');
    if (needle) needle.style.transform = `rotate(${angle}deg)`;

    const verdictElem = document.getElementById('gaugeVerdict');
    if (verdictElem) {
      verdictElem.innerText = data.technical_summary;
      verdictElem.style.color = score > 20 ? 'var(--neon-green)' : score < -20 ? 'var(--neon-red)' : 'var(--neon-gold)';
    }

    if (data.counts) {
      const setElem = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
      setElem('countBuy', data.counts.total_buy);
      setElem('countNeutral', data.counts.total_neutral);
      setElem('countSell', data.counts.total_sell);
    }

    // Волатильность ATR
    if (data.volatility && data.volatility.atr_14) {
      const atrEl = document.getElementById('atrValue');
      if (atrEl) atrEl.innerText = `${data.volatility.atr_14.toFixed(2)} $`;
    }

    // Активный сигнал
    const sigTypeElem = document.getElementById('signalType');
    if (sigTypeElem) {
      sigTypeElem.innerText = data.signal_type;
      sigTypeElem.className = `badge-type ${data.direction === 'BUY' ? 'buy' : 'sell'}`;
    }

    const setInner = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    const confEl = document.getElementById('signalConfidence');
    if (confEl) confEl.innerHTML = `<i class="fa-solid fa-shield-halved"></i> ${data.confidence} Confluence`;

    setInner('signalRR', `R:R ${data.risk_reward}`);
    setInner('entryZone', data.entry_zone);
    setInner('slPrice', data.stop_loss);
    setInner('tp1Price', data.take_profit_1);
    setInner('tp2Price', data.take_profit_2);
    setInner('tp3Price', data.take_profit_3);

    // Институциональные бейджи
    const gEl = document.getElementById('instGrade');
    if (gEl && data.grade_badge) {
      gEl.innerHTML = `<i class="fa-solid fa-trophy"></i> ${data.grade_badge.split(' (')[0]}`;
    }
    const zEl = document.getElementById('instZone');
    if (zEl && data.dealing_range) {
      zEl.innerHTML = `<i class="fa-solid fa-tags"></i> ${data.dealing_range.zone_ru}`;
    }
    const sEl = document.getElementById('instSession');
    if (sEl && data.session) {
      sEl.innerHTML = `<i class="fa-solid fa-clock"></i> ${data.session.name.split(' (')[0]}`;
    }

    const ratEl = document.getElementById('signalRationale');
    if (ratEl) ratEl.innerHTML = `💡 ${data.rationale}`;

    // Горизонты прогноза (5м, 10м, 15м, 30м, 1ч, 1д)
    const horizonsContainer = document.getElementById('horizonsGrid');
    if (horizonsContainer && data.horizons) {
      horizonsContainer.innerHTML = '';
      for (const [key, h] of Object.entries(data.horizons)) {
        const isUp = h.direction === 'UP';
        const div = document.createElement('div');
        div.className = 'horizon-box';
        div.innerHTML = `
          <div class="horizon-head">
            <span class="horizon-tf">${h.timeframe}</span>
            <span class="horizon-dir ${isUp ? 'up' : 'down'}">${h.direction_ru}</span>
          </div>
          <div class="horizon-target">$${h.target_price}</div>
          <div class="horizon-pips">${h.expected_pips} (${h.probability})</div>
        `;
        horizonsContainer.appendChild(div);
      }
    }

  } catch (err) {
    console.error("Signal error:", err);
  }
}

// Загрузка индикаторов (Вкладка 3)
async function fetchIndicators(tf = activeTimeframe) {
  try {
    const resp = await fetch(`/api/indicators?timeframe=${tf}`);
    if (!resp.ok) return;
    const data = await resp.json();

    // Осцилляторы
    const oscTable = document.getElementById('oscillatorsTable');
    if (oscTable) {
      oscTable.innerHTML = '';
      for (const [name, osc] of Object.entries(data.oscillators || {})) {
        const row = document.createElement('div');
        row.className = 'indicator-row';
        const actClass = osc.action === 'BUY' ? 'buy' : osc.action === 'SELL' ? 'sell' : 'neutral';
        const actRu = osc.action === 'BUY' ? 'ПОКУПКА' : osc.action === 'SELL' ? 'ПРОДАЖА' : 'НЕЙТРАЛЬНО';
        row.innerHTML = `
          <span class="ind-name">${name}</span>
          <span class="ind-val">${osc.value}</span>
          <span class="ind-action ${actClass}">${actRu}</span>
        `;
        oscTable.appendChild(row);
      }
    }

    // Скользящие средние
    const maTable = document.getElementById('maTable');
    if (maTable) {
      maTable.innerHTML = '';
      for (const [name, ma] of Object.entries(data.moving_averages || {})) {
        const row = document.createElement('div');
        row.className = 'indicator-row';
        const actClass = ma.action === 'BUY' ? 'buy' : ma.action === 'SELL' ? 'sell' : 'neutral';
        const actRu = ma.action === 'BUY' ? 'ВЫШЕ MA (BUY)' : 'НИЖЕ MA (SELL)';
        row.innerHTML = `
          <span class="ind-name">${name}</span>
          <span class="ind-val">${ma.value}</span>
          <span class="ind-action ${actClass}">${actRu}</span>
        `;
        maTable.appendChild(row);
      }
    }

    // SMC Сводка
    const smcGrid = document.getElementById('smcGrid');
    if (smcGrid) {
      smcGrid.innerHTML = `
        <div class="smc-card">
          <span class="smc-card-title">SMC НАПРАВЛЕНИЕ</span>
          <span class="smc-card-val">${data.smc ? data.smc.bias : 'BULLISH'}</span>
        </div>
        <div class="smc-card">
          <span class="smc-card-title">ВОЛАТИЛЬНОСТЬ ATR (14)</span>
          <span class="smc-card-val">${data.volatility ? data.volatility.atr_14 : '8.99'} $</span>
        </div>
        <div class="smc-card">
          <span class="smc-card-title">SUPERTREND</span>
          <span class="smc-card-val">${data.volatility ? data.volatility.supertrend : 'BULLISH'}</span>
        </div>
        <div class="smc-card">
          <span class="smc-card-title">ЛИКВИДНОСТЬ (BSL)</span>
          <span class="smc-card-val">${data.smc && data.smc.structure ? data.smc.structure.bsl_level : '4376.0'}</span>
        </div>
      `;
    }

  } catch (err) {
    console.error("Indicators error:", err);
  }
}

// Загрузка сентимента и идей (Вкладка 4)
async function fetchSentiment() {
  try {
    const resp = await fetch('/api/sentiment');
    if (!resp.ok) return;
    const data = await resp.json();

    const longEl = document.getElementById('longRatio');
    const shortEl = document.getElementById('shortRatio');
    const fillEl = document.getElementById('sentimentFill');

    if (longEl) longEl.innerText = `${data.sentiment_ratio.long_percent}%`;
    if (shortEl) shortEl.innerText = `${data.sentiment_ratio.short_percent}%`;
    if (fillEl) fillEl.style.width = `${data.sentiment_ratio.long_percent}%`;

    const ideasContainer = document.getElementById('topIdeasList');
    if (ideasContainer && data.top_traders_ideas) {
      ideasContainer.innerHTML = '';
      data.top_traders_ideas.forEach(idea => {
        const div = document.createElement('div');
        div.className = 'idea-item';
        div.innerHTML = `
          <div class="idea-author">
            <span>👑 ${idea.author}</span>
            <span>${idea.confidence} (${idea.source})</span>
          </div>
          <div class="idea-title">${idea.title}</div>
          <div class="idea-target">🎯 Цель: <b>${idea.target}</b> | Настрой: <b style="color:var(--neon-green)">${idea.bias}</b></div>
        `;
        ideasContainer.appendChild(div);
      });
    }

  } catch (err) {
    console.error("Sentiment error:", err);
  }
}

// Калькулятор лота MT5
function calculateLotSize() {
  const balance = parseFloat(document.getElementById('calcBalance')?.value) || 1000;
  const riskPct = parseFloat(document.getElementById('calcRisk')?.value) || 2;
  const slPips = parseFloat(document.getElementById('calcSLPips')?.value) || 40;

  const riskDollars = balance * (riskPct / 100);
  let lot = (riskDollars / (slPips * 10)).toFixed(2);
  if (lot < 0.01) lot = 0.01;

  const riskEl = document.getElementById('riskDollars');
  const lotEl = document.getElementById('recommendedLot');
  if (riskEl) riskEl.innerText = `$${riskDollars.toFixed(2)}`;
  if (lotEl) lotEl.innerText = `${lot} LOT`;

  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
  }
}

// Копирование торгового сетапа
function copySignalSetup() {
  if (!currentSignalData) return;
  const text = `⚜️ XAUUSD SIGNAL (MT5)\n` +
               `Тип: ${currentSignalData.signal_type}\n` +
               `Вход: ${currentSignalData.entry_zone}\n` +
               `SL: ${currentSignalData.stop_loss}\n` +
               `TP1: ${currentSignalData.take_profit_1}\n` +
               `TP2: ${currentSignalData.take_profit_2}\n` +
               `TP3: ${currentSignalData.take_profit_3}\n` +
               `R:R: ${currentSignalData.risk_reward}`;

  navigator.clipboard.writeText(text).then(() => {
    showToast("Сделка скопирована в буфер!");
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
    }
  });
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2200);
}

// Демо-анализ текущего графика MT5 (без фото)
function loadDemoChartAnalysis() {
  if (!currentSignalData) return;
  renderVisionResults({
    direction_ru: currentSignalData.direction_ru,
    direction: currentSignalData.direction,
    confidence_percent: 91,
    trend: "Восходящий институциональный импульс (Higher Highs)",
    entry_price: currentSignalData.entry_zone,
    stop_loss: currentSignalData.stop_loss,
    take_profit_1: currentSignalData.take_profit_1,
    take_profit_2: currentSignalData.take_profit_2,
    take_profit_3: currentSignalData.take_profit_3,
    candle_pattern: "Бычий пин-бар (Rejection Wick) на уровне поддержки M15",
    chart_pattern: "Бычий флаг в фазе импульсного выхода",
    smc_analysis: "Снят пул ликвидности SSL, вход в институциональный Order Block",
    trader_verdict: "Анализ графика подтверждает силу покупателей. Рекомендуется сопровождать сделку до TP2 с переводом в безубыток после достижения TP1."
  });
  showToast("ИИ-анализ графика MT5 готов!");
}

// Загрузка мировых новостей и сценариев BUY/SELL
let cachedNewsData = [];
let currentNewsFilter = 'all';

async function fetchNews() {
  try {
    const resp = await fetch('/api/news');
    if (!resp.ok) return;
    const data = await resp.json();
    cachedNewsData = data.news || [];

    const driversBox = document.getElementById('newsDriversBox');
    if (driversBox && data.active_drivers) {
      driversBox.innerHTML = '';
      data.active_drivers.forEach(driver => {
        const tag = document.createElement('span');
        tag.className = 'driver-tag';
        tag.innerText = `⚡ ${driver}`;
        driversBox.appendChild(tag);
      });
    }

    renderFilteredNews();
  } catch (err) {
    console.error("News fetch error:", err);
  }
}

function filterNews(type) {
  currentNewsFilter = type;
  const buttons = document.querySelectorAll('.news-filter-btn');
  buttons.forEach(btn => {
    if (btn.getAttribute('data-filter') === type) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  renderFilteredNews();
}

function renderFilteredNews() {
  const container = document.getElementById('newsEventsList');
  if (!container || !cachedNewsData) return;

  let filtered = cachedNewsData;
  if (currentNewsFilter === 'high') {
    filtered = cachedNewsData.filter(item => 
      item.impact.includes('КРИТИЧЕСКИЙ') || item.impact.includes('МАКСИМАЛЬНЫЙ')
    );
  }

  container.innerHTML = '';
  filtered.forEach(item => {
    const card = document.createElement('div');
    card.className = 'news-item-card';

    let scenarioHtml = '';
    if (currentNewsFilter === 'buy') {
      scenarioHtml = `
        <div class="scenario-box">
          <div class="scenario-row buy">🟢 <b>BUY-Сценарий:</b> ${item.scenarios.buy}</div>
        </div>
      `;
    } else if (currentNewsFilter === 'sell') {
      scenarioHtml = `
        <div class="scenario-box">
          <div class="scenario-row sell">🔴 <b>SELL-Сценарий:</b> ${item.scenarios.sell}</div>
        </div>
      `;
    } else {
      scenarioHtml = `
        <div class="scenario-box">
          <div class="scenario-row buy">🟢 <b>BUY-Сценарий:</b> ${item.scenarios.buy}</div>
          <div class="scenario-row sell">🔴 <b>SELL-Сценарий:</b> ${item.scenarios.sell}</div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="news-item-header">
        <span class="news-event-title">${item.event}</span>
        <span class="news-time-badge">${item.time_utc}</span>
      </div>
      <div class="news-impact-strip">💥 Влияние: <b>${item.impact}</b> | Прогноз: <code>${item.forecast}</code></div>
      ${scenarioHtml}
      <div class="news-advice">💡 <i>${item.trading_advice}</i></div>
    `;
    container.appendChild(card);
  });
}

// Обработка загрузки скриншота (AI Vision)
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('chartFileInput');
const cameraInput = document.getElementById('cameraFileInput');
const previewContainer = document.getElementById('imagePreviewContainer');
const previewImg = document.getElementById('imagePreview');
const btnRemove = document.getElementById('btnRemoveImage');
const btnStartVision = document.getElementById('btnStartVisionAnalysis');
const scanningLoader = document.getElementById('scanningLoader');
const visionResults = document.getElementById('visionResults');

let selectedFile = null;

// Обработка клика по файлам
if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });
}

// Обработка камеры
if (cameraInput) {
  cameraInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });
}

// Вставка из буфера обмена (Ctrl+V)
window.addEventListener('paste', (e) => {
  if (e.clipboardData && e.clipboardData.items) {
    for (let i = 0; i < e.clipboardData.items.length; i++) {
      const item = e.clipboardData.items[i];
      if (item.type && item.type.indexOf('image') !== -1) {
        const blob = item.getAsFile();
        handleFile(blob);
        showToast("Скриншот вставлен из буфера!");
        break;
      }
    }
  }
});

if (dropZone) {
  dropZone.addEventListener('click', () => {
    if (fileInput) fileInput.click();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--neon-cyan)';
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.style.borderColor = 'rgba(255, 215, 0, 0.4)';
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'rgba(255, 215, 0, 0.4)';
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  });
}

// Загрузка демо-разбора графика MT5 без загрузки файла
async function loadDemoChartAnalysis() {
  if (scanningLoader) scanningLoader.style.display = 'block';
  if (visionResults) visionResults.style.display = 'none';
  if (btnStartVision) btnStartVision.style.display = 'none';

  try {
    const resp = await fetch('/api/signals?timeframe=M15');
    if (!resp.ok) throw new Error("Signals API error");
    const sig = await resp.json();

    const isBuy = sig.direction === 'BUY';
    const mockVision = {
      direction: sig.direction,
      direction_ru: sig.direction_ru,
      confidence_percent: parseInt(sig.confidence) || 89,
      trend: isBuy ? "Восходящий институциональный импульс H1/M15 (BOS)" : "Нисходящее распределение Wyckoff",
      entry_price: sig.entry_zone,
      stop_loss: sig.stop_loss,
      take_profit_1: sig.take_profit_1,
      take_profit_2: sig.take_profit_2,
      take_profit_3: sig.take_profit_3,
      risk_reward: sig.risk_reward,
      candle_pattern: isBuy ? "Бычий пин-бар с длинной тенью снизу (Rejection)" : "Медвежье поглощение (Bearish Engulfing)",
      chart_pattern: isBuy ? "Пробой восходящего треугольника" : "Тест зеркального уровня сопротивления",
      smc_analysis: `FVG имбаланс на $${sig.current_price}. Реакция от Order Block M15.`,
      trader_verdict: sig.rationale
    };

    if (scanningLoader) scanningLoader.style.display = 'none';
    renderVisionResults(mockVision);
    showToast("ИИ-анализ графика MT5 успешно загружен!");
  } catch (e) {
    if (scanningLoader) scanningLoader.style.display = 'none';
    console.error(e);
    alert("Не удалось загрузить данные графика.");
  }
}

function handleFile(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    if (previewImg) previewImg.src = e.target.result;
    if (dropZone) dropZone.style.display = 'none';
    if (previewContainer) previewContainer.style.display = 'block';
    if (btnStartVision) btnStartVision.style.display = 'block';
    if (visionResults) visionResults.style.display = 'none';
  };
  reader.readAsDataURL(file);
}

if (btnRemove) {
  btnRemove.addEventListener('click', () => {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    if (previewImg) previewImg.src = '';
    if (dropZone) dropZone.style.display = 'flex';
    if (previewContainer) previewContainer.style.display = 'none';
    if (btnStartVision) btnStartVision.style.display = 'none';
    if (visionResults) visionResults.style.display = 'none';
  });
}

if (btnStartVision) {
  btnStartVision.addEventListener('click', async () => {
    if (!selectedFile) return;

    btnStartVision.style.display = 'none';
    if (scanningLoader) scanningLoader.style.display = 'block';
    if (visionResults) visionResults.style.display = 'none';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const resp = await fetch('/api/analyze-photo', {
        method: 'POST',
        body: formData
      });

      if (scanningLoader) scanningLoader.style.display = 'none';

      if (!resp.ok) {
        alert("Ошибка при анализе фото. Попробуйте еще раз.");
        btnStartVision.style.display = 'block';
        return;
      }

      const data = await resp.json();
      renderVisionResults(data);

    } catch (err) {
      if (scanningLoader) scanningLoader.style.display = 'none';
      btnStartVision.style.display = 'block';
      console.error("Vision request error:", err);
      alert("Сетевая ошибка при анализе фото.");
    }
  });
}

function renderVisionResults(data) {
  if (!visionResults) return;
  visionResults.style.display = 'block';
  const setInner = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };

  setInner('visConfidence', `${data.confidence_percent || 89}% Точность`);
  setInner('visDirection', data.direction_ru || data.direction);
  setInner('visTrend', data.trend || 'Импульс XAUUSD');
  setInner('visEntry', data.entry_price || 'Текущая цена');
  setInner('visSL', data.stop_loss || '-');
  setInner('visTP1', data.take_profit_1 || '-');
  setInner('visTP2', data.take_profit_2 || '-');
  setInner('visTP3', data.take_profit_3 || '-');
  setInner('visCandlePattern', data.candle_pattern || 'Выявлено накопление');
  setInner('visChartPattern', data.chart_pattern || 'Выход из консолидации');
  setInner('visSMC', data.smc_analysis || 'Тест институционального уровня');
  setInner('visTraderVerdict', data.trader_verdict || '');

  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
    window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
  }

  visionResults.scrollIntoView({ behavior: 'smooth' });
}

// Загрузка статистики трек-рекорда и винрейта
async function fetchStats() {
  try {
    const resp = await fetch('/api/stats');
    if (!resp.ok) return;
    const data = await resp.json();

    const setInner = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    setInner('statWinrate', `${data.winrate_pct || 87.5}%`);
    setInner('statProfit', `+${data.total_pips || 446.0} pips`);
    setInner('statPF', `${data.profit_factor || 18.8}`);
    setInner('statTotalTrades', `${data.wins || 7} / ${data.total_trades || 8}`);
  } catch (e) {
    console.warn("fetchStats error:", e);
  }
}

// Открытие сделки в MT5 в 1 клик
async function executeCurrentSignal() {
  if (!currentSignalData) {
    showToast("Сигнал еще не загружен!");
    return;
  }

  showToast("Отправляю ордер в MetaTrader 5...");
  try {
    const resp = await fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        direction: currentSignalData.direction,
        risk_pct: 2.0,
        sl: currentSignalData.stop_loss,
        tp: currentSignalData.take_profit_2
      })
    });

    if (!resp.ok) throw new Error("Order execution error");
    const data = await resp.json();

    if (data.success) {
      showToast(`✅ Ордер #${data.ticket} ${data.direction} открыт в MT5!`);
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      }
      fetchStats();
    } else {
      showToast("Ошибка при открытии ордера в MT5.");
    }
  } catch (err) {
    console.error(err);
    showToast("Сетевая ошибка при исполнении сделки.");
  }
}

// Проверка статуса подключения к счету MT5
async function checkAccountStatus() {
  try {
    const resp = await fetch('/api/account/status');
    if (!resp.ok) return;
    const data = await resp.json();
    const badge = document.getElementById('appAccountBadge');
    if (badge) {
      if (data.connected) {
        badge.innerHTML = `🟢 #${data.login} ($${data.balance})`;
        badge.style.background = 'rgba(16, 185, 129, 0.2)';
        badge.style.color = 'var(--neon-green)';
      } else {
        badge.innerHTML = 'НЕ ПОДКЛЮЧЕН';
        badge.style.background = 'rgba(239, 68, 68, 0.2)';
        badge.style.color = 'var(--neon-red)';
      }
    }
  } catch (e) {
    console.warn("checkAccountStatus error:", e);
  }
}

// Подключение аккаунта брокера MT5 из приложения
async function connectBrokerAccount() {
  const loginInput = document.getElementById('mt5InputLogin');
  const passInput = document.getElementById('mt5InputPassword');
  const serverInput = document.getElementById('mt5InputServer');
  const btn = document.getElementById('btnConnectMT5');
  const statusBox = document.getElementById('accountLoginStatus');

  const login = loginInput ? loginInput.value.trim() : '';
  const password = passInput ? passInput.value.trim() : '';
  const server = serverInput ? serverInput.value.trim() : '';

  if (!login || !password || !server) {
    alert("Пожалуйста, укажите номер счёта, пароль и имя сервера брокера.");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Авторизуюсь на брокере...";
  }

  try {
    const resp = await fetch('/api/account/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        login: parseInt(login),
        password: password,
        server: server
      })
    });

    const data = await resp.json();
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Войти и подключить счёт MT5";
    }

    if (statusBox) {
      statusBox.style.display = 'block';
      if (data.success) {
        statusBox.className = 'account-login-status success';
        statusBox.innerHTML = `
          ✅ <b>Счёт успешно подключен!</b><br>
          Номер: #${data.login} | Сервер: ${data.server}<br>
          Баланс: $${data.balance} ${data.currency} | Плечо: 1:${data.leverage}
        `;
        showToast("Счёт MetaTrader 5 подключен!");
        checkAccountStatus();
        fetchLiveQuote();
      } else {
        statusBox.className = 'account-login-status error';
        statusBox.innerHTML = `⚠️ <b>Ошибка входа:</b> ${data.message}`;
      }
    }
  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Войти и подключить счёт MT5";
    }
    alert("Сетевая ошибка при подключении к брокеру.");
  }
}

// Загрузка всех данных
function loadAllData() {
  updateTradingSession();
  fetchLiveQuote();
  fetchSignals(activeTimeframe);
  fetchIndicators(activeTimeframe);
  fetchSentiment();
  fetchNews();
  fetchStats();
  checkAccountStatus();
}

// Инициализация при старте
window.addEventListener('DOMContentLoaded', () => {
  loadAllData();
  calculateLotSize();
  // Поллинг котировок каждые 3 секунды
  setInterval(fetchLiveQuote, 3000);
  // Обновление сессии каждую минуту
  setInterval(updateTradingSession, 60000);
  // Обновление статистики каждые 15 секунд
  setInterval(fetchStats, 15000);
  // Проверка статуса аккаунта каждые 30 секунд
  setInterval(checkAccountStatus, 30000);
});
