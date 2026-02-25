import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("lightweight-charts")) return "lightweight-charts"
          if (id.includes("@radix-ui")) return "radix-ui"
          if (
            id.includes("react-dom") ||
            id.includes("react-router") ||
            id.includes("scheduler")
          )
            return "react-vendor"
          if (id.includes("@tanstack")) return "tanstack"
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
})
