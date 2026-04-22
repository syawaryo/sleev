import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // VITE_API_PROXY_TARGET lets docker-compose point the proxy at the
  // backend service (e.g. http://api:8000) while local runs default to
  // http://localhost:8000.
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      host: true, // listen on 0.0.0.0 so docker can expose it
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
      // HMR over docker: the browser sits outside docker so it connects
      // back to localhost:5173, not the container hostname.
      hmr: {
        clientPort: 5173,
      },
    },
  }
})
