import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend chạy cổng khác thì đặt BACKEND_URL, ví dụ BACKEND_URL=http://localhost:8010 npm run dev
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
});
