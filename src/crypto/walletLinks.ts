/**
 * Wallet fast-link descriptors.
 *
 * Every wallet a user can "fast link" from the Wallet hub maps to a specific
 * wallet app. Clicking a fast link should:
 *   1. Connect through that wallet's own connector/provider when it's available
 *      (which deep-links into the installed native app or opens the in-app
 *      WalletConnect flow), OR
 *   2. Open the wallet's install / in-browser web app as a fallback.
 *
 * `appUrl` is the in-browser / install page. `mobileDeepLink` is an optional
 * native universal-link prefix used on mobile when available.
 */
export interface WalletApp {
  id: string;
  name: string;
  chain: "evm" | "solana" | "ton";
  /** In-browser web app / install page (fallback open target). */
  appUrl: string;
  /** Optional native universal link prefix for deep-linking the app on mobile. */
  mobileDeepLink?: string;
}

export const WALLET_APPS: Record<string, WalletApp> = {
  // EVM / WalletConnect wallets
  metamask: {
    id: "metamask", name: "MetaMask", chain: "evm",
    appUrl: "https://metamask.io/download/",
    mobileDeepLink: "https://metamask.app.link/browse/",
  },
  trust: {
    id: "trust", name: "Trust Wallet", chain: "evm",
    appUrl: "https://trustwallet.com/download",
    mobileDeepLink: "https://link.trustwallet.com/",
  },
  safepal: {
    id: "safepal", name: "SafePal", chain: "evm",
    appUrl: "https://www.safepal.io/",
    mobileDeepLink: "https://link.safepal.io/",
  },
  // CeFi / CCXT exchange wallets (also expose EVM WalletConnect flows)
  bybit: {
    id: "bybit", name: "Bybit Wallet", chain: "evm",
    appUrl: "https://www.bybit.com/en/web3/",
    mobileDeepLink: "https://web3.bybit.com",
  },
  okx: {
    id: "okx", name: "OKX Wallet", chain: "evm",
    appUrl: "https://www.okx.com/web3",
    mobileDeepLink: "https://www.okx.com/web3",
  },
  binance: {
    id: "binance", name: "Binance Wallet", chain: "evm",
    appUrl: "https://www.binance.com/en/web3wallet",
  },
  // Solana wallets
  phantom: {
    id: "phantom", name: "Phantom", chain: "solana",
    appUrl: "https://phantom.app/",
    mobileDeepLink: "https://phantom.app/ul/browse/",
  },
  solflare: {
    id: "solflare", name: "Solflare", chain: "solana",
    appUrl: "https://solflare.com/",
  },
  torus: {
    id: "torus", name: "Torus", chain: "solana",
    appUrl: "https://app.tor.us/",
  },
  // TON wallets
  tonkeeper: {
    id: "tonkeeper", name: "TonKeeper", chain: "ton",
    appUrl: "https://tonkeeper.com/",
    mobileDeepLink: "tonkeeper://",
  },
};

/** List of EVM wallets to surface as fast links (includes the ccxt/CeFi ones). */
export const EVM_FAST_LINKS = ["metamask", "trust", "safepal", "bybit", "okx", "binance"];

/** List of Solana wallets to surface as fast links. */
export const SOLANA_FAST_LINKS = ["phantom", "solflare", "torus"];

/** Open a wallet's app — deep link on mobile when a URI exists, else web app. */
export function openWalletApp(walletId: string): boolean {
  const app = WALLET_APPS[walletId];
  if (!app) return false;

  const isMobile =
    /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) &&
    !/Windows|Macintosh|Linux/i.test(navigator.userAgent);

  const target = isMobile && app.mobileDeepLink ? app.mobileDeepLink : app.appUrl;
  window.open(target, "_blank", "noopener,noreferrer");
  return true;
}
