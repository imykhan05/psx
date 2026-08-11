import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// host:true exposes the dev server on the LAN so the same UI can be opened on a
// phone during development (the mobile app will reuse this UX).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
});
