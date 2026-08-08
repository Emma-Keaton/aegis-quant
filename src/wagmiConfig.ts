import { createConfig, http } from 'wagmi';
import { injected } from 'wagmi/connectors';
import { mainnet, bsc, polygon } from 'wagmi/chains';
import {
  connectorsForWallets,
} from '@rainbow-me/rainbowkit';
import {
  bybitWallet,
  okxWallet,
  binanceWallet,
} from '@rainbow-me/rainbowkit/wallets';

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

const APP_NAME = 'Aegis Quant';
const APP_URL_FALLBACK = 'https://aegis-quant.vercel.app';

/** Build wagmi connectors — includes exchange wallets via WalletConnect + injected */
function buildConnectors(projectId: string | null, frontendUrl: string) {
  if (!projectId) {
    // No projectId — only injected wallets (MetaMask etc.)
    return [injected()];
  }

  return connectorsForWallets(
    [
      {
        groupName: 'Exchange Wallets',
        wallets: [bybitWallet, okxWallet, binanceWallet],
      },
      { groupName: 'Recommended', wallets: [] },
      { groupName: 'Other Wallets', wallets: [] },
    ],
    {
      projectId,
      appName: APP_NAME,
      walletConnectParameters: {
        qrModalOptions: {
          themeMode: 'dark',
          themeVariables: {
            '--wcm-font-family': 'Inter, sans-serif',
            '--wcm-accent-color': '#c6ff34',
            '--wcm-accent-fill-color': '#c6ff34',
            '--wcm-background-color': '#171717',
            '--wcm-container-border-radius': '12px',
            '--wcm-button-border-radius': '8px',
          },
        },
      },
    },
  );
}

/** Create wagmi config — call after fetching app config. */
export function buildWagmiConfig(appConfig: AppConfig) {
  const projectId = appConfig.walletConnect?.projectId;
  const frontendUrl = appConfig.frontendUrl ?? APP_URL_FALLBACK;

  return createConfig({
    chains: [mainnet, bsc, polygon],
    transports: {
      [mainnet.id]: http(),
      [bsc.id]: http(),
      [polygon.id]: http(),
    },
    connectors: buildConnectors(projectId, frontendUrl),
  });
}

/** Get the initialized wagmi config singleton. Must call initWagmi() first. */
export function getWagmiConfig() {
  if (!_wagmiConfig) {
    throw new Error('[Wagmi] Config not initialized. Call initWagmi() first.');
  }
  return _wagmiConfig;
}

/** Async init — call once at app startup before rendering WagmiProvider. */
export async function initWagmi(): Promise<ReturnType<typeof createConfig>> {
  if (_wagmiConfig) return _wagmiConfig;
  const config = await fetchAppConfig();
  _wagmiConfig = buildWagmiConfig(config);
  return _wagmiConfig;
}
