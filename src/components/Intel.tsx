import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import CopyTradeManager from "./CopyTradeManager";
import {
  RefreshCw, Radio, Sparkles, MessageSquare, Flame, Trash2,
  Link2, Activity, Zap, Trophy, ShieldCheck, Droplets, BarChart3,
} from "lucide-react";
import type {
  MarketSignal, ScoreboardResponse, TokenWatchResponse, PromotionResponse,
} from "../types";
import { apiFetch, apiJson } from "../api/client";
import TelegramLinkCard from "./TelegramLinkCard";

interface Source {
  id: string;
  name: string;
  source_type: string;
  url_or_handle: string;
  priority: number;
  enabled: boolean;
  is_default: boolean;
}

interface SourcesResponse {
  sources: Source[];
  total: number;
  baseline_count: number;
  user_count: number;
}

const CHANNELS: { type: string; label: string; hint: string }[] = [
  { type: "telegram", label: "Telegram", hint: "t.me/... or @handle" },
  { type: "reddit", label: "Reddit", hint: "r/... or subreddit URL" },
  { type: "rss", label: "RSS (News)", hint: "news / feed URL" },
];

const CHANNEL_LABEL: Record<string, string> = {
  telegram: "TELEGRAM",
  reddit: "REDDIT",
  rss: "RSS / NEWS",
  twitter: "TWITTER",
  onchain: "ON-CHAIN",
};

interface IntelProps {
  agentActedTickers: string[];
  networkOffline: boolean;
}

