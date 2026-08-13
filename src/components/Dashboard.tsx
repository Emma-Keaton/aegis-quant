import React, { useState } from "react";
import { Settings, TrendingUp, Sparkles, AlertTriangle, ArrowUpRight, ArrowDownRight, ChevronDown, Award, Wifi, WifiOff } from "lucide-react";
import { UserState } from "../types";
import { PnLChart } from "./PnLChart";

interface DashboardProps {
  userState: UserState;
  onToggleAgent: (active: boolean) => void;
  onNavigateToStrategy: () => void;
  onNavigateToLogs: () => void;
  onPanic: () => void;
  backtestResult?: any;
  networkOffline: boolean;
  onToggleNetworkOffline: (offline: boolean) => void;
}



export default function Dashboard({ userState, onToggleAgent, onNavigateToStrategy, onNavigateToLogs, onPanic, backtestResult, networkOffline, onToggleNetworkOffline }: DashboardProps) {
  const [timeframe, setTimeframe] = useState<string>("1D");
  const [showAnalytics, setShowAnalytics] = useState<boolean>(false);
  const [selectedAsset, setSelectedAsset] = useState<string>("SOL");
  const [panicState, setPanicState] = useState<"idle" | "armed" | "terminating">("idle");

  const currency = userState.currency || "USD";
  const nairaRate = userState.nairaRate;

  // Derived analytics from real open positions (fallback to "—" when empty).
  const positionPnl = (userState.positions || []).map((p) => ({
    symbol: (p.pair || "").split("/")[0] || "—",
    pnl: typeof p.pnl === "number" ? p.pnl : 0,
  }));
  const totalUnrealized = positionPnl.reduce((s, p) => s + p.pnl, 0);
  const best = positionPnl.reduce((a, b) => (b.pnl > a.pnl ? b : a), { symbol: "—", pnl: 0 });
  const worst = positionPnl.reduce((a, b) => (b.pnl < a.pnl ? b : a), { symbol: "—", pnl: 0 });
  const largest = positionPnl.reduce((a, b) => (Math.abs(b.pnl) > Math.abs(a.pnl) ? b : a), { symbol: "—", pnl: 0 });
  const hasPositions = positionPnl.length > 0;

  const handlePanicClick = () => {
    if (networkOffline) return; // Locked out when offline
    if (panicState === "idle") {
      setPanicState("armed");
    } else if (panicState === "armed") {
      setPanicState("terminating");
      setTimeout(() => {
        onPanic();
        setPanicState("idle");
      }, 1500);
    }
  };

  const formatVal = (usdAmount: number) => {
    if (currency === "NGN") {
      if (!nairaRate) return "₦—"; // live rate not loaded yet
      const ngnAmount = usdAmount * nairaRate;
      return `₦${ngnAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `$${usdAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  

  return (
    <div className="space-y-6 pb-24" id="dashboard_screen">
      {/* Mini App Header */}
      <div className="flex justify-between items-center h-14 border-b border-zinc-800 px-1">
        <h1 className="text-xl font-black text-white tracking-wider uppercase flex items-center gap-1.5">
          AEGIS <span className="text-[#c6ff34]">QUANT</span>
        </h1>
        <div className="flex items-center gap-2">
          {/* Real-time Network Status Indicator */}
          <div
            className={`flex items-center gap-1 text-[9px] font-black uppercase px-2 py-1 rounded-lg border transition-all ${
              networkOffline
                ? "bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse"
                : "bg-[#c6ff34]/10 text-[#c6ff34] border-[#c6ff34]/20"
            }`}
          >
            {networkOffline ? <WifiOff className="w-3 h-3 text-amber-400" /> : <Wifi className="w-3 h-3 text-[#c6ff34]" />}
            <span>{networkOffline ? "OFFLINE" : "ONLINE"}</span>
          </div>

          <button 
            onClick={onNavigateToStrategy}
            className="text-zinc-400 hover:text-[#c6ff34] p-2 hover:bg-zinc-900 rounded-full transition-all cursor-pointer"
            id="dashboard_settings_btn"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Mode & P&L Section below the Header */}
      <div className="flex items-center justify-between bg-zinc-900/40 rounded-xl p-3 border border-zinc-800/80 mt-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${userState.tradeMode === "LIVE" ? "bg-red-500 animate-pulse" : "bg-[#c6ff34] animate-pulse"}`}></span>
          <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded font-mono tracking-wider ${
            userState.tradeMode === "LIVE"
              ? "bg-red-500/10 text-red-400 border border-red-500/20"
              : "bg-[#c6ff34]/10 text-[#c6ff34] border border-[#c6ff34]/20"
          }`}>
            {userState.tradeMode === "LIVE" ? "LIVE TRADING" : "PAPER MODE"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-[10px] sm:text-xs text-[#c6ff34] font-black uppercase bg-[#c6ff34]/5 border border-[#c6ff34]/10 px-2.5 py-1 rounded-lg">
          <TrendingUp className="w-3.5 h-3.5 text-[#c6ff34]" />
          <span>NET P&L: +{userState.pnlPercentage}% (24h)</span>
        </div>
      </div>

      {/* Portfolio Value Display */}
      <div className="space-y-1">
        <p className="text-xs uppercase tracking-widest text-zinc-500 font-bold">Total Portfolio Value</p>
        <h2 className="text-4xl font-black font-sans tracking-tight text-white">
          {formatVal(userState.portfolioValue)}
        </h2>
        <p className="text-xs font-semibold text-[#c6ff34] flex items-center gap-1">
          <span>✔</span> +{formatVal(userState.dailyProfitLoss)} Today
        </p>
      </div>

      {/* Chart Container */}
      <PnLChart userState={userState} backtestResult={backtestResult} />

      {/* Automated Agent Switch Card */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-[#c6ff34] font-black">AUTOMATED EXECUTION AGENT</p>
          <p className="text-xs text-zinc-300 mt-1.5 leading-relaxed">
            Watches global token trends, analyzes indicators, reasons trade opportunities, and executes secure live orders.
          </p>
          <p className="text-xs text-zinc-400 mt-2 flex items-center gap-1.5">
            Status: 
            <span className={`font-bold inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${
              userState.agentActive ? "bg-[#c6ff34]/10 text-[#c6ff34]" : "bg-red-500/10 text-red-400"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${userState.agentActive ? "bg-[#c6ff34]" : "bg-red-400"}`}></span>
              {userState.agentActive ? "ACTIVE" : "SHUTDOWN"}
            </span>
          </p>
        </div>

        {/* Risk Limit Representation */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs font-mono text-zinc-400">
            <span>Risk Limit</span>
            <span className="text-white font-bold">{userState.riskLimit}%</span>
          </div>
          <div className="h-2 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
            <div 
              className="h-full bg-[#c6ff34] rounded-full transition-all" 
              style={{ width: `${userState.riskLimit}%` }}
            ></div>
          </div>
        </div>

        {/* Main Action Button */}
        {networkOffline ? (
          <button
            disabled
            className="w-full bg-zinc-800 text-zinc-500 font-bold text-xs py-3.5 px-4 rounded-xl border border-zinc-700/60 uppercase tracking-wider cursor-not-allowed opacity-50 flex items-center justify-center gap-1.5"
          >
            <span>🔌</span> CONNECTIVITY OFFLINE
          </button>
        ) : userState.agentActive ? (
          <button
            onClick={() => onToggleAgent(false)}
            className="w-full bg-[#c6ff34] text-[#101416] font-bold text-xs py-3.5 px-4 rounded-xl shadow-lg hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider cursor-pointer"
            id="shutdown_agent_btn"
          >
            SHUT DOWN TRADING AGENT
          </button>
        ) : (
          <button
            onClick={() => onToggleAgent(true)}
            className="w-full border border-dashed border-[#c6ff34] text-[#c6ff34] font-bold text-xs py-3.5 px-4 rounded-xl hover:bg-[#c6ff34]/10 active:scale-[0.98] transition-all uppercase tracking-wider cursor-pointer"
            id="start_agent_btn"
          >
            START TRADING AGENT
          </button>
        )}

        {/* Global Emergency Kill Switch / Panic Button */}
        <div className="pt-2 border-t border-zinc-800/60 mt-2">
          {networkOffline ? (
            <button
              disabled
              className="w-full border border-zinc-800 text-zinc-600 font-bold text-xs py-3.5 rounded-xl uppercase tracking-wider cursor-not-allowed opacity-40 flex items-center justify-center gap-2"
            >
              <span>🚨</span> KILL SWITCH DISABLED (OFFLINE)
            </button>
          ) : panicState === "idle" ? (
            <button
              onClick={handlePanicClick}
              className="w-full border border-red-500/40 hover:bg-red-500/10 text-red-400 font-bold text-xs py-3.5 rounded-xl transition-all uppercase tracking-wider cursor-pointer flex items-center justify-center gap-2"
            >
              <span>🚨</span> PANIC RESET SYSTEM
            </button>
          ) : panicState === "armed" ? (
            <button
              onClick={handlePanicClick}
              className="w-full bg-red-600 text-white hover:bg-red-700 font-bold text-xs py-3.5 rounded-xl transition-all uppercase tracking-wider cursor-pointer animate-pulse flex items-center justify-center gap-2 border border-red-500"
            >
              <span>⚠️</span> CONFIRM SYSTEM SHUTDOWN
            </button>
          ) : (
            <button
              disabled
              className="w-full bg-zinc-900 border border-zinc-800 text-red-500 font-bold text-xs py-3.5 rounded-xl transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              <span className="animate-spin mr-1">⏳</span> SECURING SYSTEM...
            </button>
          )}
        </div>
      </div>

      {/* Active Positions Section */}
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-wider text-zinc-400 font-bold px-1">Active Positions</p>
        {userState.positions.length === 0 ? (
          <div className="bg-zinc-900/30 border border-dashed border-zinc-800 p-6 rounded-2xl text-center space-y-1">
            <p className="text-sm font-semibold text-zinc-400">No Active Positions</p>
            <p className="text-xs text-zinc-600">Activate agents on the Intel tab or adjust risk parameters to launch trades.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {userState.positions.map((pos) => (
              <div 
                key={pos.id}
                className="bg-[#1c2023] border border-zinc-800 rounded-xl p-4 flex items-center justify-between hover:border-zinc-700 transition-all"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-zinc-950 rounded-lg flex items-center justify-center font-black text-[#c6ff34] border border-zinc-800 font-sans">
                    {pos.logo}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white">{pos.pair}</h4>
                    <p className="text-xs text-zinc-400">Size: {formatVal(pos.size)}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-bold flex items-center justify-end gap-1 ${
                    pos.pnl >= 0 ? "text-[#c6ff34]" : "text-red-400"
                  }`}>
                    {pos.pnl >= 0 ? "+" : ""}{formatVal(pos.pnl)}
                  </p>
                  <p className="text-[10px] text-zinc-500 font-mono">Buy: {formatVal(pos.buyPrice)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* integrated luminous ledger stats toggler */}
      <div className="border border-zinc-800 bg-zinc-950/40 rounded-2xl overflow-hidden">
        <button 
          onClick={() => setShowAnalytics(!showAnalytics)}
          className="w-full p-4 flex justify-between items-center hover:bg-zinc-900/40 transition-all"
        >
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-[#c6ff34]" />
            <span className="text-xs font-bold uppercase tracking-widest text-white">Performance Analytics</span>
          </div>
          <ChevronDown className={`w-4 h-4 text-zinc-400 transition-transform ${showAnalytics ? "rotate-180" : ""}`} />
        </button>

        {showAnalytics && (
          <div className="p-4 border-t border-zinc-800 space-y-6 bg-zinc-950/80 animate-fadeIn">
            {/* Asset Allocation Donut Chart representation */}
            <div className="space-y-3">
              <p className="text-xs font-bold uppercase text-zinc-400 tracking-wider">Asset Allocation</p>
              <div className="grid grid-cols-2 gap-4 items-center bg-[#1c2023] border border-zinc-800/60 rounded-xl p-4">
                {/* SVG Donut */}
                <div className="relative flex justify-center items-center">
                  <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" stroke="#222" strokeWidth="12" fill="none" />
                    <circle 
                      cx="50" 
                      cy="50" 
                      r="40" 
                      stroke="#c6ff34" 
                      strokeWidth="12" 
                      fill="none" 
                      strokeDasharray="251.2"
                      strokeDashoffset={251.2 - (251.2 * (selectedAsset === "SOL" ? 60 : selectedAsset === "USDT" ? 20 : 20)) / 100}
                      className="transition-all duration-500"
                    />
                  </svg>
                  <div className="absolute text-center">
                    <span className="text-lg font-black text-white">{selectedAsset === "SOL" ? "60%" : "20%"}</span>
                    <p className="text-[9px] uppercase tracking-wider text-zinc-400">{selectedAsset}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <button 
                    onClick={() => setSelectedAsset("SOL")}
                    className={`w-full flex justify-between items-center text-left p-1.5 rounded transition-all ${
                      selectedAsset === "SOL" ? "bg-zinc-800" : ""
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs text-white">
                      <span className="w-2 h-2 rounded-full bg-[#c6ff34]"></span>
                      <span>Solana (SOL)</span>
                    </div>
                    <span className="text-xs font-bold font-mono text-zinc-400">60%</span>
                  </button>
                  <button 
                    onClick={() => setSelectedAsset("USDT")}
                    className={`w-full flex justify-between items-center text-left p-1.5 rounded transition-all ${
                      selectedAsset === "USDT" ? "bg-zinc-800" : ""
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs text-white">
                      <span className="w-2 h-2 rounded-full bg-white"></span>
                      <span>Tether (USDT)</span>
                    </div>
                    <span className="text-xs font-bold font-mono text-zinc-400">20%</span>
                  </button>
                  <button 
                    onClick={() => setSelectedAsset("TON")}
                    className={`w-full flex justify-between items-center text-left p-1.5 rounded transition-all ${
                      selectedAsset === "TON" ? "bg-zinc-800" : ""
                    }`}
                  >
                    <div className="flex items-center gap-1.5 text-xs text-white">
                      <span className="w-2 h-2 rounded-full bg-zinc-500"></span>
                      <span>Toncoin (TON)</span>
                    </div>
                    <span className="text-xs font-bold font-mono text-zinc-400">20%</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Performance Stats Cards (real, derived from open positions) */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-[#1c2023] border border-zinc-800/60 rounded-xl p-3">
                <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Best Performer</p>
                <div className="flex justify-between items-end mt-1.5">
                  <span className="text-sm font-black text-white">{best.symbol}</span>
                  <span className="text-[10px] font-bold font-mono bg-[#c6ff34]/10 text-[#c6ff34] px-1.5 py-0.5 rounded">
                    {hasPositions ? `${best.pnl >= 0 ? "+" : ""}$${best.pnl.toFixed(2)}` : "—"}
                  </span>
                </div>
              </div>
              <div className="bg-[#1c2023] border border-zinc-800/60 rounded-xl p-3">
                <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Worst Performer</p>
                <div className="flex justify-between items-end mt-1.5">
                  <span className="text-sm font-black text-white">{worst.symbol}</span>
                  <span className="text-[10px] font-bold font-mono bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded">
                    {hasPositions ? `${worst.pnl >= 0 ? "+" : ""}$${worst.pnl.toFixed(2)}` : "—"}
                  </span>
                </div>
              </div>
              <div className="bg-[#1c2023] border border-zinc-800/60 rounded-xl p-3 col-span-2 flex justify-between items-center">
                <div>
                  <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Total Unrealized PnL</p>
                  <span className="text-base font-black font-mono mt-1 block text-[#c6ff34]">
                    {hasPositions ? `${totalUnrealized >= 0 ? "+" : ""}${formatVal(totalUnrealized)}` : "—"}
                  </span>
                </div>
                <button onClick={onNavigateToLogs} className="text-xs text-[#c6ff34] hover:underline">View Logs →</button>
              </div>
            </div>

            {/* Portfolio Metrics (real, derived) */}
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase text-zinc-400 tracking-wider">Portfolio Metrics</p>
              <div className="space-y-1.5">
                <div className="bg-[#1c2023] border border-zinc-800/60 rounded-xl p-3 flex justify-between items-center">
                  <div>
                    <h5 className="text-xs font-bold text-white">Largest Position</h5>
                    <p className="text-[10px] font-mono text-zinc-400">{largest.symbol}</p>
                  </div>
                  <span className="text-xs font-bold font-mono text-[#c6ff34]">
                    {hasPositions ? `${largest.pnl >= 0 ? "+" : ""}$${Math.abs(largest.pnl).toFixed(2)}` : "—"}
                  </span>
                </div>
                <div className="bg-[#1c2023] border border-zinc-800/60 rounded-xl p-3 flex justify-between items-center">
                  <div>
                    <h5 className="text-xs font-bold text-white">Open Positions</h5>
                    <p className="text-[10px] font-mono text-zinc-400">Currently held by agent</p>
                  </div>
                  <span className="text-xs font-bold font-mono text-[#c6ff34]">{hasPositions ? positionPnl.length : 0}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
