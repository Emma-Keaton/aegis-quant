import { connect, getAccount } from 'wagmi/actions';
import { getWagmiConfig } from '../wagmiConfig';
import { openWalletApp } from './walletLinks';

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

/**
 * Connect to a *specific* EVM / CeFi wallet (bybit, okx, binance, metamask,
 * trust, safepal, ...). Finds the matching wagmi connector so the connection
 * deep-links into that wallet's own app (or opens its WalletConnect flow).
 *
 * If the specific connector is not available (e.g. no WalletConnect project ID
 * in dev), it opens the wallet's in-browser app page as a fallback.
 */
export async function connectEVMWallet(
  walletId: string,
): Promise<{ network: string; address: string }> {
  const config = getWagmiConfig();
  const target = walletId.toLowerCase();

  const connector = config.connectors.find(
    (c) =>
      (c && (c.id || '').toLowerCase().includes(target)) ||
      (c && (c.name || '').toLowerCase().includes(target)),
  );

  if (!connector) {
    // No wired connector for this wallet (e.g. dev without projectId) —
    // open its install / in-browser app so the user can connect manually.
    openWalletApp(walletId);
    throw new Error(`No ${walletId} connector available — opened ${walletId}`);
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

