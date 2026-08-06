import { createConfig, http, injected } from 'wagmi';
import { walletConnect } from 'wagmi/connectors';
import { connect, getAccount } from 'wagmi/actions';
import { mainnet, bsc, polygon } from 'wagmi/chains';

const WALLET_CONNECT_PROJECT_ID = import.meta.env.VITE_WALLET_CONNECT_PROJECT_ID || 'YOUR_PROJECT_ID_HERE';

let _config: ReturnType<typeof createConfig> | null = null;

function getConfig() {
  if (!_config) {
    _config = createConfig({
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
  }
  return _config;
}

/**
 * Connect to an EVM wallet using wagmi/viem.
 * Supports MetaMask (injected) and WalletConnect.
 * Returns a human-readable network name and the user's address.
 */
export async function connectEVM(
  preferred: 'metamask' | 'walletconnect' = 'metamask'
): Promise<{ network: string; address: string }> {
  const config = getConfig();

  const connector =
    (preferred === 'walletconnect'
      ? config.connectors.find((c) => c.id === 'walletConnect')
      : config.connectors.find((c) => c.id === 'injected')) || config.connectors[0];

  if (!connector) {
    throw new Error('No EVM connector available');
  }

  await connect(config, { connector });

  const { address, chainId } = getAccount(config);

  const chainNameMap: Record<number, string> = {
    1: 'Ethereum',
    56: 'BNB Smart Chain',
    137: 'Polygon',
  };
  const network = chainNameMap[chainId ?? -1] ?? `Chain ${chainId}`;

  return { network, address: address ?? '' };
}
