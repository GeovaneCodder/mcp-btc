<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useMarketStore } from "./stores/market";
import { useMarketWebSocket } from "./composables/useMarketWebSocket";
import { getPrediction } from "./services/api";

const store = useMarketStore();
useMarketWebSocket();
const chart = ref<HTMLCanvasElement | null>(null);

const priceChange = computed(() => {
  const h = store.history;
  if (h.length < 2) return 0;
  return ((h[h.length - 1].price - h[Math.max(0, h.length - 21)].price) / h[Math.max(0, h.length - 21)].price) * 100;
});
const directionLabel = computed(() => ({
  UP: "Alta",
  DOWN: "Baixa",
  SIDEWAYS: "Lateral"
}[store.prediction?.direction ?? "SIDEWAYS"]));

function money(value: number | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}
function compact(value: number | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}
function pct(value: number | undefined) {
  if (value == null) return "—";
  return (value * 100).toFixed(4) + "%";
}
function drawChart() {
  const c = chart.value;
  if (!c || store.history.length < 2) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = c.getBoundingClientRect();
  c.width = rect.width * dpr; c.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const w = rect.width, h = rect.height, pad = 18;
  const prices = store.history.map(x => x.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle = "#263044"; ctx.lineWidth = 1;
  for (let i=1;i<5;i++){ const y=pad+(h-pad*2)*i/5; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }
  ctx.beginPath();
  prices.forEach((p,i) => {
    const x = pad + (w-pad*2)*i/(prices.length-1);
    const y = h-pad - ((p-min)/Math.max(max-min, 0.000001))*(h-pad*2);
    i ? ctx.lineTo(x,y) : ctx.moveTo(x,y);
  });
  ctx.strokeStyle = "#7dd3fc"; ctx.lineWidth = 2; ctx.stroke();
}
onMounted(async () => {
  await store.load();
  if (!store.prediction) {
    try { store.prediction = await getPrediction(); } catch {}
  }
  drawChart();
  window.addEventListener("resize", drawChart);
});
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <span class="eyebrow">BTC / USDT</span>
        <h1>Market Intelligence</h1>
      </div>
      <div class="live" :class="{ offline: !store.connected }">
        <span class="dot"></span>{{ store.connected ? "LIVE" : "CONNECTING" }}
      </div>
    </header>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <section class="hero card">
      <div>
        <span class="label">Preço atual</span>
        <div class="price">{{ money(store.snapshot?.price) }}</div>
        <span :class="['change', priceChange >= 0 ? 'up' : 'down']">
          {{ priceChange >= 0 ? "+" : "" }}{{ priceChange.toFixed(3) }}% · janela recente
        </span>
      </div>
      <div class="hero-meta">
        <div><span>24h Volume</span><strong>{{ compact(store.snapshot?.volume_24h) }}</strong></div>
        <div><span>Open Interest</span><strong>{{ compact(store.snapshot?.open_interest) }}</strong></div>
        <div><span>Funding</span><strong>{{ pct(store.snapshot?.funding_rate) }}</strong></div>
        <div><span>Spread</span><strong>{{ store.snapshot ? store.snapshot.spread.toFixed(2) : "—" }}</strong></div>
      </div>
    </section>

    <section class="grid">
      <article class="card chart-card">
        <div class="section-head"><div><span class="label">Price action</span><h2>Histórico em tempo real</h2></div><span class="badge">15s collector</span></div>
        <canvas ref="chart"></canvas>
      </article>

      <article class="card book-card">
        <div class="section-head"><div><span class="label">Liquidity</span><h2>Top of book</h2></div></div>
        <div class="quote bid"><span>Bid</span><strong>{{ money(store.snapshot?.bid) }}</strong></div>
        <div class="quote ask"><span>Ask</span><strong>{{ money(store.snapshot?.ask) }}</strong></div>
        <div class="liquidity"><div><span>Bid volume</span><strong>{{ compact(store.snapshot?.bid_volume) }}</strong></div><div><span>Ask volume</span><strong>{{ compact(store.snapshot?.ask_volume) }}</strong></div></div>
        <div class="imbalance"><span>Order book imbalance</span><strong>{{ (store.imbalance * 100).toFixed(2) }}%</strong></div>
      </article>
    </section>

    <section class="grid lower">
      <article class="card" style="padding: 20px;">
        <div class="section-head"><div><span class="label">Derivatives</span><h2>Market metrics</h2></div></div>
        <div class="metrics">
          <div><span>Funding rate</span><strong>{{ pct(store.snapshot?.funding_rate) }}</strong></div>
          <div><span>Open interest</span><strong>{{ compact(store.snapshot?.open_interest) }}</strong></div>
          <div><span>Spread (bps)</span><strong>{{ store.snapshot ? ((store.snapshot.spread / store.snapshot.price) * 10000).toFixed(3) : "—" }}</strong></div>
          <div><span>Liquid. long</span><strong>{{ compact(store.snapshot?.liquidation_long) }}</strong></div>
          <div><span>Liquid. short</span><strong>{{ compact(store.snapshot?.liquidation_short) }}</strong></div>
        </div>
      </article>

      <article class="card prediction">
        <div class="section-head"><div><span class="label">Baseline model</span><h2>Horizonte de 4h</h2></div><span class="badge warning">educacional</span></div>
        <template v-if="store.prediction">
          <div class="prediction-main"><strong>{{ money(store.prediction.predicted_price) }}</strong><span>{{ directionLabel }}</span></div>
          <div class="prediction-grid"><div><span>Retorno estimado</span><b>{{ (store.prediction.predicted_return * 100).toFixed(2) }}%</b></div><div><span>Amostras</span><b>{{ store.prediction.samples }}</b></div></div>
          <small>{{ store.prediction.warning }}</small>
        </template>
        <div v-else class="muted">Aguardando histórico suficiente...</div>
      </article>
    </section>

    <footer>geovanecodder@gmail.com</footer>
  </main>
</template>
