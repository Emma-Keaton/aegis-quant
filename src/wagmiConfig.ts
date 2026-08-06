import { createConfig, http } from 'wagmi';
import { injected, walletConnect } from 'wagmi/connectors';
import { mainnet, bsc, polygon } from 'wagmi/chains';

const WALLET_CONNECT_PROJECT_ID = import.meta.env.VITE_WALLET_CONNECT_PROJECT_ID || 'YOUR_PROJECT_ID_HERE';

export const wagmiConfig = createConfig({
  chains: [mainnet, bsc, polygon],
  transports: {
    [mainnet.id]: http(),
    [bsc.id]: http(),
    [polygon.id]: http(),
  },
  connectors: [
    injected(),
    walletConnect({
      projectId: WALLET_CONNECT_PROJECT_ID,
      metadata: {
        name: 'Aegis Quant',
        description: 'AI-Powered Crypto Trading Platform',
        url: 'https://aegis-quant.vercel.app',
        icons: ['https://aegis-quant.vercel.app/icon.png'],
      },
    }),
  ],
});
