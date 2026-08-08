import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import CopyTradeManager from "./CopyTradeManager";
import { Zap, RefreshCw, Radio, Sparkles, MessageSquare, Flame, Plus, Trash2, CheckCircle, XCircle } from "lucide-react";
import { MarketSignal, AlertRule } from "../types";
import { apiFetch, apiJson } from "../api/client";

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

interface IntelProps {
  onActivateAgent: (ticker: string, size: number) => void;
  networkOffline: boolean;
}

export default function Intel({ onActivateAgent, networkOffline }: IntelProps) {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [showAddSource, setShowAddSource] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", type: "rss", url: "", priority: 5 });

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
      .catch((err: any) => console.error("Sync failed:", err))
      .finally(() => setSyncing(false));
  };

  const handleAddSource = async () => {
    if (!newSource.name || !newSource.url) return;
    try {
      await apiJson("/api/sources/my", {
        method: "POST",
        body: JSON.stringify({
          name: newSource.name,
          source_type: newSource.type,
          url_or_handle: newSource.url,
          priority: newSource.priority,
        }),
      });
      setNewSource({ name: "", type: "rss", url: "", priority: 5 });
      setShowAddSource(false);
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

  const signals: MarketSignal[] = signalsData || [];
  const sources: Source[] = sourcesData?.sources || [];

  const handleActivate = (sig: MarketSignal) => {
    const ticker = sig.ticker.replace("$", "");
    onActivateAgent(ticker, 100);
  };

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

      {/* Sources Panel */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-xs uppercase tracking-widest text-zinc-400 font-bold px-1">WATCHED SOURCES</span>
          <button
            onClick={() => setShowAddSource(!showAddSource)}
            className="text-[10px] text-[#c6ff34] hover:text-white px-2 py-1 rounded border border-[#c6ff34]/30 hover:border-[#c6ff34] transition-all flex items-center gap-1"
          >
            <Plus className="w-3 h-3" /> ADD SOURCE
          </button>
        </div>

        {/* Add Source Form */}
        {showAddSource && (
          <div className="bg-[#1c2023] border border-[#c6ff34]/30 p-4 rounded-xl space-y-3 animate-fadeIn">
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Source name (e.g. Whale Alert)"
                value={newSource.name}
                onChange={e => setNewSource(p => ({ ...p, name: e.target.value }))}
                className="bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
              />
              <select
                value={newSource.type}
                onChange={e => setNewSource(p => ({ ...p, type: e.target.value }))}
                className="bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 focus:outline-none focus:border-[#c6ff34]"
              >
                <option value="rss">RSS Feed</option>
                <option value="telegram">Telegram Channel</option>
                <option value="twitter">Twitter/X</option>
                <option value="reddit">Reddit</option>
                <option value="onchain">On-Chain</option>
              </select>
            </div>
            <input
              type="text"
              placeholder="URL or handle (e.g. @CryptoWhale or https://example.com/rss)"
              value={newSource.url}
              onChange={e => setNewSource(p => ({ ...p, url: e.target.value }))}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddSource(false)}
                className="text-xs text-zinc-400 hover:text-white px-3 py-1.5 rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSource}
                disabled={!newSource.name || !newSource.url}
                className="bg-[#c6ff34] text-black text-xs font-bold px-3 py-1.5 rounded-lg hover:bg-[#b0f020] transition-all disabled:opacity-50"
              >
                Add Source
              </button>
            </div>
          </div>
        )}

        {/* Sources List */}
        <div className="bg-[#1c2023] border border-zinc-800 rounded-xl p-4 space-y-2">
          {sourcesLoading ? (
            <p className="text-xs text-zinc-500 text-center py-4">Loading sources...</p>
          ) : sources.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center py-4">No sources configured. Add RSS feeds, Telegram channels, or Twitter accounts.</p>
          ) : (
            sources.map((src) => (
              <div
                key={src.id}
                className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
                  src.enabled
                    ? "border-zinc-700 bg-zinc-900/50"
                    : "border-zinc-800 bg-zinc-950/30 opacity-60"
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  {src.enabled ? (
                    <CheckCircle className="w-4 h-4 text-[#c6ff34] shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-zinc-600 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-white truncate">{src.name}</p>
                    <p className="text-[10px] text-zinc-500 font-mono truncate">{src.url_or_handle}</p>
                  </div>
                  <span className="text-[9px] uppercase font-bold text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded shrink-0">
                    {src.source_type}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {!src.is_default && (
                    <>
                      <button
                        onClick={() => handleToggleSource(src)}
                        className={`text-xs px-2 py-1 rounded transition-all ${
                          src.enabled
                            ? "text-[#c6ff34] hover:bg-[#c6ff34]/10"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        {src.enabled ? "ON" : "OFF"}
                      </button>
                      <button
                        onClick={() => handleDeleteSource(src.id)}
                        className="text-zinc-500 hover:text-red-400 p-1 rounded transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                  {src.is_default && (
                    <span className="text-[9px] text-zinc-600 font-mono">DEFAULT</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Signals Section */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1">IDENTIFIED OPPORTUNITIES</p>
          {lastSync && (
            <span className="text-[10px] text-zinc-500 font-mono">Updated: {lastSync}</span>
          )}
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
            <button
              onClick={() => refetch()}
              className="text-xs text-white underline hover:text-[#c6ff34]"
            >
              Try Again
            </button>
          </div>
        ) : signals.length === 0 ? (
          <div className="bg-zinc-900/30 border border-dashed border-zinc-800 p-8 rounded-2xl text-center space-y-2">
            <p className="text-sm font-bold text-zinc-400">No Active Signals</p>
            <p className="text-xs text-zinc-600">Click SYNC to scan configured sources for trading opportunities.</p>
            <button
              onClick={handleRescan}
              disabled={syncing || networkOffline}
              className="mt-2 bg-[#c6ff34] text-black text-xs font-bold px-4 py-2 rounded-lg hover:bg-[#b0f020] transition-all disabled:opacity-50"
            >
              {syncing ? "Scanning..." : "SCAN NOW"}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {signals.map((sig, idx) => {
              const confidence = sig.confidence || 80;
              return (
                <div
                  key={idx}
                  className="bg-[#1c2023] border border-zinc-800 rounded-2xl overflow-hidden flex flex-col group hover:border-[#c6ff34]/40 transition-all duration-300"
                >
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
                      <p className="text-xs text-zinc-300 font-medium leading-relaxed italic">
                        "{sig.analysis}"
                      </p>
                    </div>
                  </div>

                  {/* Activation Button */}
                  <div className="px-5 pb-5 pt-1 bg-zinc-950/20">
                    <button
                      onClick={() => handleActivate(sig)}
                      disabled={networkOffline}
                      className="w-full bg-[#c6ff34] text-[#101416] font-black text-xs py-3.5 px-4 rounded-xl flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Zap className="w-3.5 h-3.5 fill-current" />
                      {sig.actionLabel}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <CopyTradeManager />
      
      {/* Decorative convergence analytics block */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent z-10"></div>
        <div className="absolute inset-0 opacity-10 pointer-events-none bg-[radial-gradient(#c6ff34_1px,transparent_1px)] [background-size:12px_12px]"></div>
        <div className="relative z-20 space-y-1">
          <p className="text-xs font-black uppercase text-[#c6ff34] tracking-widest">Global Signal Convergence</p>
          <p className="text-[10px] text-zinc-400 font-medium">Multi-chain sentiment clusters and social matrix analysis processed via Engine B + Groq.</p>
        </div>
      </div>
    </div>
  );
}
