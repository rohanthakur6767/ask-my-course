import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server runs on 5173, which the Django CORS settings already allow.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
