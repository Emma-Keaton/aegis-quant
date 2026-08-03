import { createConfig, http } from 'wagmi';
import { mainnet, bsc, polygon } from 'wagmi/chains';

export const wagmiConfig = createConfig({
  chains: [mainnet, bsc, polygon],
  transports: {
    [mainnet.id]: http(),
    [bsc.id]: http(),
    [polygon.id]: http(),
  },
});
