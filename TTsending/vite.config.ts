import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // 如果需要 WebSocket 支持，可以添加以下配置
        // ws: true,
      }
    }
  },
  preview: {
    host: 'localhost',
    port: 5173
  }
})
