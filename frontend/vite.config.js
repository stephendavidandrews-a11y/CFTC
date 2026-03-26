import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/tracker": {
        target: "http://localhost:8004",
        changeOrigin: true,
      },
      "/ai": {
        target: "http://localhost:8006",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
