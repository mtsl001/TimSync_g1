/* ═══════════════════════════════════════════════════════════
   Trade Signal Engine — Frontend App (app.js)
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const State = {
  sessionId:   null,
  signals:     [],
  chartData:   [],
  orb:         null,
  priceChart:  null,
  volChart:    null,
  priceSeries: null,
  ema9Series:  null,
  ema21Series: null,
  vwapSeries:  null,
  volSeries:   null,
};

// ── DOM Refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $q = sel => document.querySelector(sel);

// ── Strategy config from checkboxes ──────────────────────────────────────────
function getStratConfig() {
  const cfg = {};
  document.querySelectorAll('.strat-row').forEach(row => {
    const key = row.dataset.key;
    const chk = row.querySelector('input[type="checkbox"]');
    cfg[key] = chk.checked;
  });
  return cfg;
}

// ── Risk calculator ───────────────────────────────────────────────────────────
function updateRiskDisplay() {
  const capital = parseFloat($('inp-capital').value) || 25000;
  const risk    = parseFloat($('inp-risk').value)    || 500;
  $('r-loss').textContent    = `₹${(risk * 2).toLocaleString()}`;
  $('r-target').textContent  = `₹${Math.round(capital * 0.005).toLocaleString()}`;
  $('r-monthly').textContent = `₹${Math.round(capital * 0.1).toLocaleString()}`;
}

// ── Tab switcher ──────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === `tab-${tabId}`));
  if (tabId === 'chart' && State.priceChart) {
    setTimeout(() => resizeCharts(), 50);
  }
  if (tabId === 'journal') loadJournal();
}

// ── Chart helpers ─────────────────────────────────────────────────────────────
function candleColor(c) { return c.close >= c.open ? '#00d4a0' : '#ff4d6a'; }

function initCharts() {
  const chartOpts = {
    layout:   { background: { color: '#0d0f18' }, textColor: '#3d4565' },
    grid:     { vertLines: { color: '#1c2035' }, horzLines: { color: '#1c2035' } },
    crosshair:{ mode: 1 },
    rightPriceScale: { borderColor: '#1c2035' },
    timeScale: { borderColor: '#1c2035', timeVisible: true, secondsVisible: false },
    handleScroll: true,
    handleScale:  true,
  };

  const priceEl = $('chart-container');
  const volEl   = $('volume-container');

  State.priceChart = LightweightCharts.createChart(priceEl, { ...chartOpts, height: priceEl.offsetHeight || 300 });
  State.volChart   = LightweightCharts.createChart(volEl,   {
    ...chartOpts,
    height: volEl.offsetHeight || 90,
    rightPriceScale: { visible: true, borderColor: '#1c2035' },
    timeScale: { ...chartOpts.timeScale, visible: false },
  });

  State.priceSeries = State.priceChart.addCandlestickSeries({
    upColor: '#00d4a0', downColor: '#ff4d6a',
    borderUpColor: '#00d4a0', borderDownColor: '#ff4d6a',
    wickUpColor: '#00d4a0', wickDownColor: '#ff4d6a',
  });

  State.ema9Series = State.priceChart.addLineSeries({
    color: '#7c9dff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
  });
  State.ema21Series = State.priceChart.addLineSeries({
    color: '#ff9f45', lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
  });
  State.vwapSeries = State.priceChart.addLineSeries({
    color: '#00d4a0', lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false,
  });

  State.volSeries = State.volChart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'right',
  });

  window.addEventListener('resize', resizeCharts);
}

function resizeCharts() {
  const priceEl = $('chart-container');
  const volEl   = $('volume-container');
  if (State.priceChart && priceEl) State.priceChart.resize(priceEl.offsetWidth, priceEl.offsetHeight);
  if (State.volChart   && volEl)   State.volChart.resize(volEl.offsetWidth,   volEl.offsetHeight);
}

function renderChart(chartData, signals, orb) {
  if (!State.priceChart) initCharts();

  // Convert datetime strings to timestamps for lightweight-charts
  const toTS = (dt) => {
    if (!dt) return 0;
    // Try HH:MM format (intraday, assume today)
    const today = new Date().toISOString().split('T')[0];
    let parsed;
    if (/^\d{2}:\d{2}$/.test(dt)) {
      parsed = new Date(`${today}T${dt}:00`);
    } else if (/^\d{2}:\d{2}:\d{2}$/.test(dt)) {
      parsed = new Date(`${today}T${dt}`);
    } else {
      parsed = new Date(dt);
    }
    return isNaN(parsed.getTime()) ? 0 : Math.floor(parsed.getTime() / 1000);
  };

  // If timestamps aren't parseable, use index-based fake timestamps
  const baseTS = Math.floor(new Date().setHours(9, 15, 0, 0) / 1000);
  const useFakeTS = !chartData[0] || toTS(chartData[0].datetime) === 0;

  const candles   = [];
  const ema9Data  = [];
  const ema21Data = [];
  const vwapData  = [];
  const volData   = [];

  chartData.forEach((d, i) => {
    const time = useFakeTS ? baseTS + i * 60 : toTS(d.datetime) + i; // +i prevents duplicates
    if (!time) return;

    candles.push({ time, open: d.open, high: d.high, low: d.low, close: d.close });
    volData.push({ time, value: d.volume || 0, color: d.close >= d.open ? '#00d4a080' : '#ff4d6a80' });

    if (d.ema9)  ema9Data.push({ time, value: d.ema9 });
    if (d.ema21) ema21Data.push({ time, value: d.ema21 });
    if (d.vwap)  vwapData.push({ time, value: d.vwap });
  });

  State.priceSeries.setData(candles);
  State.ema9Series.setData(ema9Data);
  State.ema21Series.setData(ema21Data);
  State.vwapSeries.setData(vwapData);
  State.volSeries.setData(volData);

  // ORB reference lines
  if (orb) {
    State.priceSeries.createPriceLine({ price: orb.high, color: '#f0a500', lineWidth: 1, lineStyle: 2, title: `ORB H ${orb.high}` });
    State.priceSeries.createPriceLine({ price: orb.low,  color: '#ff4d6a', lineWidth: 1, lineStyle: 2, title: `ORB L ${orb.low}` });
    $('strip-orb').style.display = '';
    $('strip-orb-h').textContent = `₹${orb.high}`;
    $('strip-orb-l').textContent = `₹${orb.low}`;
    $('leg-orb').style.display = '';
    $('sc-orb-h').textContent = `₹${orb.high}`;
    $('sc-orb-l').textContent = `₹${orb.low}`;
    $('st-orb-h').textContent = `₹${orb.high}`;
    $('st-orb-l').textContent = `₹${orb.low}`;
  }

  // Signal markers on chart
  const markers = signals.map((s, i) => {
    const idx = s.candle_index;
    const time = useFakeTS ? baseTS + idx * 60 : (candles[idx]?.time || baseTS + idx * 60);
    return {
      time,
      position: s.type === 'BUY' ? 'belowBar' : 'aboveBar',
      color:    s.type === 'BUY' ? '#00d4a0'  : '#ff4d6a',
      shape:    s.type === 'BUY' ? 'arrowUp'  : 'arrowDown',
      text:     `${s.type} ₹${s.entry}`,
      size: 1.5,
    };
  });
  State.priceSeries.setMarkers(markers);

  State.priceChart.timeScale().fitContent();
  State.volChart.timeScale().fitContent();
}

// ── Update topbar ─────────────────────────────────────────────────────────────
function updateTopbar(data) {
  const { candles, orb, signals, session } = data;
  if (!candles || !candles.length) return;

  const last  = candles[candles.length - 1];
  const first = candles[0];
  const chg   = ((last.close - first.close) / first.close * 100).toFixed(2);
  const up    = parseFloat(chg) >= 0;

  $('strip-stock').textContent = session?.stock_name || $('inp-stock').value;
  $('strip-price').textContent = `₹${last.close.toFixed(2)}`;
  $('strip-chg').textContent   = `${up ? '▲' : '▼'} ${Math.abs(chg)}%`;
  $('strip-chg').style.color   = up ? '#00d4a0' : '#ff4d6a';

  const lastVwap  = candles[candles.length - 1].vwap;
  const lastEma9  = candles[candles.length - 1].ema9;
  const lastEma21 = candles[candles.length - 1].ema21;
  if (lastVwap)  $('strip-vwap').textContent  = `₹${lastVwap}`;
  if (lastEma9)  $('strip-ema9').textContent  = `₹${lastEma9}`;
  if (lastEma21) $('strip-ema21').textContent = `₹${lastEma21}`;

  $('badge-signals').textContent = `${signals.length} SIGNALS`;

  // Stats strip
  const high = Math.max(...candles.map(c => c.high)).toFixed(2);
  const low  = Math.min(...candles.map(c => c.low)).toFixed(2);
  $('sc-candles').textContent = candles.length;
  $('sc-high').textContent    = `₹${high}`;
  $('sc-low').textContent     = `₹${low}`;
  $('sc-sigs').textContent    = signals.length;
  $('sc-buy').textContent     = signals.filter(s => s.type === 'BUY').length;
  $('sc-sell').textContent    = signals.filter(s => s.type === 'SELL').length;

  // Sidebar stats
  $('st-candles').textContent = candles.length;
  $('st-signals').textContent = signals.length;
  $('st-buy').textContent     = signals.filter(s => s.type === 'BUY').length;
  $('st-sell').textContent    = signals.filter(s => s.type === 'SELL').length;

  $('tab-sig-count').textContent = `(${signals.length})`;
}

// ── Render signals list ───────────────────────────────────────────────────────
function renderSignals(signals) {
  const list = $('signals-list');
  const empty = $('signals-empty');

  if (!signals.length) {
    empty.style.display = '';
    list.innerHTML = '';
    return;
  }
  empty.style.display = 'none';

  list.innerHTML = signals.map(s => {
    const isBuy   = s.type === 'BUY';
    const sColor  = isBuy ? '#00d4a0' : '#ff4d6a';
    const capPct  = ((s.cap_needed / (parseFloat($('inp-capital').value) || 25000)) * 100).toFixed(0);
    const scoreColor = s.score > 65 ? '#00d4a0' : s.score > 35 ? '#f0a500' : '#ff4d6a';
    const reasons = Array.isArray(s.reasons) ? s.reasons : JSON.parse(s.reasons || '[]');

    return `
    <div class="signal-card" data-id="${s.id}"
         style="border-color:${sColor}28; border-left-color:${sColor}">
      <div class="sig-header">
        <span class="sig-badge" style="color:${sColor}; border-color:${sColor}60; background:${sColor}12">
          ${isBuy ? '▲ BUY' : '▼ SELL'}
        </span>
        ${s.grade ? `<span class="sig-badge" style="color:${gradeColor(s.grade)};border-color:${gradeColor(s.grade)}60;background:${gradeColor(s.grade)}12;font-size:10px">
          Grade ${s.grade}
        </span>` : ''}
        <span class="sig-time">${s.time}</span>
        <span class="sig-field">ENTRY <span style="color:#fff">₹${s.entry}</span></span>
        <span class="sig-field">SL <span style="color:#ff4d6a">₹${s.sl}</span></span>
        <span class="sig-field">T1 <span style="color:#00d4a0">₹${s.t1}</span></span>
        <span class="sig-field">T2 <span style="color:#00d4a0">₹${s.t2}</span></span>
        <span class="sig-field">QTY <span style="color:#f0a500">${s.qty}</span></span>
        <span class="sig-field">R:R <span style="color:#7c9dff">1:${s.rr}</span></span>
        <span class="sig-field">Cap <span style="color:#d8ddf0">₹${Number(s.cap_needed).toLocaleString()} (${capPct}%)</span></span>
        <div class="strength-wrap">
          <div class="strength-label">STRENGTH</div>
          <div class="strength-bar-bg">
            <div class="strength-bar" style="width:${s.score}%; background:${scoreColor}"></div>
          </div>
          <div class="strength-pct" style="color:${scoreColor}">${s.score}%</div>
        </div>
      </div>
      <div class="sig-reasons">
        ${reasons.map(r => `<span class="reason-tag">${r}</span>`).join('')}
      </div>
      <div class="sig-detail" style="display:none">
        <div class="sig-detail-grid">
          ${detailGrid(s, isBuy)}
        </div>
        <div class="action-box ${isBuy ? 'buy' : 'sell'}">
          <div class="action-title" style="color:${sColor}">
            ${isBuy ? '▲ BUY' : '▼ SELL SIGNAL'} — ${s.stock_name || $('inp-stock').value}
          </div>
          ${isBuy
            ? `Buy <strong>${s.qty} shares</strong> at market / limit ₹${s.entry}<br>
               Place Stop Loss at <strong style="color:#ff4d6a">₹${s.sl}</strong> immediately after entry<br>
               Exit 50% at T1 (₹${s.t1}) → trail SL to entry cost<br>
               Exit balance at T2 (₹${s.t2}) or 3:15 PM — whichever is first`
            : `<span style="color:#ff9f45">⚠ Cash segment: avoid fresh longs if holding any.</span><br>
               Square off existing longs near ₹${s.entry} — this is a bearish signal<br>
               Wait for reversal confirmation above ₹${s.t1} before re-entering long`
          }
        </div>
        ${s.conviction?.factors ? `
          <div style="margin-top:10px;display:flex;gap:5px;flex-wrap:wrap">
            ${(Array.isArray(s.conviction.factors) ? s.conviction.factors : []).map(f => {
              const isPositive = f.startsWith('✓');
              return `<span style="font-size:10px;padding:2px 7px;border-radius:3px;
                background:${isPositive ? 'rgba(0,212,160,.08)' : 'rgba(255,77,106,.08)'};
                border:1px solid ${isPositive ? 'rgba(0,212,160,.3)' : 'rgba(255,77,106,.3)'};
                color:${isPositive ? '#00d4a0' : '#ff4d6a'}">${f}</span>`;
            }).join('')}
          </div>
        ` : ''}
        </div>
        <div style="margin-top:10px; display:flex; gap:8px">
          <button class="btn-sm log-trade-btn" data-sig='${JSON.stringify({
            type: s.type, entry: s.entry, sl: s.sl, target: s.t1,
            qty: s.qty, id: s.id, session_id: State.sessionId,
          })}'>📓 Log this trade</button>
        </div>
      </div>
    </div>`;
  }).join('');

  // Toggle expand
  list.querySelectorAll('.signal-card').forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.closest('.log-trade-btn')) return;
      const detail = card.querySelector('.sig-detail');
      const expanded = card.classList.toggle('expanded');
      detail.style.display = expanded ? '' : 'none';
    });
  });

  // Log trade buttons
  list.querySelectorAll('.log-trade-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const sig = JSON.parse(btn.dataset.sig);
      prefillJournalForm(sig);
      switchTab('journal');
      $('trade-form').style.display = '';
      $('trade-form').scrollIntoView({ behavior: 'smooth' });
    });
  });
}

function detailGrid(s, isBull) {
  const items = [
    { l: 'Entry',            v: `₹${s.entry}`,    c: '#fff'    },
    { l: 'Stop Loss',        v: `₹${s.sl}`,        c: '#ff4d6a', note: `₹${Math.abs(parseFloat(s.entry) - parseFloat(s.sl)).toFixed(2)}/share` },
    { l: 'Target 1 (1.5R)',  v: `₹${s.t1}`,        c: '#00d4a0', note: `+₹${Math.abs(parseFloat(s.t1) - parseFloat(s.entry)).toFixed(2)}` },
    { l: 'Target 2 (2.5R)',  v: `₹${s.t2}`,        c: '#00d4a0', note: `+₹${Math.abs(parseFloat(s.t2) - parseFloat(s.entry)).toFixed(2)}` },
    { l: 'Target 3 (4R)',    v: `₹${s.t3}`,        c: '#00b89a', note: `+₹${Math.abs(parseFloat(s.t3) - parseFloat(s.entry)).toFixed(2)}` },
    { l: 'Quantity',         v: `${s.qty} shares`,  c: '#f0a500' },
    { l: 'Capital Required', v: `₹${Number(s.cap_needed).toLocaleString()}`, c: '#d8ddf0' },
    { l: 'Max Risk',         v: `₹${s.risk_amt}`,   c: '#ff4d6a' },
    { l: 'Potential P&L',    v: `₹${s.pot_pnl}`,    c: '#00d4a0' },
    { l: 'VWAP at Signal',   v: `₹${s.vwap}`,       c: '#00d4a0' },
    { l: 'EMA9 at Signal',   v: `₹${s.ema9}`,       c: '#7c9dff' },
    { l: 'EMA21 at Signal',  v: `₹${s.ema21}`,      c: '#ff9f45' },
    { l: 'ATR (14)',         v: `₹${s.atr}`,        c: '#3d4565' },
  ];

  // V2 fields
  if (s.grade)        items.push({ l: 'Grade',         v: s.grade,        c: gradeColor(s.grade) });
  if (s.regime)       items.push({ l: 'Market Regime',  v: s.regime,       c: '#c084fc' });
  if (s.htf_5m)       items.push({ l: 'HTF 5-min',      v: s.htf_5m,       c: s.htf_5m === 'BULLISH' ? '#00d4a0' : s.htf_5m === 'BEARISH' ? '#ff4d6a' : '#3d4565' });
  if (s.htf_15m)      items.push({ l: 'HTF 15-min',     v: s.htf_15m,      c: s.htf_15m === 'BULLISH' ? '#00d4a0' : s.htf_15m === 'BEARISH' ? '#ff4d6a' : '#3d4565' });
  if (s.momentum)     items.push({ l: 'Momentum',       v: `${s.momentum}/100`, c: '#f0a500' });
  if (s.time_window)  items.push({ l: 'Time Window',    v: s.time_window,       c: '#7c9dff' });
  if (s.sr_level)     items.push({ l: 'Nearby S/R',     v: `₹${s.sr_level}`,   c: '#f0a500' });
  if (s.size_pct)     items.push({ l: 'Capital Used',   v: `${s.size_pct}%`,    c: '#d8ddf0' });

  return items.map(it => `
    <div class="sdg-item">
      <label>${it.l}</label>
      <div class="sdg-val" style="color:${it.c}">${it.v}</div>
      ${it.note ? `<div class="sdg-note">${it.note}</div>` : ''}
    </div>
  `).join('');
}

function gradeColor(grade) {
  return { A: '#00d4a0', B: '#7c9dff', C: '#f0a500', D: '#ff9f45', F: '#ff4d6a' }[grade] || '#3d4565';
}

// ── Backtest ──────────────────────────────────────────────────────────────────
async function runBacktest() {
  if (!State.sessionId) return;
  try {
    const config = getStratConfig();
    const result = await api('POST', `/api/backtest/${State.sessionId}`, { strategies: config });
    renderBacktestResults(result);
  } catch (e) {
    console.warn('Backtest error:', e);
  }
}

function renderBacktestResults(result) {
  const s = result.summary;
  if (!s || s.total_trades === 0) return;

  // Update journal stats with backtest data if no manual journal
  const jstTotal  = $('jst-total');
  const jstWins   = $('jst-wins');
  const jstLosses = $('jst-losses');
  const jstWR     = $('jst-wr');
  const jstPnl    = $('jst-pnl');

  // Create/update a backtest summary panel in signals tab
  let panel = document.getElementById('backtest-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'backtest-panel';
    panel.style.cssText = 'flex-shrink:0; margin-bottom:12px;';
    const sigList = $('signals-list');
    sigList.parentElement.insertBefore(panel, sigList);
  }

  const pnlColor = s.total_pnl >= 0 ? '#00d4a0' : '#ff4d6a';
  const pfColor  = s.profit_factor >= 1.5 ? '#00d4a0' : s.profit_factor >= 1 ? '#f0a500' : '#ff4d6a';

  // Grade breakdown
  const gradeHTML = Object.entries(s.grade_breakdown || {})
    .sort(([a],[b]) => a.localeCompare(b))
    .map(([g, d]) => {
      const gc = gradeColor(g);
      return `<span style="display:inline-flex;align-items:center;gap:4px;background:${gc}18;border:1px solid ${gc}40;color:${gc};padding:2px 8px;border-radius:3px;font-size:10px">
        Grade ${g}: ${d.trades} trades, ${d.win_rate}% WR, ₹${d.pnl}
      </span>`;
    }).join(' ');

  // Exit reasons
  const exitHTML = Object.entries(s.exit_reasons || {}).map(([r, d]) =>
    `<span style="color:#3d4565;font-size:10px;margin-right:10px">${r}: ${d.count} (₹${d.pnl})</span>`
  ).join('');

  panel.innerHTML = `
    <div style="background:#0d0f18;border:1px solid #1c2035;border-radius:6px;padding:14px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <span style="color:#f0a500;font-size:11px;font-weight:700;letter-spacing:2px">📊 BACKTEST RESULTS</span>
        <span style="color:#3d4565;font-size:10px">(walk-forward simulation on loaded data)</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin-bottom:12px">
        ${[
          ['Trades',      s.total_trades,   '#d8ddf0'],
          ['Wins',        s.wins,           '#00d4a0'],
          ['Losses',      s.losses,         '#ff4d6a'],
          ['Win Rate',    `${s.win_rate}%`, s.win_rate >= 55 ? '#00d4a0' : s.win_rate >= 45 ? '#f0a500' : '#ff4d6a'],
          ['Total P&L',   `₹${s.total_pnl}`, pnlColor],
          ['Avg Win',     `₹${s.avg_win}`,  '#00d4a0'],
          ['Avg Loss',    `₹${s.avg_loss}`, '#ff4d6a'],
          ['Expectancy',  `₹${s.expectancy}`, s.expectancy > 0 ? '#00d4a0' : '#ff4d6a'],
          ['Profit Factor', s.profit_factor, pfColor],
          ['Max DD',       `₹${s.max_drawdown}`, '#ff4d6a'],
          ['Consec Losses', s.max_consecutive_losses, '#ff9f45'],
          ['Return %',    `${s.return_pct}%`, pnlColor],
        ].map(([l, v, c]) => `
          <div style="background:#08090d;border:1px solid #1c2035;border-radius:4px;padding:6px;text-align:center">
            <div style="color:#3d4565;font-size:9px;letter-spacing:1px">${l}</div>
            <div style="color:${c};font-size:14px;font-weight:700">${v}</div>
          </div>
        `).join('')}
      </div>
      <div style="margin-bottom:8px">${gradeHTML}</div>
      <div>${exitHTML}</div>
    </div>
  `;
}

// ── API calls ─────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'API error');
  return data;
}

async function runAnalysis() {
  if (!State.sessionId) return;
  const config = getStratConfig();
  // Use V2 enhanced engine
  const result = await api('POST', `/api/analyze-v2/${State.sessionId}`, { strategies: config });
  State.signals = result.signals;
  renderSignals(State.signals);
  if (result.regime) State.regime = result.regime;
  if (result.gap)    State.gap    = result.gap;

  // Refresh chart data to get updated signals
  const cd = await api('GET', `/api/chart-data/${State.sessionId}`);
  renderChart(cd.candles, cd.signals, cd.orb);
  updateTopbar(cd);

  // Auto-run backtest
  runBacktest();
}

async function loadChartAndSignals(sessionId) {
  const data = await api('GET', `/api/chart-data/${sessionId}`);
  State.chartData = data.candles;
  State.signals   = data.signals;
  State.orb       = data.orb;

  renderChart(data.candles, data.signals, data.orb);
  renderSignals(data.signals);
  updateTopbar(data);

  $('btn-analyze').disabled = false;
  $('demo-note').style.display = 'none';
  $('badge-mode').textContent = data.session?.stock_name || 'LIVE';
  $('badge-mode').style.color = '#00d4a0';
}

// ── Upload + analyze ──────────────────────────────────────────────────────────
async function uploadAndAnalyze() {
  const cashCSV    = $('csv-cash').value.trim();
  const futCSV     = $('csv-futures').value.trim();
  const stockName  = $('inp-stock').value.trim() || 'STOCK';
  const capital    = parseFloat($('inp-capital').value) || 25000;
  const risk       = parseFloat($('inp-risk').value) || 500;

  if (!cashCSV) {
    showError('Please paste your cash segment CSV data first.');
    return;
  }

  hideError();

  try {
    const uploadRes = await api('POST', '/api/upload', {
      stock_name: stockName, capital, risk,
      cash_csv: cashCSV, futures_csv: futCSV,
    });

    State.sessionId = uploadRes.session_id;
    await runAnalysis();
    switchTab('chart');
    loadSessionList();
  } catch (err) {
    showError(err.message);
  }
}

// ── Session list ──────────────────────────────────────────────────────────────
async function loadSessionList() {
  const sessions = await api('GET', '/api/sessions');
  const sel = $('session-select');
  sel.innerHTML = '<option value="">— Sessions —</option>' +
    sessions.map(s => `<option value="${s.id}">${s.stock_name} (${s.date}) — ${s.candle_count} candles</option>`).join('');
}

// ── Journal ───────────────────────────────────────────────────────────────────
async function loadJournal() {
  const sessionId = State.sessionId;
  const entries   = await api('GET', `/api/journal${sessionId ? `?session_id=${sessionId}` : ''}`);
  renderJournal(entries);

  if (sessionId) {
    const stats = await api('GET', `/api/stats/${sessionId}`);
    $('jst-total').textContent  = stats.total_trades;
    $('jst-wins').textContent   = stats.wins;
    $('jst-losses').textContent = stats.losses;
    $('jst-wr').textContent     = `${stats.win_rate}%`;
    const pnl = stats.total_pnl;
    $('jst-pnl').textContent    = `${pnl >= 0 ? '+' : ''}₹${pnl.toLocaleString()}`;
    $('jst-pnl').style.color    = pnl >= 0 ? '#00d4a0' : '#ff4d6a';
  }
}

function renderJournal(entries) {
  const tbody = $('journal-tbody');
  const empty = $('journal-empty');
  const table = $('journal-table');

  if (!entries.length) {
    empty.style.display = '';
    table.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  table.style.display = '';

  tbody.innerHTML = entries.map(e => {
    const pnl    = e.net_pnl != null ? parseFloat(e.net_pnl) : null;
    const pnlStr = pnl != null ? `${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(0)}` : '—';
    const pnlCol = pnl == null ? '' : pnl >= 0 ? 'val-green' : 'val-red';
    const rawPnl = e.pnl != null ? `${parseFloat(e.pnl) >= 0 ? '+' : ''}₹${parseFloat(e.pnl).toFixed(0)}` : '—';
    const outcomeClass = {
      WIN:'outcome-win', LOSS:'outcome-loss', PARTIAL:'outcome-partial',
      BE:'outcome-be', MISSED:'outcome-missed',
    }[e.outcome] || '';

    return `<tr>
      <td>${e.trade_date || '—'}</td>
      <td>${e.stock_name || '—'}</td>
      <td style="color:${e.type==='BUY'?'#00d4a0':'#ff4d6a'}; font-weight:700">${e.type || '—'}</td>
      <td>₹${e.entry || '—'}</td>
      <td>₹${e.exit_price || '—'}</td>
      <td>${e.qty || '—'}</td>
      <td>${rawPnl}</td>
      <td class="${pnlCol}" style="font-weight:700">${pnlStr}</td>
      <td class="${outcomeClass}">${e.outcome || '—'}</td>
      <td style="color:#3d4565; max-width:180px; overflow:hidden; text-overflow:ellipsis">${e.notes || ''}</td>
      <td><button class="del-btn" data-id="${e.id}">✕</button></td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this journal entry?')) return;
      await api('DELETE', `/api/journal/${btn.dataset.id}`);
      loadJournal();
    });
  });
}

function prefillJournalForm(sig) {
  $('jf-stock').value   = $('inp-stock').value;
  $('jf-type').value    = sig.type;
  $('jf-entry').value   = sig.entry;
  $('jf-sl').value      = sig.sl;
  $('jf-target').value  = sig.target;
  $('jf-qty').value     = sig.qty;
  $('jf-date').value    = new Date().toISOString().split('T')[0];
}

// ── Demo data ─────────────────────────────────────────────────────────────────
function generateDemo() {
  // Generate realistic 1-min candles and push to server
  let price = 724.50;
  const rows = ['datetime,open,high,low,close,volume'];
  const futRows = ['datetime,open,high,low,close,volume'];
  const phases = [
    [15, 0.007, -0.0005, 180000],
    [3,  0.008,  0.006,  350000],
    [60, 0.002,  0.0008,  70000],
    [45, 0.001,  0,       40000],
    [30, 0.004, -0.002,   90000],
    [40, 0.002,  0.001,   55000],
    [60, 0.002, -0.0003,  45000],
    [30, 0.003,  0.0005,  95000],
    [15, 0.004, -0.001,  140000],
  ];
  let hour = 9, min = 15;
  for (const [len, vol, trend, baseVol] of phases) {
    for (let i = 0; i < len; i++) {
      const chg = (Math.random() - 0.5) * 2 * vol + trend;
      const open = price;
      price = price * (1 + chg);
      const wick = vol * 0.8;
      const high = Math.max(open, price) * (1 + Math.random() * wick);
      const lw   = Math.min(open, price) * (1 - Math.random() * wick);
      const volume = Math.floor(baseVol * (0.6 + Math.random() * 0.8));
      const time = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`;
      rows.push(`${time},${open.toFixed(2)},${high.toFixed(2)},${lw.toFixed(2)},${price.toFixed(2)},${volume}`);
      const prem = 3.8 + (Math.random()-0.5)*2;
      futRows.push(`${time},${(open+prem).toFixed(2)},${(high+prem).toFixed(2)},${(lw+prem).toFixed(2)},${(price+prem).toFixed(2)},${Math.floor(volume*0.35)}`);
      min++;
      if (min >= 60) { min = 0; hour++; }
    }
  }
  $('csv-cash').value    = rows.join('\n');
  $('csv-futures').value = futRows.join('\n');
  $('inp-stock').value   = 'DEMO';
  document.querySelector('.strat-row[data-key="futures"] input').checked = true;
  updateStrategyRows();
}

// ── Error helpers ─────────────────────────────────────────────────────────────
function showError(msg) {
  const box = $('upload-error');
  box.textContent = `⚠ ${msg}`;
  box.style.display = '';
}
function hideError() {
  $('upload-error').style.display = 'none';
}

// ── Update strategy row styles ────────────────────────────────────────────────
function updateStrategyRows() {
  document.querySelectorAll('.strat-row').forEach(row => {
    const chk   = row.querySelector('input[type="checkbox"]');
    const color = row.dataset.color;
    row.classList.toggle('active', chk.checked);
    row.style.color = chk.checked ? color : '';
    row.style.background = chk.checked ? `${color}12` : '';
    row.style.borderColor = chk.checked ? `${color}40` : 'transparent';
  });
}

// ══ INIT ══════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {

  // Strategy checkboxes
  document.querySelectorAll('.strat-row').forEach(row => {
    const chk = row.querySelector('input[type="checkbox"]');
    updateStrategyRows(); // initial
    row.addEventListener('click', (e) => {
      if (e.target !== chk) chk.checked = !chk.checked;
      updateStrategyRows();
      if (State.sessionId) runAnalysis();
    });
  });

  // Tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Risk inputs
  $('inp-capital').addEventListener('input', updateRiskDisplay);
  $('inp-risk').addEventListener('input', updateRiskDisplay);
  updateRiskDisplay();

  // Analyze button (sidebar)
  $('btn-analyze').addEventListener('click', runAnalysis);

  // Upload button
  $('btn-upload').addEventListener('click', uploadAndAnalyze);

  // Demo button
  $('btn-demo').addEventListener('click', () => {
    generateDemo();
    uploadAndAnalyze();
  });

  // Session select
  $('session-select').addEventListener('change', async (e) => {
    if (!e.target.value) return;
    State.sessionId = parseInt(e.target.value);
    $('inp-stock').value = e.target.options[e.target.selectedIndex].text.split(' ')[0];
    await loadChartAndSignals(State.sessionId);
  });

  // Journal add/cancel
  $('btn-add-trade').addEventListener('click', () => {
    $('trade-form').style.display = '';
    $('jf-date').value = new Date().toISOString().split('T')[0];
    $('jf-stock').value = $('inp-stock').value;
  });
  $('btn-cancel-trade').addEventListener('click', () => {
    $('trade-form').style.display = 'none';
  });

  // Journal save
  $('btn-save-trade').addEventListener('click', async () => {
    const entry = {
      session_id:  State.sessionId,
      stock_name:  $('jf-stock').value,
      trade_date:  $('jf-date').value,
      type:        $('jf-type').value,
      entry:       parseFloat($('jf-entry').value) || null,
      exit_price:  parseFloat($('jf-exit').value)  || null,
      qty:         parseInt($('jf-qty').value)      || null,
      sl:          parseFloat($('jf-sl').value)     || null,
      target:      parseFloat($('jf-target').value) || null,
      outcome:     $('jf-outcome').value,
      notes:       $('jf-notes').value,
    };
    await api('POST', '/api/journal', entry);
    $('trade-form').style.display = 'none';
    loadJournal();
  });

  // Modal close
  $('modal-close').addEventListener('click', () => { $('modal-overlay').style.display = 'none'; });
  $('modal-overlay').addEventListener('click', e => { if (e.target === $('modal-overlay')) $('modal-overlay').style.display = 'none'; });

  // Initialize charts
  initCharts();

  // Load session list
  loadSessionList();

  // Load demo on start
  generateDemo();
  uploadAndAnalyze();
});
