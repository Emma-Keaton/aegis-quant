// Solana wallet connector using @solana/web3.js.
// Connects to Phantom, Solflare, or other Solana wallets via provider injection.

import { PublicKey } from '@solana/web3.js';
import { openWalletApp } from './walletLinks';

/**
 * Shape of an injected Solana wallet provider (Phantom / Solflare / Torus).
 * Wallets inject whatever they like, so every member is optional and loosely
 * typed — but never `any`, so call sites must narrow before use.
 */
interface SolanaProvider {
  request?: (args: {
    method: string;
    params?: unknown;
  }) => Promise<Record<string, unknown> | undefined>;
  connect?: () => Promise<void>;
  disconnect?: () => Promise<void>;
  getAccounts?: () => Promise<string[]>;
  getCluster?: () => Promise<string>;
  signTransaction?: (tx: string) => Promise<unknown>;
  signAllTransactions?: (txs: string[]) => Promise<unknown[]>;
  publicKey?: { toString(): string } | null;
  isConnected?: boolean;
  isPhantom?: boolean;
  isSolflare?: boolean;
  isTorus?: boolean;
}

interface SolanaWindow {
  solana?: SolanaProvider;
  phantom?: { solana?: SolanaProvider };
  solflare?: SolanaProvider;
  torus?: SolanaProvider;
}

function solanaWindow(): SolanaWindow {
  return window as unknown as SolanaWindow;
}

/**
 * Resolve the injected provider for a specific Solana wallet.
 * Falls back to the generic `window.solana` provider.
 */
function getSolanaProvider(walletId?: string): SolanaProvider | undefined {
  const w = solanaWindow();
  switch (walletId) {
    case 'phantom':
      return w.phantom?.solana || (w.solana?.isPhantom ? w.solana : undefined) || undefined;
    case 'solflare':
      return w.solflare || (w.solana?.isSolflare ? w.solana : undefined) || undefined;
    case 'torus':
      return w.torus || (w.solana?.isTorus ? w.solana : undefined) || undefined;
    default:
      return w.solana;
  }
}

/**
 * Connect using an already-resolved provider object.
 */
async function connectWithProvider(provider: SolanaProvider, walletId: string): Promise<{ network: string; address: string }> {
  try {
    // For newer wallet APIs
    if (typeof provider.request === 'function') {
      await provider.request({ method: 'solana_requestAccounts' });
    } else if (typeof provider.connect === 'function') {
      await provider.connect();
    } else {
      throw new Error(`${walletId} provider does not expose connect`);
    }

    const accounts = await (provider.getAccounts
      ? provider.getAccounts()
      : provider.publicKey
        ? [provider.publicKey.toString()]
        : null);
    if (!accounts || accounts.length === 0) {
      throw new Error(`${walletId} returned no accounts`);
    }
    const publicKey = new PublicKey(accounts[0]);

    // Determine network (mainnet vs devnet vs testnet)
    let network = 'Solana';
    if (provider.isConnected && typeof provider.getCluster === 'function') {
      const cluster = await provider.getCluster();
      if (cluster === 'devnet' || cluster === 'testnet') {
        network = 'Solana ' + cluster.charAt(0).toUpperCase() + cluster.slice(1);
      }
    }

    return {
      network,
      address: publicKey.toString(),
    };
  } catch (error) {
    console.error(`${walletId} connection failed:`, error);
    throw new Error(`${walletId} connection error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export function connectSolana(): Promise<{ network: string; address: string }> {
  // Check for injected Solana provider (Phantom, Solflare, etc.)
  const solana = solanaWindow().solana;
  if (!solana) {
    throw new Error('Solana wallet extension not detected. Please install Phantom or Solflare.');
  }
  return connectWithProvider(solana, 'Solana');
}

/**
 * Connect to a *specific* Solana wallet (phantom, solflare, torus).
 * Uses that wallet's own injected provider when installed; otherwise opens the
 * wallet's in-browser web app (or install page) as a fallback.
 */
export function connectSolanaWallet(
  walletId: string,
): Promise<{ network: string; address: string }> {
  const provider = getSolanaProvider(walletId);
  if (!provider) {
    openWalletApp(walletId);
    throw new Error(`${walletId} not detected — opened ${walletId}`);
  }
  return connectWithProvider(provider, walletId);
}

export async function disconnectSolana(): Promise<void> {
  const solana = solanaWindow().solana;
  if (solana && typeof solana.disconnect === 'function') {
    await solana.disconnect();
  }
}

// Check if Solana wallet is available
export function isSolanaWalletAvailable(): boolean {
  return !!solanaWindow().solana;
}

// Get available Solana wallet names
export function getAvailableSolanaWallets(): string[] {
  const wallets: string[] = [];
  const solana = solanaWindow().solana;
  if (solana) {
    if (solana.isPhantom) wallets.push('Phantom');
    if (solana.isSolflare) wallets.push('Solflare');
    if (solana.isTorus) wallets.push('Torus');
    if (wallets.length === 0) wallets.push('Solana wallet detected');
  }
  return wallets;
}

/**
 * Sign a raw Solana transaction (base64) with the connected wallet provider.
 * Returns the signed raw transaction (base64) for the backend to broadcast.
 * The private key never leaves the wallet.
 */
export async function signSolanaTransaction(
  unsignedTxBase64: string,
  walletAddress: string,
  walletId?: string,
): Promise<string> {
  const provider = getSolanaProvider(walletId) || solanaWindow().solana;
  if (!provider) {
    throw new Error('Solana wallet not detected — install Phantom or Solflare');
  }

  // Provider adapters expose signTransaction in different shapes.
  if (typeof provider.signTransaction === 'function') {
    // Returns base64 signed raw transaction.
    const signed = await provider.signTransaction(unsignedTxBase64);
    return typeof signed === 'string' ? signed : String(signed);
  }
  if (typeof provider.signAllTransactions === 'function') {
    const signed = await provider.signAllTransactions([unsignedTxBase64]);
    const first = signed?.[0];
    return typeof first === 'string' ? first : String(first);
  }
  if (typeof provider.request === 'function') {
    // Phantom-style JSON-RPC sign.
    const res = (await provider.request({
      method: 'solana_signRawTransaction',
      params: { encodedTransaction: unsignedTxBase64, address: walletAddress },
    })) as { signedTransaction?: string; encodedTransaction?: string } | undefined;
    return res?.signedTransaction || res?.encodedTransaction || String(res);
  }
  throw new Error(`${walletId || 'Solana'} wallet does not expose transaction signing`);
}

