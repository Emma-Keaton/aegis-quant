import React, { useState, useEffect } from "react";
import { Sliders, ShieldCheck, CheckSquare, Square, AlertOctagon, HelpCircle, Trash2, Plus, DollarSign, Coins, Play, RefreshCw, BarChart2, Bell, Zap, Sparkles } from "lucide-react";
import { RiskSettings, AlertRule } from "../types";

interface StrategyProps {
  riskSettings: RiskSettings;
  onUpdateSettings: (settings: Partial<RiskSettings>) => void;
  onPanic: () => void;
  tradeMode: "PAPER" | "LIVE";
  onToggleTradeMode: (mode: "PAPER" | "LIVE") => void;
  onResetSettings: () => void;
  currency: "USD" | "NGN";
  nairaRate: number;
  onToggleCurrency: (currency: "USD" | "NGN") => void;
  backtestResult?: {
    backtestCurve: any[];
    benchmarkCurve: any[];
    metrics: any;
    active: boolean;
  } | null;
  onUpdateBacktest: (result: any) => void;
  networkOffline: boolean;
}

export default function Strategy({
  riskSettings,
  onUpdateSettings,
  onPanic,
  tradeMode,
  onToggleTradeMode,
  onResetSettings,
  currency,
  nairaRate,
  onToggleCurrency,
  backtestResult,
  onUpdateBacktest,
  networkOffline
}: StrategyProps) {
  // Local state for smooth real-time slider updates
  const [allocation, setAllocation] = useState<number>(riskSettings.maxAllocation);
  const [maxTrades, setMaxTrades] = useState<number>(riskSettings.maxConcurrentTrades);
  const [stopLoss, setStopLoss] = useState<string>(riskSettings.stopLoss.toString());
  const [takeProfit, setTakeProfit] = useState<string>(riskSettings.takeProfit.toString());
  const [trailing, setTrailing] = useState<string>(riskSettings.trailingStop.toString());

  // Modal and safety states
  const [showLiveWarningModal, setShowLiveWarningModal] = useState<boolean>(false);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);
  const [understandRisks, setUnderstandRisks] = useState<boolean>(false);
  const [panicState, setPanicState] = useState<"idle" | "armed" | "terminating">("idle");

  const handlePanicClick = () => {
    if (networkOffline) return;
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

  // Dynamic Whitelist Tokens List
  const [tokensList, setTokensList] = useState<string[]>(() => {
    const defaults = ["SOL", "TON", "ETH", "BTC", "PEPE", "DOGE", "BONK", "WIF"];
    const combined = Array.from(new Set([...defaults, ...(riskSettings.whitelist || [])]));
    return combined;
  });
  const [newTokenInput, setNewTokenInput] = useState<string>("");

  // Historical Backtesting states
  const [backtestRange, setBacktestRange] = useState<string>("3M");
  const [customRange, setCustomRange] = useState<string>("30D");
  const [backtestCap, setBacktestCap] = useState<number>(10000);
  const [backtestBench, setBacktestBench] = useState<string>("vs_btc");
  const [customBench, setCustomBench] = useState<string>("vs_sol");
  const [backtestLoading, setBacktestLoading] = useState<boolean>(false);
  const [backtestProgress, setBacktestProgress] = useState<number>(0);
  const [backtestMetrics, setBacktestMetrics] = useState<any>(
    backtestResult?.active ? backtestResult.metrics : null
  );

  // Dynamic Alerts Rule Builder States
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [ruleMetric, setRuleMetric] = useState<string>("Portfolio Drawdown");
  const [ruleCondition, setRuleCondition] = useState<string>(">");
  const [ruleValue, setRuleValue] = useState<string>("5%");
  const [ruleAction, setRuleAction] = useState<string>("Pause TON Grid Bot");
  const [ruleSubmitting, setRuleSubmitting] = useState<boolean>(false);

  // Fetch alert rules on mount
  const fetchRules = async () => {
    try {
      const res = await fetch("/api/rules");
      if (res.ok) {
        const json = await res.json();
        if (json.status === "success" && json.data) {
          setRules(json.data);
        }
      }
    } catch (e) {
      console.error("Failed to load rules", e);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  // Backtest triggering handler
  const handleRunBacktest = async () => {
    if (networkOffline) return;
    setBacktestLoading(true);
    setBacktestProgress(0);
    
    // Smooth progress loader simulation
    const interval = setInterval(() => {
      setBacktestProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 10;
      });
    }, 150);

    const finalRange = backtestRange === "CUSTOM" ? customRange : backtestRange;
    const finalBench = backtestBench === "CUSTOM" ? customBench : backtestBench;

    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          range: finalRange,
          initialCapital: backtestCap,
          benchmarkCompare: finalBench
        })
      });
      
      if (res.ok) {
        const json = await res.json();
        // Wait till progress bar finishes
        setTimeout(() => {
          setBacktestLoading(false);
          if (json.status === "success") {
            setBacktestMetrics(json.metrics);
            onUpdateBacktest({
              backtestCurve: json.backtestCurve,
              benchmarkCurve: json.benchmarkCurve,
              metrics: json.metrics,
              active: true
            });
          }
        }, 1600);
      } else {
        setBacktestLoading(false);
      }
    } catch (e) {
      console.error("Backtest simulation failed", e);
      setBacktestLoading(false);
    }
  };

  const handleClearBacktest = () => {
    setBacktestMetrics(null);
    onUpdateBacktest(null);
  };

  // Rule builder form submission
  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (networkOffline) return;
    if (!ruleValue.trim()) return;
    setRuleSubmitting(true);

    try {
      const res = await fetch("/api/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metric: ruleMetric,
          condition: ruleCondition,
          value: ruleValue,
          action: ruleAction
        })
      });

      if (res.ok) {
        const json = await res.json();
        if (json.status === "success") {
          setRules(json.allRules);
          setRuleValue("");
        }
      }
    } catch (err) {
      console.error("Rule submission failed", err);
    } finally {
      setRuleSubmitting(false);
    }
  };

  const handleToggleRule = async (id: string) => {
    if (networkOffline) return;
    try {
      const res = await fetch("/api/rules/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        const json = await res.json();
        if (json.status === "success") {
          setRules(json.allRules);
        }
      }
    } catch (err) {
      console.error("Toggle rule failed", err);
    }
  };

  const handleDeleteRule = async (id: string) => {
    if (networkOffline) return;
    try {
      const res = await fetch("/api/rules/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        const json = await res.json();
        if (json.status === "success") {
          setRules(json.allRules);
        }
      }
    } catch (err) {
      console.error("Delete rule failed", err);
    }
  };

  useEffect(() => {
    setAllocation(riskSettings.maxAllocation);
    setMaxTrades(riskSettings.maxConcurrentTrades);
    setStopLoss(riskSettings.stopLoss.toString());
    setTakeProfit(riskSettings.takeProfit.toString());
    setTrailing(riskSettings.trailingStop.toString());
    
    // Sync tokensList with any newly loaded whitelist
    const defaults = ["SOL", "TON", "ETH", "BTC", "PEPE", "DOGE", "BONK", "WIF"];
    setTokensList(prev => {
      const combined = Array.from(new Set([...defaults, ...prev, ...(riskSettings.whitelist || [])]));
      return combined;
    });
  }, [riskSettings]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value);
    setAllocation(val);
  };

  const handleSliderRelease = () => {
    onUpdateSettings({ maxAllocation: allocation });
  };

  const handleRiskProfileChange = (profile: "CONSERVATIVE" | "AGGRESSIVE") => {
    // Dynamic defaults for specific profiles as an interactive preset helper
    const stopLossPreset = profile === "CONSERVATIVE" ? 1.5 : 3.0;
    const takeProfitPreset = profile === "CONSERVATIVE" ? 3.5 : 6.5;
    const trailingPreset = profile === "CONSERVATIVE" ? 0.5 : 1.0;

    onUpdateSettings({
      riskLevel: profile,
      stopLoss: stopLossPreset,
      takeProfit: takeProfitPreset,
      trailingStop: trailingPreset
    });
  };

  const handleNumericBlur = (field: "stopLoss" | "takeProfit" | "trailingStop", valStr: string) => {
    const parsed = parseFloat(valStr);
    if (!isNaN(parsed) && parsed >= 0) {
      onUpdateSettings({ [field]: parsed });
    }
  };

  const handleTokenToggle = (token: string) => {
    let currentWhitelist = [...riskSettings.whitelist];
    if (currentWhitelist.includes(token)) {
      currentWhitelist = currentWhitelist.filter(t => t !== token);
    } else {
      currentWhitelist.push(token);
    }
    onUpdateSettings({ whitelist: currentWhitelist });
  };

  const incrementTrades = () => {
    if (maxTrades < 10) {
      const newVal = maxTrades + 1;
      setMaxTrades(newVal);
      onUpdateSettings({ maxConcurrentTrades: newVal });
    }
  };

  const decrementTrades = () => {
    if (maxTrades > 1) {
      const newVal = maxTrades - 1;
      setMaxTrades(newVal);
      onUpdateSettings({ maxConcurrentTrades: newVal });
    }
  };

  const handleToggleTradeModeCapsule = () => {
    if (tradeMode === "PAPER") {
      setShowLiveWarningModal(true);
    } else {
      onToggleTradeMode("PAPER");
    }
  };

  return (
    <div className="space-y-6 pb-24 font-sans" id="strategy_screen">
      {/* Header */}
      <div className="flex items-center justify-between h-14 border-b border-zinc-800 px-1">
        <div className="flex items-center gap-2">
          <Sliders className="w-5 h-5 text-[#c6ff34]" />
          <h2 className="text-lg font-black tracking-wider uppercase text-[#c6ff34]">SETTINGS</h2>
        </div>
        <button
          type="button"
          onClick={() => setShowResetConfirm(true)}
          className="text-[10px] text-zinc-400 border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 hover:text-red-400 hover:border-red-500/30 px-3 py-1.5 rounded-lg font-mono font-bold tracking-widest transition-all flex items-center gap-1.5 uppercase"
        >
          <span>↺</span> RESET TO DEFAULTS
        </button>
      </div>

      {/* Trading Execution Mode */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>⚙</span> TRADING EXECUTION MODE
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-black text-zinc-500 block uppercase tracking-wider">EXECUTION SYSTEM</span>
            <span className={`text-sm font-black flex items-center gap-1.5 mt-1 ${tradeMode === "LIVE" ? "text-red-400" : "text-[#c6ff34]"}`}>
              <span className={`w-2 h-2 rounded-full ${tradeMode === "LIVE" ? "bg-red-500 animate-pulse" : "bg-[#c6ff34]"}`}></span>
              {tradeMode === "LIVE" ? "LIVE REAL-MONEY TRADES" : "PAPER DEMO TRADING"}
            </span>
          </div>
          {/* Symmetrical Two-Option Selector Capsule */}
          <div 
            onClick={handleToggleTradeModeCapsule}
            className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-800 cursor-pointer select-none"
          >
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleToggleTradeModeCapsule();
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                tradeMode === "PAPER"
                  ? "bg-[#c6ff34] text-black shadow-lg shadow-[#c6ff34]/20"
                  : "text-zinc-500 hover:text-white"
              }`}
            >
              PAPER
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleToggleTradeModeCapsule();
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                tradeMode === "LIVE"
                  ? "bg-red-500 text-white shadow-lg shadow-red-500/20"
                  : "text-zinc-500 hover:text-white"
              }`}
            >
              LIVE
            </button>
          </div>
        </div>
      </div>

      {/* Base Pricing Currency Toggle */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>💵</span> BASE PRICING CURRENCY
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-black text-zinc-500 block uppercase tracking-wider">SYSTEM CURRENCY</span>
            <span className="text-sm font-black text-white flex items-center gap-1.5 mt-1">
              <span className="text-[#c6ff34] font-bold">{currency === "NGN" ? "NIGERIAN NAIRA (₦)" : "US DOLLARS ($)"}</span>
            </span>
            <p className="text-[9px] text-zinc-500 font-mono mt-0.5">
              Live Exchange Rate: 1 USD = ₦{nairaRate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
          
          <div 
            onClick={() => onToggleCurrency(currency === "USD" ? "NGN" : "USD")}
            className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-800 cursor-pointer select-none"
          >
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleCurrency(currency === "USD" ? "NGN" : "USD");
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                currency === "USD"
                  ? "bg-[#c6ff34] text-black shadow-lg shadow-[#c6ff34]/20"
                  : "text-zinc-500 hover:text-white"
              }`}
            >
              USD ($)
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleCurrency(currency === "USD" ? "NGN" : "USD");
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                currency === "NGN"
                  ? "bg-[#c6ff34] text-black shadow-lg shadow-[#c6ff34]/20"
                  : "text-zinc-500 hover:text-white"
              }`}
            >
              NGN (₦)
            </button>
          </div>
        </div>
      </div>

      {/* Sizing Section */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>🏛</span> TRADE CAPITAL SIZING
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-5">
          {/* Active Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-bold text-zinc-400">
              <span>MAX ALLOCATION PER TRADE</span>
              <span className="text-[#c6ff34] text-sm font-black">{allocation}%</span>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              value={allocation}
              onChange={handleSliderChange}
              onMouseUp={handleSliderRelease}
              onTouchEnd={handleSliderRelease}
              className="w-full h-1.5 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#c6ff34] focus:outline-none"
            />
          </div>

          {/* Sizing Numeric Incrementor */}
          <div className="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-3.5 rounded-xl">
            <span className="text-xs font-bold text-zinc-400">MAX DAILY CONCURRENT TRADES</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={decrementTrades}
                className="w-8 h-8 rounded-lg bg-zinc-900 hover:bg-zinc-800 flex items-center justify-center font-bold text-white transition-all border border-zinc-800 active:scale-95"
              >
                —
              </button>
              <span className="text-sm font-black text-white w-4 text-center font-mono">{maxTrades}</span>
              <button
                type="button"
                onClick={incrementTrades}
                className="w-8 h-8 rounded-lg bg-zinc-900 hover:bg-zinc-800 flex items-center justify-center font-bold text-white transition-all border border-zinc-800 active:scale-95"
              >
                +
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Profile Selector */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>🛡</span> RISK MITIGATION PROFILES
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-5">
          {/* Grid Selection */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleRiskProfileChange("CONSERVATIVE")}
              className={`py-3 rounded-xl border font-bold text-xs uppercase tracking-wider transition-all ${
                riskSettings.riskLevel === "CONSERVATIVE"
                  ? "border-[#c6ff34] text-[#c6ff34] bg-[#c6ff34]/5"
                  : "border-zinc-800 text-zinc-400 hover:border-zinc-700"
              }`}
            >
              CONSERVATIVE
            </button>
            <button
              type="button"
              onClick={() => handleRiskProfileChange("AGGRESSIVE")}
              className={`py-3 rounded-xl border font-bold text-xs uppercase tracking-wider transition-all ${
                riskSettings.riskLevel === "AGGRESSIVE"
                  ? "border-[#c6ff34] text-[#c6ff34] bg-[#c6ff34]/5"
                  : "border-zinc-800 text-zinc-400 hover:border-zinc-700"
              }`}
            >
              AGGRESSIVE
            </button>
          </div>

          {/* Numeric Custom Overrides */}
          <div className="grid grid-cols-3 gap-2 pt-1">
            <div className="space-y-1">
              <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">STOP LOSS</label>
              <div className="relative">
                <input
                  type="text"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  onBlur={() => handleNumericBlur("stopLoss", stopLoss)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 text-center font-bold focus:outline-none focus:border-[#c6ff34]"
                />
                <span className="absolute right-3 top-2.5 text-xs text-[#c6ff34] font-black font-sans">%</span>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">TAKE PROFIT</label>
              <div className="relative">
                <input
                  type="text"
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(e.target.value)}
                  onBlur={() => handleNumericBlur("takeProfit", takeProfit)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 text-center font-bold focus:outline-none focus:border-[#c6ff34]"
                />
                <span className="absolute right-3 top-2.5 text-xs text-[#c6ff34] font-black font-sans">%</span>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">TRAILING STOP</label>
              <div className="relative">
                <input
                  type="text"
                  value={trailing}
                  onChange={(e) => setTrailing(e.target.value)}
                  onBlur={() => handleNumericBlur("trailingStop", trailing)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 text-center font-bold focus:outline-none focus:border-[#c6ff34]"
                />
                <span className="absolute right-3 top-2.5 text-xs text-[#c6ff34] font-black font-sans">%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Base Trade Amount */}
      <div className="space-y-3 mt-4">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>💰</span> BASE TRADE AMOUNT (USD)
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 flex items-center">
          <input
            type="number"
            min="0"
            step="0.01"
            value={riskSettings.baseTradeUsd}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val)) {
                onUpdateSettings({ baseTradeUsd: val });
              }
            }}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-white p-2.5 text-center font-bold focus:outline-none focus:border-[#c6ff34]"
          />
          <span className="ml-2 text-[#c6ff34] font-bold text-sm">USD</span>
        </div>
      </div>

      {/* Whitelist Matrix */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>⁝≣</span> TOKEN WHITELISTING & ASSETS
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {tokensList.map((token) => {
              const isWhitelisted = riskSettings.whitelist.includes(token);
              return (
                <div
                  key={token}
                  className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${
                    isWhitelisted
                      ? "border-[#c6ff34]/30 bg-[#171717] text-white shadow-sm"
                      : "border-zinc-800/40 bg-[#171717]/30 text-zinc-500 hover:border-zinc-800/60"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => handleTokenToggle(token)}
                    className="flex-1 flex items-center gap-2.5 text-left focus:outline-none cursor-pointer"
                  >
                    <span className={`w-4 h-4 rounded flex items-center justify-center border transition-all ${
                      isWhitelisted 
                        ? "bg-[#c6ff34] border-[#c6ff34] text-black" 
                        : "border-zinc-700 text-transparent"
                    }`}>
                      {isWhitelisted && <span className="text-[9px] font-black">✔</span>}
                    </span>
                    <span className="text-xs font-bold tracking-wider">{token}</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setTokensList(prev => prev.filter(t => t !== token));
                      onUpdateSettings({
                        whitelist: riskSettings.whitelist.filter(t => t !== token)
                      });
                    }}
                    className="p-1 rounded text-zinc-600 hover:text-red-400 hover:bg-zinc-900 transition-colors cursor-pointer"
                    title={`Delete ${token}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Add custom token form */}
          <div className="flex gap-2 pt-2 border-t border-zinc-900">
            <input
              type="text"
              placeholder="e.g. BONK, SHIB, DOGE"
              value={newTokenInput}
              onChange={(e) => setNewTokenInput(e.target.value.toUpperCase())}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white font-bold placeholder-zinc-700 focus:outline-none focus:border-[#c6ff34]"
            />
            <button
              type="button"
              onClick={() => {
                const trimmed = newTokenInput.trim().toUpperCase();
                if (trimmed) {
                  if (tokensList.includes(trimmed)) {
                    if (!riskSettings.whitelist.includes(trimmed)) {
                      onUpdateSettings({
                        whitelist: [...riskSettings.whitelist, trimmed]
                      });
                    }
                  } else {
                    setTokensList(prev => [...prev, trimmed]);
                    onUpdateSettings({
                      whitelist: [...riskSettings.whitelist, trimmed]
                    });
                  }
                  setNewTokenInput("");
                }
              }}
              className="bg-[#c6ff34] hover:bg-[#b0f020] text-black text-xs font-black px-4 py-2 rounded-xl flex items-center gap-1 transition-all cursor-pointer active:scale-95 shadow-md shadow-[#c6ff34]/10"
            >
              <Plus className="w-3.5 h-3.5" />
              ADD
            </button>
          </div>
        </div>
      </div>

      {/* Historical Backtesting Engine Card */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>📊</span> HISTORICAL BACKTEST ENGINE
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
          <p className="text-[11px] text-zinc-400">
            Simulate the Aegis Quant logic against granular high-fidelity historical data. Adjust variables to observe metrics like Drawdown and Sharpe ratios.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">HISTORICAL RANGE</label>
              <select
                value={backtestRange}
                onChange={(e) => setBacktestRange(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold font-mono focus:outline-none focus:border-[#c6ff34] cursor-pointer"
              >
                <option value="30D">30 DAYS (RECENT MONTH)</option>
                <option value="3M">3 MONTHS (Q2 2026)</option>
                <option value="1Y">1 YEAR (FY 2025-2026)</option>
                <option value="2Y">2 YEARS (2024-2026)</option>
                <option value="5Y">5 YEARS (CYCLE)</option>
                <option value="CUSTOM">CUSTOM RANGE (TYPE...)</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">BENCHMARK COMPARE</label>
              <select
                value={backtestBench}
                onChange={(e) => setBacktestBench(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold font-mono focus:outline-none focus:border-[#c6ff34] cursor-pointer"
              >
                <option value="vs_btc">BTC BUY & HOLD</option>
                <option value="vs_eth">ETH BUY & HOLD</option>
                <option value="vs_sol">SOL BUY & HOLD</option>
                <option value="vs_ton">TON BUY & HOLD</option>
                <option value="vs_sp500">S&P 500 INDEX (SPY)</option>
                <option value="CUSTOM">CUSTOM SYMBOL (TYPE...)</option>
              </select>
            </div>

            {backtestRange === "CUSTOM" && (
              <div className="col-span-2 space-y-1 animate-fade-in">
                <label className="text-[9px] uppercase tracking-wider text-[#c6ff34] font-bold block">
                  CUSTOM HISTORICAL RANGE (e.g. 45D, 6M, 3Y)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 45D, 6M, 3Y"
                  value={customRange}
                  onChange={(e) => setCustomRange(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold font-mono focus:outline-none focus:border-[#c6ff34]"
                />
              </div>
            )}

            {backtestBench === "CUSTOM" && (
              <div className="col-span-2 space-y-1 animate-fade-in">
                <label className="text-[9px] uppercase tracking-wider text-[#c6ff34] font-bold block">
                  CUSTOM BENCHMARK SYMBOL OR CONTRACT
                </label>
                <input
                  type="text"
                  placeholder="e.g. SOL, BNB, TON, AAPL"
                  value={customBench}
                  onChange={(e) => setCustomBench(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold font-mono focus:outline-none focus:border-[#c6ff34]"
                />
              </div>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-bold text-zinc-400">
              <span>INITIAL TEST CAPITAL ({currency === "NGN" ? "₦" : "$"})</span>
              <div className="flex items-center bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden select-none">
                <button
                  type="button"
                  disabled={backtestLoading}
                  onClick={() => setBacktestCap(Math.max(500, backtestCap - 500))}
                  className="px-2 py-1 text-zinc-400 hover:text-[#c6ff34] hover:bg-zinc-900 border-r border-zinc-800 text-xs font-bold transition-all disabled:opacity-40 active:scale-95"
                >
                  −
                </button>
                <input
                  type="number"
                  min="500"
                  max="10000000"
                  step="500"
                  value={backtestCap}
                  onChange={(e) => {
                    const parsed = parseInt(e.target.value);
                    setBacktestCap(isNaN(parsed) ? 0 : parsed);
                  }}
                  disabled={backtestLoading}
                  className="w-16 bg-transparent text-xs text-[#c6ff34] font-black text-center py-1 focus:outline-none font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <button
                  type="button"
                  disabled={backtestLoading}
                  onClick={() => setBacktestCap(Math.min(10000000, backtestCap + 500))}
                  className="px-2 py-1 text-zinc-400 hover:text-[#c6ff34] hover:bg-zinc-900 border-l border-zinc-800 text-xs font-bold transition-all disabled:opacity-40 active:scale-95"
                >
                  +
                </button>
              </div>
            </div>
            <input
              type="range"
              min="500"
              max="100000"
              step="500"
              value={backtestCap}
              onChange={(e) => setBacktestCap(parseInt(e.target.value))}
              disabled={backtestLoading}
              className="w-full h-1.5 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#c6ff34] focus:outline-none disabled:opacity-50"
            />
            {currency === "NGN" && (
              <div className="text-right text-[10px] text-zinc-500 font-mono mt-0.5">
                Calculated NGN: <span className="text-[#c6ff34] font-bold">₦{(backtestCap * nairaRate).toLocaleString("en-US", { maximumFractionDigits: 0 })}</span> (at 1 USD = ₦{nairaRate.toLocaleString()})
              </div>
            )}
          </div>

          {backtestLoading ? (
            <div className="space-y-2 pt-2">
              <div className="flex justify-between items-center text-[10px] font-mono text-[#c6ff34] font-bold">
                <span className="animate-pulse flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RUNNING QUANT SIMULATION...
                </span>
                <span>{backtestProgress}%</span>
              </div>
              <div className="h-1.5 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
                <div
                  className="h-full bg-[#c6ff34] transition-all duration-150"
                  style={{ width: `${backtestProgress}%` }}
                ></div>
              </div>
            </div>
          ) : (
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleRunBacktest}
                disabled={networkOffline}
                className={`flex-1 bg-[#c6ff34] hover:bg-[#b0f020] text-black font-black text-xs py-3 rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md shadow-[#c6ff34]/10 active:scale-95 ${
                  networkOffline ? "opacity-40 cursor-not-allowed" : ""
                }`}
              >
                <Play className="w-3.5 h-3.5 fill-black" />
                RUN BACKTEST SIMULATION
              </button>

              {backtestMetrics && (
                <button
                  type="button"
                  onClick={handleClearBacktest}
                  className="bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white px-4 rounded-xl text-xs font-bold font-mono transition-all cursor-pointer"
                >
                  CLEAR
                </button>
              )}
            </div>
          )}

          {/* Backtest Metrics Panel */}
          {backtestMetrics && (
            <div className="pt-4 border-t border-zinc-800/80 space-y-3 animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black text-white uppercase tracking-widest flex items-center gap-1">
                  <BarChart2 className="w-3.5 h-3.5 text-[#14b8a6]" /> BACKTEST METRICS REPORT
                </span>
                <span className="text-[9px] font-bold bg-[#14b8a6]/10 text-[#14b8a6] border border-[#14b8a6]/20 px-2 py-0.5 rounded-md font-mono uppercase">
                  SIMULATION PASSED
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">SHARPE RATIO</span>
                  <span className="text-sm font-black font-mono text-[#c6ff34]">
                    {backtestMetrics.sharpeRatio}
                  </span>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">SORTINO RATIO</span>
                  <span className="text-sm font-black font-mono text-[#14b8a6]">
                    {backtestMetrics.sortinoRatio}
                  </span>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center col-span-2 sm:col-span-1">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">MAX DRAWDOWN</span>
                  <span className="text-sm font-black font-mono text-red-400">
                    -{backtestMetrics.maxDrawdown}%
                  </span>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">WIN / LOSS</span>
                  <span className="text-xs font-black font-mono text-white">
                    {backtestMetrics.winLossRatio}%
                  </span>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">TOTAL TRADES</span>
                  <span className="text-xs font-black font-mono text-zinc-400">
                    {backtestMetrics.totalTrades}
                  </span>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-800 p-2.5 rounded-xl text-center col-span-2 sm:col-span-1">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 block">NET RETURN</span>
                  <span className="text-xs font-black font-mono text-[#c6ff34]">
                    +{backtestMetrics.netReturn}%
                  </span>
                </div>
              </div>
              <p className="text-[9px] text-zinc-500 text-center font-mono italic">
                *The backtest curve has been layered onto the Dashboard performance chart.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Alert Rules & Webhook Customizer */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
          <span>🔔</span> ALERTS & WEBHOOK ENGINE
        </p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
          <p className="text-[11px] text-zinc-400">
            Define automated conditions that trigger instant push alerts or trigger custom API webhooks on external nodes.
          </p>

          <form onSubmit={handleAddRule} className="space-y-3 pt-1">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">IF METRIC</label>
                <select
                  value={ruleMetric}
                  onChange={(e) => setRuleMetric(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold focus:outline-none focus:border-[#c6ff34] cursor-pointer animate-none bg-none"
                >
                  <option value="Portfolio Drawdown">Portfolio Drawdown</option>
                  <option value="RSI (14) SOL">RSI (14) SOL</option>
                  <option value="Price Deviation TON">Price Deviation TON</option>
                  <option value="Funding Rate Bybit">Funding Rate Bybit</option>
                  <option value="MACD Histogram (12, 26) BTC">MACD Histogram (12, 26) BTC</option>
                  <option value="Bollinger Band %B ETH">Bollinger Band %B ETH</option>
                  <option value="EMA (200) Cross-under SOL">EMA (200) Cross-under SOL</option>
                  <option value="Hourly Volume Surge USDT">Hourly Volume Surge USDT</option>
                  <option value="Open Interest Delta Bybit">Open Interest Delta Bybit</option>
                  <option value="Orderbook Imbalance > 15%">Orderbook Imbalance &gt; 15%</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">CONDITION</label>
                <select
                  value={ruleCondition}
                  onChange={(e) => setRuleCondition(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold focus:outline-none focus:border-[#c6ff34] cursor-pointer animate-none bg-none"
                >
                  <option value=">">&gt; (Is Greater Than)</option>
                  <option value="<">&lt; (Is Less Than)</option>
                  <option value="drops below">Drops Below</option>
                  <option value="rises above">Rises Above</option>
                  <option value="crosses above">Crosses Above</option>
                  <option value="crosses below">Crosses Below</option>
                  <option value="deviates by">Deviates By</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">TRIGGER VALUE</label>
                <input
                  type="text"
                  placeholder="e.g. 5%, 30, 0.05%"
                  value={ruleValue}
                  onChange={(e) => setRuleValue(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold placeholder-zinc-700 focus:outline-none focus:border-[#c6ff34]"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block">THEN ACTION</label>
                <select
                  value={ruleAction}
                  onChange={(e) => setRuleAction(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 font-bold focus:outline-none focus:border-[#c6ff34] cursor-pointer animate-none bg-none"
                >
                  <option value="Pause TON Grid Bot">Pause TON Grid Bot</option>
                  <option value="Send Telegram Alert">Send Telegram Alert</option>
                  <option value="Buy SOL">Market Buy SOL</option>
                  <option value="Activate Kill Switch">Trigger Kill Switch</option>
                  <option value="Scale Out 50% Exposure">Scale Out 50% Exposure</option>
                  <option value="Leverage Hedge Short BTC">Leverage Hedge Short BTC</option>
                  <option value="Post Webhook Payload">Post Webhook Payload</option>
                  <option value="Rebalance to Neutral">Rebalance to Neutral</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={networkOffline || ruleSubmitting}
              className={`w-full bg-zinc-950 hover:bg-zinc-900 border border-zinc-800 text-white font-bold text-xs py-3 rounded-xl transition-all cursor-pointer flex items-center justify-center gap-1.5 uppercase ${
                networkOffline ? "opacity-40 cursor-not-allowed" : ""
              }`}
            >
              <Plus className="w-4 h-4 text-[#c6ff34]" />
              {ruleSubmitting ? "ADDING TRIGGER RULE..." : "ADD ALERT TRIGGER RULE"}
            </button>
          </form>

          {/* Active rules list */}
          <div className="space-y-2 pt-2 border-t border-zinc-900">
            <span className="text-[9px] uppercase font-black text-zinc-500 tracking-wider block">
              ACTIVE TRADING ALERTS & WEBHOOKS ({rules.length})
            </span>

            {rules.length === 0 ? (
              <div className="text-center py-4 bg-zinc-950/40 border border-dashed border-zinc-800 rounded-xl">
                <p className="text-[10px] text-zinc-600 font-bold uppercase tracking-wider">
                  No automated rules configured
                </p>
              </div>
            ) : (
              <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    className="flex items-center justify-between p-3 bg-zinc-950 border border-zinc-800 rounded-xl text-xs font-mono"
                  >
                    <div className="flex-1 min-w-0 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#14b8a6]"></span>
                        <span className="text-[10px] font-black text-[#c6ff34] uppercase tracking-wider">
                          IF
                        </span>
                        <span className="text-white font-bold truncate">
                          {rule.metric} {rule.condition} {rule.value}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1 text-[10px] text-zinc-400">
                        <span className="font-bold text-zinc-600">THEN</span>
                        <span className="bg-[#14b8a6]/10 text-[#14b8a6] border border-[#14b8a6]/20 px-1.5 py-0.2 rounded text-[9px] font-sans font-bold">
                          {rule.action}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Toggle active switch */}
                      <button
                        type="button"
                        onClick={() => handleToggleRule(rule.id)}
                        disabled={networkOffline}
                        className={`relative inline-flex h-4.5 w-8 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          rule.active ? "bg-[#c6ff34]" : "bg-zinc-800"
                        } ${networkOffline ? "opacity-40 cursor-not-allowed" : ""}`}
                      >
                        <span
                          className={`pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full bg-black shadow transition duration-200 ease-in-out ${
                            rule.active ? "translate-x-3.5" : "translate-x-0"
                          }`}
                        />
                      </button>

                      {/* Delete button */}
                      <button
                        type="button"
                        onClick={() => handleDeleteRule(rule.id)}
                        disabled={networkOffline}
                        className={`text-zinc-600 hover:text-red-400 p-1 rounded hover:bg-zinc-900 transition-colors ${
                          networkOffline ? "opacity-30 cursor-not-allowed" : ""
                        }`}
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

      {/* Panic Switch */}
      <div className="pt-2">
        {networkOffline ? (
          <button
            type="button"
            disabled
            className="w-full border border-zinc-800 text-zinc-600 font-bold text-xs py-4.5 rounded-xl uppercase tracking-wider cursor-not-allowed opacity-40 flex items-center justify-center gap-2"
          >
            <span>🚨</span> KILL SWITCH DISABLED (OFFLINE)
          </button>
        ) : panicState === "idle" ? (
          <button
            type="button"
            onClick={handlePanicClick}
            className="w-full bg-[#1c2023] border border-red-500/70 hover:bg-red-500/10 text-red-400 font-black text-xs py-4.5 px-4 rounded-xl shadow-lg shadow-red-500/5 hover:shadow-red-500/10 active:scale-[0.98] transition-all uppercase tracking-widest flex items-center justify-center gap-2 border-2"
            id="panic_sell_btn"
          >
            <AlertOctagon className="w-4 h-4 animate-pulse" />
            PANIC: CLOSE ALL TRADES
          </button>
        ) : panicState === "armed" ? (
          <button
            type="button"
            onClick={handlePanicClick}
            className="w-full bg-red-600 text-white hover:bg-red-700 font-bold text-xs py-4.5 px-4 rounded-xl transition-all uppercase tracking-wider cursor-pointer animate-pulse flex items-center justify-center gap-2 border border-red-500"
          >
            <span>⚠️</span> CONFIRM SYSTEM SHUTDOWN
          </button>
        ) : (
          <button
            type="button"
            disabled
            className="w-full bg-zinc-900 border border-zinc-800 text-red-500 font-bold text-xs py-4.5 px-4 rounded-xl transition-all uppercase tracking-wider flex items-center justify-center gap-2"
          >
            <span className="animate-spin mr-1">⏳</span> SECURING SYSTEM...
          </button>
        )}
        <p className="text-center text-[10px] text-zinc-600 mt-2 font-mono">
          Aegis Quant v2.4.12-stable • Standby Node online
        </p>
      </div>

      {/* Reset settings confirmation modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 bg-black/85 flex items-center justify-center p-4 z-50 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#1c2023] border-2 border-[#c6ff34]/20 rounded-2xl w-full max-w-sm overflow-hidden p-6 space-y-5 shadow-2xl shadow-black">
            <div className="flex items-center gap-2.5 text-[#c6ff34]">
              <Sliders className="w-6 h-6 shrink-0" />
              <h3 className="font-black text-sm uppercase tracking-wider">RESET RISK SETTINGS?</h3>
            </div>
            
            <p className="text-xs text-zinc-300 leading-relaxed font-sans">
              This will restore Max Allocation, Max Concurrent Trades, Stop Loss, Take Profit, Trailing Stop, and whitelists to system aggressive/conservative defaults.
            </p>

            <div className="grid grid-cols-2 gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowResetConfirm(false)}
                className="py-2.5 rounded-xl border border-zinc-800 text-zinc-400 hover:text-white font-bold text-xs uppercase font-mono tracking-wider transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  if (onResetSettings) {
                    onResetSettings();
                  }
                  setShowResetConfirm(false);
                }}
                className="py-2.5 rounded-xl bg-[#c6ff34] text-black font-bold text-xs uppercase tracking-wider transition-all hover:bg-[#b0f020] cursor-pointer shadow-lg shadow-[#c6ff34]/20"
              >
                CONFIRM RESET
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Live trading warning modal */}
      {showLiveWarningModal && (
        <div className="fixed inset-0 bg-black/85 flex items-center justify-center p-4 z-50 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#1c2023] border-2 border-red-500/40 rounded-2xl w-full max-w-sm overflow-hidden p-6 space-y-5 shadow-2xl shadow-red-500/10">
            <div className="flex items-center gap-3 text-red-500">
              <AlertOctagon className="w-8 h-8 shrink-0 animate-bounce" />
              <div>
                <h3 className="font-black text-sm uppercase tracking-wider">CRITICAL RISK ALERT</h3>
                <p className="text-[10px] text-red-400 font-mono">LIVE EXECUTION WARNING</p>
              </div>
            </div>
            
            <p className="text-xs text-zinc-300 leading-relaxed font-sans">
              You are transitioning from <span className="text-[#c6ff34] font-bold">Paper Simulator</span> to <span className="text-red-400 font-bold">Live real-money markets</span>.
            </p>
            
            <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2">
              <p className="text-[10px] text-zinc-400 leading-normal">
                Aegis Quant will route trade instructions using real capital from connected TON wallet and manual/CeFi Exchange keys. Financial risk is real.
              </p>
            </div>

            <div className="space-y-3">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={understandRisks}
                  onChange={(e) => setUnderstandRisks(e.target.checked)}
                  className="mt-0.5 rounded border-zinc-800 text-red-500 focus:ring-red-500/40 bg-zinc-950"
                />
                <span className="text-[10px] text-zinc-400 leading-tight font-semibold">
                  I understand and accept full risk of capital loss in live financial environments.
                </span>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowLiveWarningModal(false);
                  setUnderstandRisks(false);
                }}
                className="py-2.5 rounded-xl border border-zinc-800 text-zinc-400 hover:text-white font-bold text-xs uppercase font-mono tracking-wider transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!understandRisks}
                onClick={() => {
                  if (onToggleTradeMode) {
                    onToggleTradeMode("LIVE");
                  }
                  setShowLiveWarningModal(false);
                  setUnderstandRisks(false);
                }}
                className={`py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center ${
                  understandRisks
                    ? "bg-red-500 text-white hover:bg-red-600 cursor-pointer shadow-lg shadow-red-500/20"
                    : "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                }`}
              >
                DEPLOY LIVE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
