import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { Prediction, Snapshot } from "../types";
import { getHistory, getPrediction, getSnapshot } from "../services/api";

export const useMarketStore = defineStore("market", () => {
  const snapshot = ref<Snapshot | null>(null);
  const history = ref<Snapshot[]>([]);
  const prediction = ref<Prediction | null>(null);
  const connected = ref(false);
  const loading = ref(true);
  const error = ref("");

  const imbalance = computed(() => {
    if (!snapshot.value) return 0;
    const total = snapshot.value.bid_volume + snapshot.value.ask_volume;
    return total ? (snapshot.value.bid_volume - snapshot.value.ask_volume) / total : 0;
  });

  async function load() {
    loading.value = true;
    error.value = "";
    try {
      const [s, h, p] = await Promise.all([
        getSnapshot(),
        getHistory(),
        getPrediction()
      ]);
      if ("status" in s) snapshot.value = null;
      else snapshot.value = s;
      history.value = h;
      if (!("status" in p)) prediction.value = p;
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Erro desconhecido";
    } finally {
      loading.value = false;
    }
  }

  function applySnapshot(next: Snapshot) {
    snapshot.value = next;
    history.value = [...history.value, next].slice(-300);
  }

  return {
    snapshot, history, prediction, connected, loading, error, imbalance,
    load, applySnapshot
  };
});
