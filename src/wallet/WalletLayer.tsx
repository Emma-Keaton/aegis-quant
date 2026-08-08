import type { ReactNode } from 'react';
import { WagmiProvider } from 'wagmi';
import { RainbowKitProvider } from '@rainbow-me/rainbowkit';

interface WalletLayerProps {
  config: any;
  children: ReactNode;
}

/**
 * Mounts the heavy wallet stack (Wagmi + RainbowKit). This is lazy-loaded into
 * its own async chunk and only mounted once the wagmi config is ready, so the
 * app shell paints before the wallet bundle is fetched.
 */
export function WalletLayer({ config, children }: WalletLayerProps) {
  return (
    <WagmiProvider config={config}>
      <RainbowKitProvider>{children}</RainbowKitProvider>
    </WagmiProvider>
  );
}

export default WalletLayer;