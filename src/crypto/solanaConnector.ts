// Solana wallet connector using @solana/web3.js.
// Connects to Phantom, Solflare, or other Solana wallets via window.solana injection.

import { Connection, PublicKey } from '@solana/web3.js';

export async function connectSolana(): Promise<{ network: string; address: string }> {
  // Check for injected Solana provider (Phantom, Solflare, etc.)
  if (!(window as any).solana) {
    throw new Error('Solana wallet extension not detected. Please install Phantom or Solflare.');
  }

  const solana = (window as any).solana;
  
  // Request connection
  try {
    // For newer wallet APIs
    if (typeof solana.request === 'function') {
      await solana.request({ method: 'solana_requestAccounts' });
    } else {
      // Legacy: try connect directly
      await solana.connect();
    }
    
    const accounts = await solana.getAccounts();
    const publicKey = new PublicKey(accounts[0]);
    
    // Determine network (mainnet vs devnet vs testnet)
    // Some wallets expose network info
    let network = 'Solana';
    if (solana.isConnected) {
      // Check if we're on a test/devnet
      const cluster = await solana.getCluster();
      if (cluster === 'devnet' || cluster === 'testnet') {
        network = 'Solana ' + cluster.charAt(0).toUpperCase() + cluster.slice(1);
      }
    }
    
    return {
      network,
      address: publicKey.toString(),
    };
  } catch (error) {
    console.error('Solana connection failed:', error);
    throw new Error(`Solana connection error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export async function disconnectSolana(): Promise<void> {
  const solana = (window as any).solana;
  if (solana && typeof solana.disconnect === 'function') {
    await solana.disconnect();
  }
}

// Check if Solana wallet is available
export function isSolanaWalletAvailable(): boolean {
  return !!(window as any).solana;
}

// Get available Solana wallet names
export function getAvailableSolanaWallets(): string[] {
  const wallets: string[] = [];
  const solana = (window as any).solana;
  if (solana) {
    if (solana.isPhantom) wallets.push('Phantom');
    if (solana.isSolflare) wallets.push('Solflare');
    if (solana.isTorus) wallets.push('Torus');
    if (wallets.length === 0) wallets.push('Solana wallet detected');
  }
  return wallets;
}
