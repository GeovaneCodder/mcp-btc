import { onBeforeUnmount, onMounted } from "vue";
import { useMarketStore } from "../stores/market";
import type { Snapshot } from "../types";

export function useMarketWebSocket() {
  const store = useMarketStore();
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(protocol + "://" + location.host + "/ws/market");

    socket.onopen = () => { store.connected = true; };
    socket.onmessage = event => {
      try {
        const payload = JSON.parse(event.data) as Snapshot;
        if (payload.price) store.applySnapshot(payload);
      } catch {}
    };
    socket.onclose = () => {
      store.connected = false;
      retry = setTimeout(connect, 2000);
    };
    socket.onerror = () => socket?.close();
  }

  onMounted(connect);
  onBeforeUnmount(() => {
    if (retry) clearTimeout(retry);
    socket?.close();
  });
}
