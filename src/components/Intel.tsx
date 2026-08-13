import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import CopyTradeManager from "./CopyTradeManager";
import {
  RefreshCw, Radio, Sparkles, MessageSquare, Flame, Plus, Trash2,
  CheckCircle, XCircle, Link2, Activity, Zap,
} from "lucide-react";
import { MarketSignal } from "../types";
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
    </div>
  );
}
