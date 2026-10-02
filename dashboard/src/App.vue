<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useMarketStore } from "./stores/market";
import { useMarketWebSocket } from "./composables/useMarketWebSocket";
import { getPrediction } from "./services/api";

const store = useMarketStore();
useMarketWebSocket();
const chart = ref<HTMLCanvasElement | null>(null);
const chartTooltip = ref({ visible: false, x: 0, y: 0, time: "", price: 0 });

const priceChange = computed(() => {
  const h = store.history;
  if (h.length < 2) return 0;
  const previous = h[Math.max(0, h.length - 21)].price;
  return ((h[h.length - 1].price - previous) / previous) * 100;
});

const directionLabel = computed(() => ({
  UP: "Alta",
  DOWN: "Baixa",
  SIDEWAYS: "Lateral"
}[store.prediction?.direction ?? "SIDEWAYS"]));

function money(value: number | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function compact(value: number | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("pt-BR", {
    notation: "compact",
    maximumFractionDigits: 2
  }).format(value);
}

function pct(value: number | undefined) {
  if (value == null) return "—";
  return (value * 100).toFixed(4) + "%";
}

function formatChartTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function chartPoint(index: number) {
  const c = chart.value;
  const history = store.history;
  if (!c || history.length < 2) return null;
  const rect = c.getBoundingClientRect();
  const pad = 18;
  const prices = history.map(x => x.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const p = history[index].price;
  return {
    x: pad + (rect.width - pad * 2) * index / (history.length - 1),
    y: rect.height - pad - ((p - min) / Math.max(max - min, 0.000001)) * (rect.height - pad * 2)
  };
}

function handleChartMove(event: MouseEvent) {
  const c = chart.value;
  if (!c || store.history.length < 2) return;
  const rect = c.getBoundingClientRect();
  const pad = 18;
  const usableWidth = rect.width - pad * 2;
  const raw = Math.round(((event.clientX - rect.left - pad) / usableWidth) * (store.history.length - 1));
  const index = Math.max(0, Math.min(store.history.length - 1, raw));
  const point = chartPoint(index);
  if (!point) return;
  chartTooltip.value = {
    visible: true,
    x: point.x,
    y: point.y,
    time: formatChartTime(store.history[index].ts),
    price: store.history[index].price
  };
  drawChart(index);
}

function hideChartTooltip() {
  chartTooltip.value.visible = false;
  drawChart();
}

function drawChart(activeIndex?: number) {
  const c = chart.value;
  if (!c || store.history.length < 2) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = c.getBoundingClientRect();
  c.width = rect.width * dpr;
  c.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;
  const pad = 18;
  const prices = store.history.map(x => x.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#263044";
  ctx.lineWidth = 1;

  for (let i = 1; i < 5; i++) {
    const y = pad + (h - pad * 2) * i / 5;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  ctx.beginPath();
  prices.forEach((p, i) => {
    const x = pad + (w - pad * 2) * i / (prices.length - 1);
    const y = h - pad - ((p - min) / Math.max(max - min, 0.000001)) * (h - pad * 2);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });

  ctx.strokeStyle = "#7dd3fc";
  ctx.lineWidth = 2;
  ctx.stroke();
}

onMounted(async () => {
  await store.load();

  if (!store.prediction) {
    try {
      store.prediction = await getPrediction();
    } catch {}
  }

  drawChart();
  window.addEventListener("resize", () => drawChart());
});
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <span class="eyebrow">BTC / USDT</span>
        <h1>Inteligência de Mercado NN</h1>
      </div>

      <div class="live" :class="{ offline: !store.connected }">
        <span class="dot"></span>{{ store.connected ? "AO VIVO" : "CONECTANDO" }}
      </div>
    </header>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <section class="hero card">
      <div>
        <span class="label">Preço atual</span>
        <div class="price">{{ money(store.snapshot?.price) }}</div>
        <span :class="['change', priceChange >= 0 ? 'up' : 'down']">
          {{ priceChange >= 0 ? "+" : "" }}{{ priceChange.toFixed(3) }}% · período recente
        </span>
      </div>

      <div class="hero-meta">
        <div>
          <span>Volume em 24h</span>
          <strong>{{ compact(store.snapshot?.volume_24h) }}</strong>
        </div>
        <div>
          <span>Interesse em aberto</span>
          <strong>{{ compact(store.snapshot?.open_interest) }}</strong>
        </div>
        <div>
          <span>Taxa de financiamento</span>
          <strong>{{ pct(store.snapshot?.funding_rate) }}</strong>
        </div>
        <div>
          <span>Diferença de preço</span>
          <strong>{{ store.snapshot ? store.snapshot.spread.toFixed(2) : "—" }}</strong>
        </div>
      </div>
    </section>

    <section class="grid">
      <article class="card chart-card">
        <div class="section-head">
          <div>
            <span class="label">Movimento do preço</span>
            <h2>Histórico em tempo real</h2>
          </div>
          <span class="badge">Coleta a cada 15 segundos</span>
        </div>
        <div class="chart-wrap" @mousemove="handleChartMove" @mouseleave="hideChartTooltip">
          <canvas ref="chart"></canvas>
          <div v-if="chartTooltip.visible" class="chart-tooltip" :style="{ left: `${chartTooltip.x}px`, top: `${chartTooltip.y}px` }">
            <span>{{ chartTooltip.time }}</span>
            <strong>{{ money(chartTooltip.price) }}</strong>
          </div>
        </div>
      </article>

      <article class="card book-card">
        <div class="section-head">
          <div>
            <span class="label">Liquidez</span>
            <h2>Melhores ofertas</h2>
          </div>
        </div>

        <div class="quote bid">
          <span>Compra</span>
          <strong>{{ money(store.snapshot?.bid) }}</strong>
        </div>

        <div class="quote ask">
          <span>Venda</span>
          <strong>{{ money(store.snapshot?.ask) }}</strong>
        </div>

        <div class="liquidity">
          <div>
            <span>Volume de compra</span>
            <strong>{{ compact(store.snapshot?.bid_volume) }}</strong>
          </div>
          <div>
            <span>Volume de venda</span>
            <strong>{{ compact(store.snapshot?.ask_volume) }}</strong>
          </div>
        </div>

        <div class="imbalance">
          <span>Desequilíbrio do livro de ofertas</span>
          <strong>{{ (store.imbalance * 100).toFixed(2) }}%</strong>
        </div>
      </article>
    </section>

    <section class="grid lower">
      <article class="card" style="padding: 20px;">
        <div class="section-head">
          <div>
            <span class="label">Derivativos</span>
            <h2>Indicadores do mercado</h2>
          </div>
        </div>

        <div class="metrics">
          <div>
            <span>Taxa de financiamento</span>
            <strong>{{ pct(store.snapshot?.funding_rate) }}</strong>
          </div>
          <div>
            <span>Interesse em aberto</span>
            <strong>{{ compact(store.snapshot?.open_interest) }}</strong>
          </div>
          <div>
            <span>Diferença de preço (bps)</span>
            <strong>{{ store.snapshot ? ((store.snapshot.spread / store.snapshot.price) * 10000).toFixed(3) : "—" }}</strong>
          </div>
          <div>
            <span>Liquidações compradas</span>
            <strong>{{ compact(store.snapshot?.liquidation_long) }}</strong>
          </div>
          <div>
            <span>Liquidações vendidas</span>
            <strong>{{ compact(store.snapshot?.liquidation_short) }}</strong>
          </div>
        </div>
      </article>

      <article class="card prediction">
        <div class="section-head">
          <div>
            <span class="label">Modelo de referência</span>
            <h2>Previsão para 4 horas</h2>
          </div>
          <span class="badge warning">Educacional</span>
        </div>

        <template v-if="store.prediction">
          <div class="prediction-main">
            <strong>{{ money(store.prediction.predicted_price) }}</strong>
            <span>{{ directionLabel }}</span>
          </div>

          <div class="prediction-grid">
            <div>
              <span>Retorno estimado</span>
              <b>{{ (store.prediction.predicted_return * 100).toFixed(2) }}%</b>
            </div>
            <div>
              <span>Quantidade de amostras</span>
              <b>{{ store.prediction.samples }}</b>
            </div>
          </div>

          <small>{{ store.prediction.warning }}</small>
        </template>

        <div v-else class="muted">Aguardando histórico suficiente...</div>
      </article>
    </section>

    <footer>geovanecodder@gmail.com - <a href="https://geovane-ashen.vercel.app" target="_blank">Portifólio</a></footer>
  </main>
</template>