export default function Intel({ agentActedTickers, networkOffline }: IntelProps) {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [newSource, setNewSource] = useState({ name: "", type: "telegram", url: "", priority: 5 });

  // Fetch signals from backend
  const { data: signalsData, isLoading, error, refetch } = useQuery({
    queryKey: ["signals"],
    queryFn: async () => {
      const res = await apiFetch("/api/signals");
      if (!res.ok) throw new Error("Failed to fetch signals");
      const json = await res.json();
      return json.signals || [];
    },
  });

  // Fetch user sources
  const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
    queryKey: ["sources"],
    queryFn: async () => {
      const res = await apiFetch("/api/sources/combined");
      if (!res.ok) throw new Error("Failed to fetch sources");
      return res.json() as Promise<SourcesResponse>;
    },
  });

  // Model scoreboard — ledger-derived model quality + breaker state.
  const { data: scoreboardData } = useQuery<ScoreboardResponse>({
    queryKey: ["scoreboard"],
    queryFn: async () => {
      const res = await apiFetch("/api/model/scoreboard");
      if (!res.ok) throw new Error("Scoreboard unavailable");
      return res.json() as Promise<ScoreboardResponse>;
    },
    refetchInterval: 60000,
    retry: false,
  });

  // Token watch — DEX snapshots, spikes, whale flows.
  const { data: watchData } = useQuery<TokenWatchResponse>({
    queryKey: ["tokenWatch"],
    queryFn: async () => {
      const res = await apiFetch("/api/token-watch?limit=30");
      if (!res.ok) throw new Error("Watch unavailable");
      return res.json() as Promise<TokenWatchResponse>;
    },
    refetchInterval: 90000,
    retry: false,
  });

  // Promotion readiness — live-trading gate checklist.
  const { data: promotionData } = useQuery<PromotionResponse>({
    queryKey: ["promotion"],
    queryFn: async () => {
      const res = await apiFetch("/api/model/promotion");
      if (!res.ok) throw new Error("Promotion status unavailable");
      return res.json() as Promise<PromotionResponse>;
    },
    refetchInterval: 120000,
    retry: false,
  });

  const breakerState = (watchData?.breaker?.state ?? scoreboardData?.breaker?.state ?? "closed") as string;
  const breakerColor =
    breakerState === "open" ? "text-red-400 border-red-500/40 bg-red-500/10"
    : breakerState === "warning" ? "text-amber-400 border-amber-500/40 bg-amber-500/10"
    : "text-[#c6ff34] border-[#c6ff34]/30 bg-[#c6ff34]/10";

  const fmtPct = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  const fmtUsd = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  // Sync engine B + Groq to generate new signals
  const syncMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/signals/sync", { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Sync failed" }));
        throw new Error(err.error || "Sync failed");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["signals"] });
      setLastSync(new Date().toLocaleTimeString());
    },
  });

  const handleRescan = () => {
    setSyncing(true);
    syncMutation.mutateAsync()
      .catch((err: unknown) => console.error("Sync failed:", err))
      .finally(() => setSyncing(false));
  };

  const handleAddSource = async () => {
    if (!newSource.url) return;
    const name = newSource.name || newSource.url;
    try {
      await apiJson("/api/sources/my", {
        method: "POST",
        body: JSON.stringify({
          name,
          source_type: newSource.type,
          url_or_handle: newSource.url,
          priority: newSource.priority,
        }),
      });
      setNewSource({ name: "", type: newSource.type, url: "", priority: 5 });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    } catch (err) {
      console.error("Failed to add source:", err);
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    try {
      await apiFetch(`/api/sources/my/${sourceId}`, { method: "DELETE" });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    } catch (err) {
      console.error("Failed to delete source:", err);
    }
  };

  const handleToggleSource = async (source: Source) => {
    try {
      await apiFetch(`/api/sources/my/${source.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !source.enabled }),
      });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    } catch (err) {
      console.error("Failed to toggle source:", err);
    }
  };

  // -- Trending tokens (separate bucket from the watchlist) ----------------
  interface TrendingItem {
    ticker: string;
    symbol: string;
    source: string;
    rank?: number;
    price?: number | null;
    change_24h?: number | null;
    volume_24h?: number | null;
    market_cap?: number | null;
  }
  const [watchBusy, setWatchBusy] = useState<string | null>(null);
  const { data: trendingData } = useQuery({
    queryKey: ["trending"],
    queryFn: async () => {
      const res = await apiFetch("/api/trending");
      if (!res.ok) return { tickers: [] as TrendingItem[], updated: null };
      const json = await res.json();
      return json.data || { tickers: [] as TrendingItem[], updated: null };
    },
    refetchInterval: 300000, // refresh every 5 min to match backend poller
  });
  const trending: TrendingItem[] = trendingData?.tickers || [];

  const handleWatchTrending = async (ticker: string) => {
    if (!ticker || networkOffline) return;
    setWatchBusy(ticker);
    try {
      await apiJson("/api/whitelist", {
        method: "POST",
        body: JSON.stringify({
          symbol: ticker.replace("$", "").toUpperCase(),
          exchange: "bybit",
          timeframe: "1m",
        }),
      });
      queryClient.invalidateQueries({ queryKey: ["whitelist"] });
    } catch (err) {
      console.error("Failed to watch trending token:", err);
    } finally {
      setWatchBusy(null);
    }
  };

  const signals: MarketSignal[] = signalsData || [];
  const sources: Source[] = sourcesData?.sources || [];

  const baseTicker = (t: string) =>
    t.replace("$", "").replace("/USDT", "").trim().toUpperCase();

  // Cards show only signals the agent is currently acting on (open positions).
  const actedSignals = signals.filter((sig) =>
    agentActedTickers.includes(baseTicker(sig.ticker))
  );

  return (
    <div className="space-y-6 pb-24 font-sans" id="intel_screen">
      {/* Header */}
      <div className="flex justify-between items-center h-14 border-b border-zinc-800 px-1">
        <div className="flex items-center gap-2">
          <Radio className="w-5 h-5 text-[#c6ff34]" />
          <h2 className="text-lg font-black tracking-wider uppercase text-[#c6ff34]">LIVE MARKET FEED</h2>
        </div>
        <button
          onClick={handleRescan}
          disabled={syncing || networkOffline}
          className="text-zinc-400 hover:text-[#c6ff34] p-2 hover:bg-zinc-900 rounded-full transition-all flex items-center gap-1.5 text-xs font-bold font-mono"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "SYNCING" : lastSync ? `LAST: ${lastSync}` : "SYNC"}
        </button>
      </div>

      {/* Console Feed Monitor Widget */}
      <div className="bg-[#1c2023] border border-zinc-800 p-4 rounded-xl flex items-center gap-4">
        <div className="w-10 h-10 bg-zinc-950 rounded-lg border border-zinc-800 flex items-center justify-center shrink-0">
          <Activity className={`w-5 h-5 text-[#c6ff34] ${syncing ? "animate-pulse" : ""}`} />
        </div>
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${syncing ? "bg-[#c6ff34] animate-pulse" : "bg-[#c6ff34]"}`}></span>
            Market Feed {syncing ? "Scanning..." : "Online"}
          </p>
          <p className="text-[10px] font-mono text-zinc-500 truncate">
            {sources.length} sources - {signals.length} parsed signals - Binance + CoinGecko + Coinbase + CoinLore
          </p>
        </div>
      </div>

      {/* Model Scoreboard + Promotion Readiness + Watch & Spikes (quant ops) */}
      <div className="space-y-4" id="quant_ops">
        {/* Scoreboard */}
        <div className="space-y-3">
          <div className="flex justify-between items-center px-1">
            <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold flex items-center gap-1.5">
              <Trophy className="w-3.5 h-3.5 text-[#c6ff34]" /> MODEL SCOREBOARD
            </p>
            <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded border ${breakerColor}`}>
              BREAKER {breakerState.toUpperCase()}
            </span>
          </div>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 space-y-3">
            {scoreboardData?.forecast_models?.length ? (
              <div className="overflow-x-auto no-scrollbar">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[8px] uppercase tracking-widest text-zinc-500">
                      <th className="pb-2 pr-2 font-bold">#</th>
                      <th className="pb-2 pr-2 font-bold">Model</th>
                      <th className="pb-2 pr-2 font-bold">Settled</th>
                      <th className="pb-2 pr-2 font-bold">Hit</th>
                      <th className="pb-2 pr-2 font-bold">Brier</th>
                      <th className="pb-2 pr-2 font-bold">AUC</th>
                      <th className="pb-2 font-bold">IC</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-[11px]">
                    {scoreboardData.forecast_models.slice(0, 8).map((m) => (
                      <tr key={m.model} className="border-t border-zinc-800/60">
                        <td className="py-1.5 pr-2 text-zinc-500">{m.rank}</td>
                        <td className="py-1.5 pr-2 text-white font-bold truncate max-w-[110px]">{m.model}</td>
                        <td className="py-1.5 pr-2 text-zinc-400">{m.settled}</td>
                        <td className="py-1.5 pr-2 text-[#c6ff34] font-bold">
                          {m.hit_rate === null ? "—" : `${(m.hit_rate * 100).toFixed(1)}%`}
                        </td>
                        <td className="py-1.5 pr-2 text-zinc-400">{m.brier ?? "—"}</td>
                        <td className="py-1.5 pr-2 text-zinc-400">{m.roc_auc ?? "—"}</td>
                        <td className={`py-1.5 font-bold ${m.spearman_ic !== null && m.spearman_ic > 0.05 ? "text-[#c6ff34]" : "text-zinc-500"}`}>
                          {m.spearman_ic ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-zinc-500 text-center py-4">No scored forecasts yet — the board fills as the ledger settles.</p>
            )}
            {scoreboardData?.paper && (
              <div className="grid grid-cols-4 gap-2 border-t border-zinc-800/60 pt-3">
                {[
                  { label: "Open", value: String(scoreboardData.paper.open_positions) },
                  { label: "Settled", value: String(scoreboardData.paper.settled_trades) },
                  { label: "Paper WR", value: scoreboardData.paper.win_rate === null ? "—" : `${(scoreboardData.paper.win_rate * 100).toFixed(1)}%` },
                  { label: "Equity", value: fmtUsd(scoreboardData.paper.equity_usd) },
                ].map((cell) => (
                  <div key={cell.label} className="bg-zinc-950 rounded-lg border border-zinc-800 px-2 py-2">
                    <p className="text-[8px] uppercase tracking-widest text-zinc-500 font-bold">{cell.label}</p>
                    <p className="text-xs font-mono font-bold text-white mt-0.5">{cell.value}</p>
                  </div>
                ))}
              </div>
            )}
            {scoreboardData?.latest_promotion && (
              <p className="text-[9px] font-mono text-zinc-500 pt-1">
                Latest promotion: <span className={scoreboardData.latest_promotion.status === "promoted" ? "text-[#c6ff34]" : "text-zinc-300"}>{scoreboardData.latest_promotion.status}</span>
                {scoreboardData.latest_promotion.reason ? ` — ${scoreboardData.latest_promotion.reason}` : ""}
              </p>
            )}
          </div>
        </div>

        {/* Promotion readiness checklist */}
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-[#c6ff34]" /> LIVE READINESS
          </p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 space-y-2">
            {promotionData?.readiness?.length ? (
              <>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono text-zinc-400">
                    Mode: <span className="text-white font-bold uppercase">{promotionData.trading_mode}</span>
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400">
                    Decision: <span className={`font-bold ${promotionData.decision.status === "promoted" ? "text-[#c6ff34]" : "text-zinc-300"}`}>{promotionData.decision.status}</span>
                  </span>
                </div>
                {promotionData.readiness.map((check) => (
                  <div key={check.name} className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${check.passed ? "bg-[#c6ff34]" : "bg-red-500"}`}></span>
                    <span className="text-[10px] font-bold text-white uppercase tracking-wider flex-1 min-w-0 truncate">{check.name}</span>
                    <span className={`text-[9px] font-mono ${check.passed ? "text-[#c6ff34]" : "text-red-400"}`}>
                      {check.passed ? "PASS" : "FAIL"}
                    </span>
                  </div>
                ))}
                {promotionData.decision.reason && (
                  <p className="text-[9px] font-mono text-zinc-500 pt-1">{promotionData.decision.reason}</p>
                )}
              </>
            ) : (
              <p className="text-xs text-zinc-500 text-center py-4">Readiness checklist unavailable.</p>
            )}
          </div>
        </div>

        {/* Watch & spikes */}
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1 flex items-center gap-1.5">
            <Droplets className="w-3.5 h-3.5 text-[#c6ff34]" /> WATCH & SPIKES
          </p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-zinc-500">
                {watchData?.enabled ? `DEX watch ON · every ${watchData.interval_seconds}s` : "DEX watch OFF"}
                {" · threshold "}{watchData ? `${watchData.spike_threshold_pct}%` : "—"}
              </span>
              <span className={`text-[9px] font-mono px-2 py-0.5 rounded border ${breakerColor}`}>
                {breakerState.toUpperCase()}
              </span>
            </div>
            <div className="space-y-1.5">
              <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold flex items-center gap-1.5">
                <BarChart3 className="w-3 h-3" /> Spike candidates
              </p>
              {watchData?.spikes?.length ? (
                watchData.spikes.slice(0, 8).map((s, i) => (
                  <div key={`${s.symbol}-${i}`} className="flex items-center justify-between gap-2 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-white truncate">{s.symbol}</p>
                      <p className="text-[9px] font-mono text-zinc-500 truncate">
                        {s.chain} · liq {fmtUsd(s.liquidity_usd)} · price ${s.price_usd?.toFixed(4) ?? "—"}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={`text-xs font-mono font-bold ${s.spike_pct >= 0 ? "text-[#c6ff34]" : "text-red-400"}`}>
                        {fmtPct(s.spike_pct)}
                      </p>
                      {typeof s.z_score === "number" && (
                        <p className="text-[9px] font-mono text-zinc-500">z {s.z_score.toFixed(1)}</p>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-zinc-500 text-center py-3">No spikes above threshold right now.</p>
              )}
            </div>
            <div className="space-y-1.5 border-t border-zinc-800/60 pt-3">
              <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">
                Whale flows{watchData?.whale_enabled ? "" : " (HELIUS key not set)"}
              </p>
              {watchData?.whale_flows?.length ? (
                watchData.whale_flows.slice(0, 6).map((f, i) => (
                  <div key={`${f.wallet}-${i}`} className="flex items-center justify-between gap-2 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-white truncate">{f.symbol}</p>
                      <p className="text-[9px] font-mono text-zinc-500 truncate">{f.wallet?.slice(0, 8)}…{f.wallet?.slice(-4)}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={`text-[10px] font-mono font-bold ${f.side === "buy" ? "text-[#c6ff34]" : "text-red-400"}`}>
                        {f.side.toUpperCase()} {fmtUsd(f.amount_usd)}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-zinc-500 text-center py-3">No whale flows in the last 2h.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Agent-Acted Opportunities */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-[#c6ff34]" /> AGENT ACTIONS
          </p>
          <span className="text-[10px] text-[#c6ff34] font-mono font-bold">{actedSignals.length} ACTIVE</span>
        </div>

        {isLoading && signals.length === 0 ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4 animate-pulse">
                <div className="flex justify-between">
                  <div className="space-y-2 w-1/3">
                    <div className="h-4 bg-zinc-800 rounded"></div>
                    <div className="h-3 bg-zinc-900 rounded w-2/3"></div>
                  </div>
                  <div className="h-6 bg-zinc-800 rounded w-24"></div>
                </div>
                <div className="h-10 bg-zinc-800 rounded"></div>
                <div className="h-12 bg-zinc-800 rounded"></div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-xl text-center space-y-2">
            <p className="text-xs font-bold text-red-400">{error}</p>
            <button onClick={() => refetch()} className="text-xs text-white underline hover:text-[#c6ff34]">
              Try Again
            </button>
          </div>
        ) : actedSignals.length === 0 ? (
          <div className="bg-zinc-900/30 border border-dashed border-zinc-800 p-6 rounded-2xl text-center space-y-1">
            <p className="text-sm font-bold text-zinc-300">No Active Agent Actions</p>
            <p className="text-xs text-zinc-600">The agent currently has no open positions on parsed signals. Open positions will appear here.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {actedSignals.map((sig, idx) => {
              const confidence = sig.confidence || 80;
              return (
                <div key={idx} className="bg-[#1c2023] border border-zinc-800 rounded-2xl overflow-hidden flex flex-col group hover:border-[#c6ff34]/40 transition-all duration-300">
                  <div className="p-5 space-y-4 flex-1">
                    {/* Top Row Ticker */}
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-xl font-black text-white tracking-tight flex items-center gap-1.5">
                          {sig.ticker}
                          <Flame className="w-3.5 h-3.5 text-orange-500 fill-orange-500" />
                        </h3>
                        <p className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mt-0.5">{sig.category}</p>
                      </div>
                      <span className="text-[10px] font-black tracking-widest bg-[#c6ff34]/10 text-[#c6ff34] border border-[#c6ff34]/20 px-2.5 py-1 rounded-lg">
                        {sig.badge}
                      </span>
                    </div>

                    {/* Source Metrics Box */}
                    <div className="grid grid-cols-2 gap-4 border-y border-zinc-800/60 py-3.5">
                      <div className="space-y-0.5">
                        <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">SOURCE</p>
                        <p className="text-xs font-extrabold text-white flex items-center gap-1">
                          <MessageSquare className="w-3.5 h-3.5 text-zinc-500" />
                          {sig.source}
                        </p>
                      </div>
                      <div className="space-y-0.5">
                        <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">CONFIDENCE</p>
                        <p className="text-xs font-extrabold font-mono text-[#c6ff34]">{confidence}%</p>
                      </div>
                    </div>

                    {/* AI Output Card Section */}
                    <div className="bg-zinc-950 p-3 rounded-xl border-l-2 border-[#c6ff34] space-y-1">
                      <div className="flex items-center gap-1 text-[9px] font-black text-[#c6ff34] uppercase tracking-widest">
                        <Sparkles className="w-3 h-3 fill-[#c6ff34] text-[#c6ff34]" />
                        <span>AI Analysis</span>
                      </div>
                      <p className="text-xs text-zinc-300 font-medium leading-relaxed italic">"{sig.analysis}"</p>
                    </div>
                  </div>

                  {/* Passive agent status footer */}
                  <div className="px-5 pb-5 pt-1 bg-zinc-950/20">
                    <div className="w-full flex items-center justify-center gap-1.5 border border-[#c6ff34]/30 bg-[#c6ff34]/10 text-[#c6ff34] font-black text-xs py-3 px-4 rounded-xl uppercase tracking-wider">
                      <Zap className="w-3.5 h-3.5 fill-current" />
                      AGENT IN POSITION
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {/* Global Signal Convergence - all parsed signals from all sources */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#c6ff34]" /> GLOBAL SIGNAL CONVERGENCE
          </p>
          <span className="text-[10px] text-zinc-500 font-mono font-bold">{signals.length} PARSED</span>
        </div>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 relative overflow-hidden">
          <div className="absolute inset-0 opacity-10 pointer-events-none bg-[radial-gradient(#c6ff34_1px,transparent_1px)] [background-size:12px_12px]"></div>
          <div className="relative z-10 space-y-2 max-h-72 overflow-y-auto no-scrollbar pr-1">
            {signals.length === 0 ? (
              <p className="text-xs text-zinc-500 text-center py-6">No parsed signals yet. Hit SYNC to scan configured sources.</p>
            ) : (
              signals.map((sig, idx) => (
                <div key={idx} className="flex items-center justify-between gap-3 bg-zinc-950/60 border border-zinc-800/60 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-6 h-6 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center font-black text-[10px] text-[#c6ff34] shrink-0">
                      {baseTicker(sig.ticker).slice(0, 1)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-white truncate">{sig.ticker}</p>
                      <p className="text-[9px] font-mono text-zinc-500 truncate">{CHANNEL_LABEL[sig.source] || sig.source}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] font-mono text-[#c6ff34] font-bold">{sig.confidence || 80}%</span>
                    <span className="text-[9px] font-mono text-zinc-500">{sig.metric}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <CopyTradeManager />

      {/* Source Linker - channel + source input system */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <Link2 className="w-3.5 h-3.5" /> SOURCE LINKER
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
          <p className="text-[11px] text-zinc-400">
            Link a channel - pick Telegram, Reddit, or RSS (news) - then paste the link, handle, or ID. The agent will start parsing it into the convergence feed.
          </p>
          {/* Telegram account link for private channels */}
          <TelegramLinkCard />


          {/* Channel selector segmented control */}
          <div className="grid grid-cols-3 gap-1 bg-zinc-950 p-1 rounded-xl border border-zinc-800">
            {CHANNELS.map((ch) => (
              <button
                key={ch.type}
                type="button"
                onClick={() => setNewSource((s) => ({ ...s, type: ch.type }))}
                className={`px-2 py-2 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer ${
                  newSource.type === ch.type
                    ? "bg-[#c6ff34] text-black shadow-lg shadow-[#c6ff34]/20"
                    : "text-zinc-500 hover:text-white"
                }`}
              >
                {ch.label}
              </button>
            ))}
          </div>

          {/* Source input */}
          <div className="space-y-2">
            <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">
              SOURCE INPUT - {CHANNELS.find((c) => c.type === newSource.type)?.hint}
            </label>
            <input
              value={newSource.url}
              onChange={(e) => setNewSource((s) => ({ ...s, url: e.target.value }))}
              placeholder="Paste link, handle, or ID..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
            />
          </div>

          <button
            type="button"
            onClick={handleAddSource}
            disabled={!newSource.url || networkOffline}
            className="w-full bg-[#c6ff34] text-[#101416] font-black text-xs py-3.5 px-4 rounded-xl flex items-center justify-center gap-1.5 hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Link2 className="w-3.5 h-3.5" /> LINK CHANNEL
          </button>
        </div>

        {/* Watched Sources */}
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
          <div className="flex justify-between items-center">
            <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider">WATCHED SOURCES</p>
            <span className="text-[10px] font-mono text-zinc-500">{sources.length} TRACKED</span>
          </div>
          {sourcesLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => <div key={i} className="h-10 bg-zinc-900/60 rounded-lg animate-pulse"></div>)}
            </div>
          ) : sources.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-4">No sources linked yet.</p>
          ) : (
            <div className="space-y-2">
              {sources.map((src) => (
                <div key={src.id} className="flex items-center justify-between gap-2 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2.5">
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-white truncate">{src.name}</p>
                    <p className="text-[9px] font-mono text-zinc-500 truncate">
                      {CHANNEL_LABEL[src.source_type] || src.source_type.toUpperCase()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => handleToggleSource(src)}
                      className={`text-[8px] font-black uppercase px-2 py-1 rounded-md border transition-all cursor-pointer ${
                        src.enabled
                          ? "bg-[#c6ff34]/10 text-[#c6ff34] border-[#c6ff34]/20"
                          : "bg-zinc-900 text-zinc-500 border-zinc-800"
                      }`}
                    >
                      {src.enabled ? "ON" : "OFF"}
                    </button>
                    <button
                      onClick={() => handleDeleteSource(src.id)}
                      className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Trending tokens — separate bucket from the watchlist (CMC ? CoinGecko ? Raydium) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5">
            <Flame className="w-3.5 h-3.5" /> TRENDING
          </p>
          <span className="text-[9px] font-mono text-zinc-500">
            {trending.length} HOT
          </span>
        </div>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl overflow-hidden">
          {trending.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-6 px-4">
              Polling trending tokens (CoinMarketCap ? CoinGecko ? Raydium)... check back in a moment.
            </p>
          ) : (
            <div className="divide-y divide-zinc-800">
              {trending.slice(0, 25).map((t, i) => (
                <div key={`${t.ticker}-${i}`} className="flex items-center justify-between gap-2 px-4 py-2.5 hover:bg-zinc-900/40 transition-all">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[9px] font-mono text-zinc-600 w-5 text-right">{i + 1}</span>
                    <span className="text-xs font-bold text-white truncate">{t.ticker}</span>
                    <span className="text-[8px] font-mono uppercase px-1.5 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-zinc-500">
                      {t.source}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {typeof t.price === "number" && (
                      <span className="text-[10px] font-mono text-zinc-400">
                        ${t.price < 1 ? t.price.toPrecision(4) : t.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </span>
                    )}
                    {typeof t.change_24h === "number" && (
                      <span className={`text-[10px] font-mono font-bold ${t.change_24h >= 0 ? "text-[#c6ff34]" : "text-red-400"}`}>
                        {t.change_24h >= 0 ? "+" : ""}{t.change_24h.toFixed(1)}%
                      </span>
                    )}
                    <button
                      onClick={() => handleWatchTrending(t.ticker)}
                      disabled={watchBusy === t.ticker}
                      className="text-[8px] font-black uppercase px-2 py-1 rounded-md border border-[#c6ff34]/30 text-[#c6ff34] hover:bg-[#c6ff34]/10 transition-all cursor-pointer disabled:opacity-40"
                    >
                      {watchBusy === t.ticker ? "..." : "WATCH"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <p className="text-[9px] text-zinc-500 px-1">
          Trending is separate from your watchlist. Tap WATCH to promote a token onto your watchlist.
        </p>
      </div>
    </div>
  );
}
