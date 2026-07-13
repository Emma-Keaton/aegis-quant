import React, { useState, useEffect } from "react";
import { Zap, RefreshCw, Radio, Sparkles, MessageSquare, Flame } from "lucide-react";
import { MarketSignal } from "../types";

interface IntelProps {
  onActivateAgent: (ticker: string, size: number) => void;
  networkOffline: boolean;
}

export default function Intel({ onActivateAgent, networkOffline }: IntelProps) {
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [scanningStatus, setScanningStatus] = useState<string>("Scanning Reddit, RSS, & News...");
  const [activeSourceIndex, setActiveSourceIndex] = useState<number>(0);

  const sources = [
    "Source: r/cryptocurrency [Active]",
    "Source: CoinDesk API [Connected]",
    "Source: Twitter Firehose [Awaiting...]",
    "Source: r/solana [Analyzing]",
    "Source: Telegram Whale Watcher [Active]"
  ];

  const fetchSignals = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/signals");
      if (!res.ok) {
        throw new Error("Failed to fetch market signals");
      }
      const json = await res.json();
      if (json.status === "success" && json.data) {
        setSignals(json.data);
      } else {
        throw new Error("Invalid format returned by market scanner");
      }
    } catch (err: any) {
      setError(err.message || "Unknown error occurred during market scanning");
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();

    // Rotate active source indicator in scanner-effect
    const interval = setInterval(() => {
      setActiveSourceIndex((prev) => (prev + 1) % sources.length);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const handleRescan = () => {
    setScanningStatus("Scraping social clusters...");
    setLoading(true);
    setTimeout(() => {
      setScanningStatus("Routing vectors to Kronos microservice...");
      setTimeout(() => {
        fetchSignals(false);
        setScanningStatus("Scanning Reddit, RSS, & News...");
        setLoading(false);
      }, 8000); // 1.5s total loading simulation
    }, 1000);
  };

  const handleActivate = (sig: MarketSignal) => {
    // Default trade size based on ticker or random allocation simulation
    const simulatedSize = sig.ticker === "$WIF" ? 180.00 : 350.00;
    onActivateAgent(sig.ticker.replace("$", ""), simulatedSize);
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
          disabled={loading}
          className="text-zinc-400 hover:text-[#c6ff34] p-2 hover:bg-zinc-900 rounded-full transition-all flex items-center gap-1.5 text-xs font-bold font-mono"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "SCANNING" : "RESCAN"}
        </button>
      </div>

      {/* Live Market scanner active widget */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-xs uppercase tracking-widest text-zinc-400 font-bold px-1">SIGNAL ANALYSIS HUB</span>
          <span className="flex items-center gap-1 text-[10px] font-bold text-[#c6ff34]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#c6ff34] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#c6ff34]"></span>
            </span>
            LIVE FEED
          </span>
        </div>

        {/* Scanner border animation effect container */}
        <div className="relative overflow-hidden bg-[#1c2023] border border-zinc-800 p-4 rounded-xl flex items-center gap-4">
          <div className="flex items-center justify-center bg-zinc-950 h-10 w-10 rounded-lg border border-zinc-800">
            <RefreshCw className="w-5 h-5 text-[#c6ff34] animate-spin" style={{ animationDuration: "5s" }} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-white italic truncate">
              🕒 {scanningStatus}
            </p>
            <p className="text-[10px] text-[#8d947a] font-bold mt-1 font-mono uppercase tracking-wider transition-all">
              {sources[activeSourceIndex]}
            </p>
          </div>
        </div>
      </div>

      {/* Identified opportunities header */}
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1">IDENTIFIED OPPORTUNITIES</p>

        {loading && signals.length === 0 ? (
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
              onClick={() => fetchSignals()}
              className="text-xs text-white underline hover:text-[#c6ff34]"
            >
              Try Scanning Again
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
                        <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">MENTIONS / DENSITY</p>
                        <p className="text-xs font-extrabold text-[#c6ff34]">{sig.metric}</p>
                      </div>
                    </div>

                    {/* AI Output Card Section */}
                    <div className="bg-zinc-950 p-3 rounded-xl border-l-2 border-[#c6ff34] space-y-1">
                      <div className="flex items-center gap-1 text-[9px] font-black text-[#c6ff34] uppercase tracking-widest">
                        <Sparkles className="w-3 h-3 fill-[#c6ff34] text-[#c6ff34]" />
                        <span>AI Output</span>
                      </div>
                      <p className="text-xs text-zinc-300 font-medium leading-relaxed italic">
                        "{sig.analysis}"
                      </p>
                    </div>
                  </div>

                  {/* Immediate Activation Bottom Button Area */}
                  <div className="px-5 pb-5 pt-1 bg-zinc-950/20">
                    <button
                      onClick={() => handleActivate(sig)}
                      className="w-full bg-[#c6ff34] text-[#101416] font-black text-xs py-3.5 px-4 rounded-xl flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all hover:brightness-110"
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

      {/* Decorative convergence analytics block from design specs */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 relative overflow-hidden h-32 flex flex-col justify-end">
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent z-10"></div>
        {/* Subtle grid accent background */}
        <div className="absolute inset-0 opacity-10 pointer-events-none bg-[radial-gradient(#c6ff34_1px,transparent_1px)] [background-size:12px_12px]"></div>
        
        <div className="relative z-20 space-y-0.5">
          <p className="text-xs font-black uppercase text-[#c6ff34] tracking-widest">Global Signal Convergence</p>
          <p className="text-[10px] text-zinc-400 font-medium">Multi-chain sentiment clusters and social matrix analysis processed in real-time.</p>
        </div>
      </div>
    </div>
  );
}
