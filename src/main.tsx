import { lazy, StrictMode, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App.tsx';
import './index.css';
import SkeletonLoader from './components/SkeletonLoader';
import { TonConnectUIProvider } from '@tonconnect/ui-react';
import { initWagmi } from './wagmiConfig';

const queryClient = new QueryClient();

// The heavy wallet stack (Wagmi/RainbowKit/AppKit) is lazy-loaded in its own
// async chunk and only mounted once the wagmi config is ready — so the app shell
// paints before the wallet bundle finishes loading.
const WalletLayer = lazy(() =>
  import('./wallet/WalletLayer').then((m) => ({ default: m.WalletLayer })),
);

const WAGMI_TIMEOUT_MS = 3000;

function Root() {
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [config, setConfig] = useState<any>(null);

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      if (!alive) return;
      setStatus((s) => (s === 'loading' ? 'failed' : s));
    }, WAGMI_TIMEOUT_MS);

    initWagmi()
      .then((cfg) => {
        if (!alive) return;
        setConfig(cfg);
        setStatus('ready');
      })
      .catch(() => {
        if (alive) setStatus('failed');
      })
      .finally(() => clearTimeout(timer));

    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);

  // While wagmi config is being fetched, show the branded full-screen skeleton.
  if (status === 'loading') {
    return <SkeletonLoader />;
  }

  if (status === 'ready' && config) {
    return (
      // While the lazy wallet chunk loads, paint <App/> immediately (Wallet tab
      // shows its buffering state); App remounts once under the providers in the
      // boot window. Skeleton stays only during the brief config fetch above.
      <Suspense fallback={<App walletReady={false} />}>
        <WalletLayer config={config}>
          <App walletReady />
        </WalletLayer>
      </Suspense>
    );
  }

  // init failed or timed out → render the app immediately without the wallet layer.
  return <App walletReady={false} />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TonConnectUIProvider manifestUrl="/tonconnect.json">
        <Root />
      </TonConnectUIProvider>
    </QueryClientProvider>
  </StrictMode>,
);
