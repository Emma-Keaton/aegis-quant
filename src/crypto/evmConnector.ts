import { createConfig, http, injected } from 'wagmi';
import { walletConnect } from '@wagmi/connectors';
import { mainnet, bsc, polygon } from 'wagmi/chains';
import { useAccount, useConnect } from 'wagmi';
import type { Connector } from 'wagmi';

// WalletConnect Project ID (get one at https://cloud.walletconnect.com)
const WALLET_CONNECT_PROJECT_ID = 'YOUR_PROJECT_ID_HERE';

/**
 * Connect to an EVM wallet using wagmi/viem.
 * Supports MetaMask (injected) and WalletConnect.
 * Returns a human-readable network name and the user's address.
 */
export async function connectEVM(preferred: 'metamask' | 'walletconnect' = 'metamask'): Promise<{ network: string; address: string }> {
  // Create a fresh config for programmatic connection
  const config = createConfig({
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
          url: 'https://aegis-quant.app',
          icons: ['https://aegis-quant.app/icon.png'],
        },
      }),
    ],
  });

  // Choose the connector based on the caller's preference
  const connectorName = preferred === 'walletconnect' ? 'WalletConnect' : 'MetaMask';
  const connector = config.connectors.find(c => c.name === connectorName) || config.connectors[0];

  // Initiate the connection flow
  await connector.connect({ connector });

  // Get account info via state
  const { account, chainId } = connector?.getAccount?.() ?? {};
  
  // Map known chain IDs to friendly names
  const chainNameMap: Record<number, string> = {
    1: 'Ethereum',
    56: 'BNB Smart Chain',
    137: 'Polygon',
  };
  const network = chainNameMap[chainId as number] ?? `Chain ${chainId}`;

  return { network, address: account?.address ?? '' };
}

/**
 * Connect to a Solana wallet.
 * Supports Phantom and Solflare adapters.
 */
export async function connectSolana(preferred?: 'phantom' | 'solflare'): Promise<{ network: string; address: string }> {
  const solana = (window as any).solana;
  if (!solana) {
    throw new Error('Solana wallet extension not found');
  }

  // Phantom wallet (default)
  if (!preferred || preferred === 'phantom') {
    if (solana.isPhantom) {
      await solana.connect();
      return { network: 'Solana', address: solana.publicKey.toString() };
    }
    // fall back to Solflare if Phantom not available
  }

  // Solflare wallet
  if (preferred === 'solflare') {
    if (solana.isSolflare) {
      await solana.connect();
      return { network: 'Solana', address: solana.publicKey.toString() };
    }
    throw new Error('Solflare wallet not detected');
  }

  // If Phantom was not preferred but is present, use it as fallback
  if (solana.isPhantom) {
    await solana.connect();
    return { network: 'Solana', address: solana.publicKey.toString() };
  }

  throw new Error('No supported Solana wallet found');
}
