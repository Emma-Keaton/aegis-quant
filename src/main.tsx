import React, { useState, useEffect } from 'react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App.tsx';
import './index.css';
import { WagmiProvider } from 'wagmi';
import { RainbowKitProvider } from '@rainbow-me/rainbowkit';
import { initWagmi } from './wagmiConfig';

const queryClient = new QueryClient();

/** Minimal boot screen — keeps the page alive while wagmi configures itself. */
function BootScreen() {
  const [stage, setStage] = useState<string>('');
  useEffect(() => {
    const t1 = setTimeout(() => setStage('query'), 200);
    const t2 = setTimeout(() => setStage('wagmi'), 600);
    const t3 = setTimeout(() => setStage('done'), 1400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);
  return (
    <div className="min-h-screen bg-[#101416] flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 mx-auto border-2 border-[#c6ff34] border-t-transparent rounded-full animate-spin" />
        <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{stage || 'boot'}</p>
      </div>
    </div>
  );
}

let _root: ReturnType<typeof createRoot> | null = null;
let _rendered = false;

async function renderApp(wagmiConfig: any) {
  if (_rendered) return;
  _rendered = true;
  _root!.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <WagmiProvider config={wagmiConfig}>
          <RainbowKitProvider>
            <App />
          </RainbowKitProvider>
        </WagmiProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
}

function renderFallback() {
  if (_rendered) return;
  _rendered = true;
  _root!.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
}

_root = createRoot(document.getElementById('root')!);
_root.render(<BootScreen />);

const WAGMI_TIMEOUT_MS = 3000;

initWagmi()
  .then((cfg) => renderApp(cfg))
  .catch((err) => {
    console.error('[Wagmi] Init failed, rendering without wallet connect:', err);
    renderFallback();
  })
  .finally(() => {
    // Safety net: if init hangs beyond timeout, fall back anyway
    setTimeout(() => {
      if (!_rendered) {
        console.warn('[Wagmi] Timed out after', WAGMI_TIMEOUT_MS, 'ms — falling back');
        renderFallback();
      }
    }, WAGMI_TIMEOUT_MS);
  });
