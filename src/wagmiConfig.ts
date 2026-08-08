import { createConfig, http } from 'wagmi';
import { injected, walletConnect } from 'wagmi/connectors';
import { mainnet, bsc, polygon } from 'wagmi/chains';

let _wagmiConfig: ReturnType<typeof createConfig> | null = null;

export interface AppConfig {
  walletConnect?: { projectId: string | null };
  frontendUrl: string | null;
}

/** Fetch app config from backend. Returns fallback if unavailable. */
async function fetchAppConfig(): Promise<AppConfig> {
  try {
    const base = import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? '';
    const res = await fetch(`${base}/api/config`, { cache: 'no-store' });
    if (res.ok) {
      const json = await res.json();
      return json as AppConfig;
    }
  } catch {}
  // Graceful fallback
  return {
    walletConnect: { projectId: import.meta.env.VITE_WALLET_CONNECT_PROJECT_ID || null },
    frontendUrl: null,
  };
}

/** Create wagmi config — call after fetching app config. */
export function buildWagmiConfig(appConfig: AppConfig) {
  const projectId = appConfig.walletConnect?.projectId;
  const frontendUrl = appConfig.frontendUrl ?? 'https://aegis-quant.vercel.app';

  return createConfig({
    chains: [mainnet, bsc, polygon],
    transports: {
      [mainnet.id]: http(),
      [bsc.id]: http(),
      [polygon.id]: http(),
    },
    connectors: [
      injected(),
      ...(projectId ? [
        walletConnect({
          projectId,
          metadata: {
            name: 'Aegis Quant',
            description: 'AI-Powered Crypto Trading Platform',
            url: frontendUrl,
            icons: [`${frontendUrl}/icon.png`],
          },
        }),
      ] : []),
    ],
  });
}

/** Async init — call once at app startup before rendering WagmiProvider. */
export async function initWagmi(): Promise<ReturnType<typeof createConfig>> {
  if (_wagmiConfig) return _wagmiConfig;
  const config = await fetchAppConfig();
  _wagmiConfig = buildWagmiConfig(config);
  return _wagmiConfig;
}
