import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    build: {
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          // Split 3rd-party libs into cached vendor chunks (parallel load +
          // long-term caching) so the app shell loads fast in the Telegram webview.
          manualChunks(id) {
            const mod = id.replace(/\\/g, '/');
            if (!mod.includes('node_modules')) return;
            if (/(\/react\/|react-dom|scheduler)/.test(mod)) return 'react-vendor';
            if (/(\/wagmi\/|\/@wagmi\/|\/viem\/)/.test(mod)) return 'wagmi';
            if (
              /\/(@rainbow-me|\/@reown\/|\/@coinbase\/|\/@walletconnect\/|\/@base-org\/|\/porto\/|from-external)/.test(mod) ||
              /\/@reown\/appkit\/dist/.test(mod)
            ) {
              return 'wallet';
            }
            if (/\/(@tanstack\/)/.test(mod)) return 'query';
            if (/\/lightweight-charts\//.test(mod)) return 'charts';
            if (/\/lucide-react\//.test(mod)) return 'icons';
            if (/\/motion\//.test(mod)) return 'motion';
            // NOTE: no dedicated `ox` chunk — ox/viem are pulled into the wagmi
            // chunk to avoid a circular ox -> wagmi -> ox dependency warning.
          },
        },
      },
    },
    server: {
      hmr: true,
      watch: {},
    },
  };
});
