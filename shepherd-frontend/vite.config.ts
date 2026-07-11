import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Separate app from shepherd-infra. Builds to dist/ which can later be
// uploaded to the aabw-shepherd-frontend S3 bucket + CloudFront.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
