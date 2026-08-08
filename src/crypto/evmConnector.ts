import { connect, getAccount } from 'wagmi/actions';
import { getWagmiConfig } from '../wagmiConfig';

/**
 * Connect to an EVM wallet using wagmi/viem.
 * Supports MetaMask (injected), OKX Wallet, Bybit Wallet, Binance Wallet,
 * and any other WalletConnect-compatible wallet via the shared wagmi config.
 * Returns a human-readable network name and the user's address.
 */
export async function connectEVM(): Promise<{ network: string; address: string }> {
  const config = getWagmiConfig();

  // Prefer injected (MetaMask etc.), fallback to first available connector
  const connector =
    config.connectors.find((c) => c.id === 'injected') || config.connectors[0];

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
