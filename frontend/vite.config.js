import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react({ include: /\.(jsx|js)$/ })],
    esbuild: {
      loader: 'jsx',
      include: /src\/.*\.js$/,
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      port: 3200,
      host: '0.0.0.0',
      allowedHosts: true,
      proxy: {
        '/api': {
          target: 'http://localhost:8200',
          changeOrigin: true,
        },
      },
    },
    define: {
      'process.env.REACT_APP_BACKEND_URL': JSON.stringify(''),
    },
  }
})
