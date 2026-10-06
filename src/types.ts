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
  nairaRate: number | null;
  positions: Position[];
  connectedCeFi: {
    bybit: CeFiConnection;
    okx: CeFiConnection;
    binance: CeFiConnection;
  };
  onboardingCompleted: boolean;
  onboardingPages: string[];
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

/** Single point of a backtest equity/benchmark curve (epoch seconds -> value). */
export interface BacktestCurvePoint {
  time: number;
  value: number;
}

/** Summary statistics returned by POST /api/backtest. */
export interface BacktestMetrics {
  sharpeRatio?: number;
  sortinoRatio?: number;
  maxDrawdown?: number;
  winLossRatio?: number;
  totalTrades?: number;
  netReturn?: number;
  [key: string]: number | string | undefined;
}

/** Full backtest payload held in app state and drawn as a chart overlay. */
export interface BacktestResult {
  backtestCurve: BacktestCurvePoint[];
  benchmarkCurve: BacktestCurvePoint[];
  metrics: BacktestMetrics | null;
  active: boolean;
}

export interface ScoreboardModelRow {
  rank: number;
  model: string;
  settled: number;
  hit_rate: number | null;
  brier: number | null;
  roc_auc: number | null;
  spearman_ic: number | null;
}

export interface ScoreboardPaper {
  open_positions: number;
  settled_trades: number;
  win_rate: number | null;
  equity_usd: number;
}

export interface ScoreboardBreaker {
  state?: string;
  reason?: string | null;
  [key: string]: unknown;
}

export interface ScoreboardResponse {
  updated_at: string;
  forecast_models: ScoreboardModelRow[];
  promotion_ranking?: unknown[];
  paper: ScoreboardPaper;
  breaker: ScoreboardBreaker;
  latest_promotion: {
    profile_id?: string;
    status: string;
    reason?: string | null;
    decided_at?: string | null;
  } | null;
  note?: string;
}

export interface TokenWatchSnapshot {
  symbol: string;
  chain: string;
  price_usd: number | null;
  liquidity_usd: number | null;
  volume_usd: number | null;
  price_change_5m: number | null;
  price_change_1h: number | null;
  price_change_24h: number | null;
  ts: string | null;
}

export interface TokenWatchResponse {
  enabled: boolean;
  interval_seconds: number;
  spike_threshold_pct: number;
  snapshots: TokenWatchSnapshot[];
  spikes: (TokenWatchSnapshot & { spike_pct: number; z_score?: number | null })[];
  whale_flows: { symbol: string; wallet: string; side: string; amount_usd: number; ts: string | null }[];
  whale_enabled: boolean;
  quota?: unknown;
  breaker?: ScoreboardBreaker;
}

export interface PromotionCheck {
  name: string;
  passed: boolean;
  detail?: string;
}

export interface PromotionResponse {
  trading_mode: string;
  decision: {
    status: string;
    reason?: string | null;
    evidence?: unknown;
    decided_at?: string | null;
  };
  readiness: PromotionCheck[];
  require_promotion_for_live: boolean;
  live_trading_enabled: boolean;
}

