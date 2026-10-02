import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    watch: {
      usePolling: true,
      interval: 300
    },
    proxy: {
      "/api": {
        target: "http://dashboard:8080",
        changeOrigin: true
      },
      "/ws": {
        target: "ws://dashboard:8080",
        ws: true
      }
    }
  }
});
