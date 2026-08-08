export interface Position {
  id: string;
  pair: string;
  size: number;
  pnl: number;
  buyPrice: number;
  currentPrice: number;
  logo: string;
}

export interface CeFiConnection {
  connected: boolean;
  encryptedKeys: string | null;
}

export interface UserState {
  walletConnected: boolean;
  walletAddress: string;
  network: string;
  balance: number;
  portfolioValue: number;
  dailyProfitLoss: number;
  pnlPercentage: number;
  agentActive: boolean;
  agentTarget: string;
  riskLimit: number;
  tradeMode: "PAPER" | "LIVE";
  currency: "USD" | "NGN";
  nairaRate: number;
  positions: Position[];
  connectedCeFi: {
    bybit: CeFiConnection;
    okx: CeFiConnection;
    binance: CeFiConnection;
  };
}

export interface RiskSettings {
  maxAllocation: number;
  maxConcurrentTrades: number;
  riskLevel: "CONSERVATIVE" | "AGGRESSIVE";
  stopLoss: number;
  takeProfit: number;
  trailingStop: number;
  whitelist: string[];
  baseTradeUsd: number;
}

export interface TransactionLog {
  id: string;
  type: string;
  pair: string;
  volume: string;
  status: "Filled" | "Pending" | "Failed";
  timestamp: string;
  hash: string;
}

export interface MarketSignal {
  ticker: string;
  category: string;
  badge: string;
  source: string;
  metric: string;
  analysis: string;
  confidence: number;
  actionLabel: string;
}

export interface AlertRule {
  id: string;
  metric: string;
  condition: string;
  value: string;
  action: string;
  active: boolean;
}

