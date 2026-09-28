import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

// https://vite.dev/config/
// https://vite.dev/config/
export default defineConfig(({ command }) => {
  let httpsConfig = undefined;

  // Only attempt to load certs in serve mode (local dev)
  if (command === 'serve') {
    const keyPath = path.resolve(__dirname, '../../server/key.pem');
    const certPath = path.resolve(__dirname, '../../server/cert.pem');

    if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
      httpsConfig = {
        key: fs.readFileSync(keyPath),
        cert: fs.readFileSync(certPath),
      };
    }
  }

  return {
    plugins: [react()],
    server: {
      https: httpsConfig,
      port: 5173,
    },
  };
})
