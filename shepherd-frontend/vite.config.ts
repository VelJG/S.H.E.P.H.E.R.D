import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api/yolo': {
          target: env.VITE_YOLO_TARGET || 'http://100.83.240.13:8080',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/yolo/, ''),
        },
        '/api/tracker': {
          target: env.VITE_TRACKER_TARGET || 'http://100.83.240.13:8090',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/tracker/, ''),
        },
      },
    },
  };
});