import React, { useState, useEffect } from "react";
import { UserState, RiskSettings } from "./types";
import Dashboard from "./components/Dashboard";
import Wallet from "./components/Wallet";
import Strategy from "./components/Strategy";
import Intel from "./components/Intel";
import Logs from "./components/Logs";
import { Home, Wallet as WalletIcon, Sliders, Zap, History, Shield, RefreshCw } from "lucide-react";

export default function App() {
  const [currentTab, setCurrentTab] = useState<"home" | "wallet" | "strategy" | "intel" | "logs">("home");
  const [loading, setLoading] = useState<boolean>(true);
  const [stateError, setStateError] = useState<string | null>(null);

  // App core state
  const [userState, setUserState] = useState<UserState>({
    walletConnected: true,
    walletAddress: "UQAzf88d7H6kR39_TqW7Lp93mJ21_z_Xy89Yd",
    network: "TON",
    balance: 124.50,
    portfolioValue: 4812.90,
    dailyProfitLoss: 520.10,
    pnlPercentage: 14.2,
    agentActive: true,
    agentTarget: "Trend Scrape + Kronos",
    riskLimit: 10,
    tradeMode: "PAPER",
    currency: "USD",
    nairaRate: 1520,
    positions: [],
    connectedCeFi: {
      bybit: { connected: true, encryptedKeys: "aes-256:simulated" },
      okx: { connected: false, encryptedKeys: null }
    }
  });

  // Backtest result overlay state
  const [backtestResult, setBacktestResult] = useState<{
    backtestCurve: any[];
    benchmarkCurve: any[];
    metrics: any;
    active: boolean;
  } | null>(null);

  // Network Offline connection loss simulation state
  const [networkOffline, setNetworkOffline] = useState<boolean>(false);

  const [riskSettings, setRiskSettings] = useState<RiskSettings>({
    maxAllocation: 15,
    maxConcurrentTrades: 3,
    riskLevel: "AGGRESSIVE",
    stopLoss: 3.0,
    takeProfit: 6.5,
    trailingStop: 1.0,
    whitelist: ["SOL", "TON", "ETH", "BTC", "PEPE", "BONK", "WIF"]
  });

  const fetchState = async () => {
    try {
      const [stateRes, riskRes] = await Promise.all([
        fetch("/api/state"),
        fetch("/api/risk-profile")
      ]);
      if (stateRes.ok && riskRes.ok) {
        const stateJson = await stateRes.json();
        const riskJson = await riskRes.json();
        if (stateJson.status === "success") {
          const uState = stateJson.data || stateJson.userState;
          if (uState) {
            setUserState(uState);
          }
        }
        if (riskJson.status === "success" && riskJson.data) {
          setRiskSettings(riskJson.data);
        }
      }
    } catch (err) {
      console.error("Could not coordinate full state with background server", err);
    } finally {
      setLoading(false);
    }
  };

  // Real-time Internet & Backend connectivity monitoring (watches real navigator and polls backend API)
  useEffect(() => {
    const checkConnectivity = async () => {
      // 1. Check window.navigator.onLine first
      if (!window.navigator.onLine) {
        setNetworkOffline(true);
        return;
      }

      // 2. Ping the backend health endpoint
      try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 2500); // 2.5 seconds timeout
        const res = await fetch("/api/health", { 
          signal: controller.signal,
          headers: { 'Cache-Control': 'no-cache' }
        });
        clearTimeout(id);
        if (res.ok) {
          setNetworkOffline(false);
        } else {
          setNetworkOffline(true);
        }
      } catch (err) {
        setNetworkOffline(true);
      }
    };

    // Run immediately on mount
    checkConnectivity();

    // Event listeners for browser online/offline events
    const handleOnline = () => {
      checkConnectivity();
    };
    const handleOffline = () => {
      setNetworkOffline(true);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Periodic polling check every 5 seconds to detect backend/internet drops
    const interval = setInterval(checkConnectivity, 5000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(interval);
    };
  }, []);

  const handleRestoreCheck = async () => {
    if (!window.navigator.onLine) {
      alert("Browser reports you are still offline. Please verify your internet connection.");
      return;
    }
    try {
      const res = await fetch("/api/health", { headers: { 'Cache-Control': 'no-cache' } });
      if (res.ok) {
        setNetworkOffline(false);
        alert("✔ Connection successfully re-established!");
        fetchState();
      } else {
        alert("Backend is still unreachable. Reconnecting...");
      }
    } catch (err) {
      alert("Backend is still unreachable. Please verify server status.");
    }
  };

  useEffect(() => {
    if (!networkOffline) {
      fetchState();
    }
  }, [networkOffline]);

  // Handler to toggle automated trading agent
  const handleToggleAgent = async (active: boolean) => {
    // Optimistic update
    setUserState(prev => ({ ...prev, agentActive: active }));
    try {
      const res = await fetch("/api/toggle-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active })
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Agent toggle failed", err);
    }
  };

  // Handler to update strategy settings
  const handleUpdateRiskSettings = async (updates: Partial<RiskSettings>) => {
    const updated = { ...riskSettings, ...updates };
    // Optimistic update
    setRiskSettings(updated);
    try {
      const res = await fetch("/api/risk-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Strategy update failed", err);
    }
  };

  // Handler to toggle trade mode (paper/live)
  const handleToggleTradeMode = async (mode: "PAPER" | "LIVE") => {
    setUserState(prev => ({ ...prev, tradeMode: mode }));
    try {
      const res = await fetch("/api/toggle-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode })
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Mode toggle failed", err);
    }
  };

  // Handler to toggle currency
  const handleToggleCurrency = async (currency: "USD" | "NGN") => {
    setUserState(prev => ({ ...prev, currency }));
    try {
      const res = await fetch("/api/toggle-currency", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currency })
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Currency toggle failed", err);
    }
  };

  // Handler to update paper trading balance
  const handleUpdatePaperBalance = async (newBalance: number) => {
    setUserState(prev => ({ ...prev, balance: newBalance }));
    try {
      const res = await fetch("/api/update-paper-balance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ balance: newBalance })
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Failed to update paper balance", err);
    }
  };

  // Handler to reset settings to default
  const handleResetSettings = async () => {
    try {
      const res = await fetch("/api/reset-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        const json = await res.json();
        if (json.status === "success" && json.data) {
          setRiskSettings(json.data);
          alert("✔ Strategy and risk settings restored to system defaults.");
        }
      }
    } catch (err) {
      console.error("Reset settings failed", err);
    }
  };

  // Handler to close all trades under panic trigger
  const handlePanic = async () => {
    setUserState(prev => ({ ...prev, positions: [], agentActive: false }));
    try {
      const res = await fetch("/api/panic", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        fetchState();
        alert("🚨 PANIC CLOSE TRIGGERED: All active trade vectors terminated. Systems in secure standby.");
      }
    } catch (err) {
      console.error("Panic trigger failed", err);
    }
  };

  // Handler to link Web3 fallback address
  const handleConnectWallet = async (network: string, address: string) => {
    try {
      const res = await fetch("/api/wallet-connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ network, address })
      });
      if (res.ok) {
        fetchState();
      }
    } catch (err) {
      console.error("Manual wallet connect failed", err);
    }
  };

  // Handler to save manual API keys
  const handleLinkExchangeManual = async (exchange: string, apiKey: string, apiSecret: string) => {
    try {
      const res = await fetch("/api/exchange-manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exchange, apiKey, apiSecret })
      });
      if (res.ok) {
        fetchState();
        alert(`✔ ${exchange.toUpperCase()} API keys saved successfully with active AES-256 database protection.`);
      }
    } catch (err) {
      console.error("Manual keys save failed", err);
    }
  };

  // Handler to disconnect exchange integration
  const handleDisconnectExchange = async (exchange: string) => {
    try {
      const res = await fetch("/api/exchange-disconnect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exchange })
      });
      if (res.ok) {
        fetchState();
        alert(`✔ ${exchange.toUpperCase()} exchange integration disconnected successfully.`);
      }
    } catch (err) {
      console.error("Disconnect exchange failed", err);
    }
  };

  // Handler to launch quantitative agent for selected token signal
  const handleActivateSignalAgent = async (ticker: string, size: number) => {
    // Log immediate action to logs
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "BUY",
          pair: `${ticker}/USDT`,
          volume: `$${size.toFixed(2)}`,
          status: "Filled"
        })
      });
      if (res.ok) {
        // Mock add position state
        const newPosition = {
          id: String(Date.now()),
          pair: `${ticker}/USDT`,
          size: size,
          pnl: 0.0,
          buyPrice: ticker === "WIF" ? 2.15 : 7.20,
          currentPrice: ticker === "WIF" ? 2.15 : 7.20,
          logo: ticker.slice(0, 1)
        };
        setUserState(prev => ({
          ...prev,
          positions: [...prev.positions, newPosition]
        }));
        
        // Switch tab to Home so they can watch the live position immediately
        setCurrentTab("home");
        alert(`⚡ Quantitative Agent Activated for $${ticker} with size $${size.toFixed(2)}. Monitoring position.`);
      }
    } catch (err) {
      console.error("Failed to activate agent", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#101416] text-zinc-100 flex justify-center selection:bg-[#c6ff34] selection:text-black">
      {/* Centered TMA phone viewport layout on wider monitors, fluid on real phones */}
      <div className="w-full max-w-[480px] min-h-screen flex flex-col bg-[#171717] relative shadow-2xl shadow-black border-x border-zinc-900 px-4">
        
        {/* Main Content Render Area */}
        <div className="flex-1 overflow-y-auto no-scrollbar pt-2 relative">
          {/* Graceful Network & Offline State Banner Overlay (Full-screen blocking) */}
          {networkOffline && (
            <div className="absolute inset-0 z-50 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center space-y-5 animate-fade-in">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center animate-pulse shadow-lg shadow-amber-500/5">
                <span className="text-3xl">🔌</span>
              </div>
              <div className="space-y-2">
                <h3 className="font-sans text-sm font-black uppercase tracking-wider text-amber-400">CONNECTIVITY STANDBY</h3>
                <p className="text-xs text-zinc-400 max-w-[280px] mx-auto leading-relaxed">
                  The connection node was interrupted. All trading vectors have been secured. Restore connection or verify servers to resume actions.
                </p>
                <div className="flex items-center justify-center gap-1.5 pt-2 text-[9px] text-zinc-500 font-mono uppercase font-bold tracking-wider">
                  <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-ping"></span>
                  <span>Polling backup Standby gateway...</span>
                </div>
              </div>

              <button 
                onClick={handleRestoreCheck} 
                className="w-full max-w-[220px] bg-amber-500 text-black font-black py-3 rounded-xl uppercase tracking-wider hover:brightness-110 active:scale-[0.98] transition-all text-[11px] cursor-pointer shadow-lg shadow-amber-500/20"
              >
                RE-ESTABLISH CONNECTION
              </button>
            </div>
          )}

          {loading ? (
            <div className="h-[75vh] flex flex-col items-center justify-center space-y-3">
              <RefreshCw className="w-8 h-8 text-[#c6ff34] animate-spin" />
              <p className="text-xs text-zinc-500 font-mono uppercase tracking-widest font-black">AEGIS QUANT BOOTING...</p>
            </div>
          ) : (
            <>
              {currentTab === "home" && (
                <Dashboard
                  userState={userState}
                  onToggleAgent={handleToggleAgent}
                  onNavigateToStrategy={() => setCurrentTab("strategy")}
                  onNavigateToLogs={() => setCurrentTab("logs")}
                  onPanic={handlePanic}
                  backtestResult={backtestResult}
                  networkOffline={networkOffline}
                  onToggleNetworkOffline={setNetworkOffline}
                />
              )}
              {currentTab === "wallet" && (
                <Wallet
                  userState={userState}
                  onConnectWallet={handleConnectWallet}
                  onLinkExchangeManual={handleLinkExchangeManual}
                  onDisconnectExchange={handleDisconnectExchange}
                  onNavigateToLogs={() => setCurrentTab("logs")}
                  networkOffline={networkOffline}
                  onUpdatePaperBalance={handleUpdatePaperBalance}
                />
              )}
              {currentTab === "strategy" && (
                <Strategy
                  riskSettings={riskSettings}
                  onUpdateSettings={handleUpdateRiskSettings}
                  onPanic={handlePanic}
                  tradeMode={userState.tradeMode}
                  onToggleTradeMode={handleToggleTradeMode}
                  onResetSettings={handleResetSettings}
                  currency={userState.currency}
                  nairaRate={userState.nairaRate}
                  onToggleCurrency={handleToggleCurrency}
                  backtestResult={backtestResult}
                  onUpdateBacktest={setBacktestResult}
                  networkOffline={networkOffline}
                />
              )}
              {currentTab === "intel" && (
                <Intel 
                  onActivateAgent={handleActivateSignalAgent} 
                  networkOffline={networkOffline}
                />
              )}
              {currentTab === "logs" && <Logs />}
            </>
          )}
        </div>

        {/* Bottom Fixed Navigation Bar conforming to guidelines */}
        <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] h-[72px] bg-[#1c2023] border-t border-zinc-800 flex items-center justify-around px-2 z-50 shadow-2xl shadow-black rounded-t-2xl">
          <button
            onClick={() => setCurrentTab("home")}
            className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
              currentTab === "home" ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Home className="w-5 h-5" />
            <span className="text-[10px] font-bold tracking-wider">Home</span>
          </button>

          <button
            onClick={() => setCurrentTab("wallet")}
            className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
              currentTab === "wallet" ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <WalletIcon className="w-5 h-5" />
            <span className="text-[10px] font-bold tracking-wider">Wallet</span>
          </button>

          <button
            onClick={() => setCurrentTab("strategy")}
            className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
              currentTab === "strategy" ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Sliders className="w-5 h-5" />
            <span className="text-[10px] font-bold tracking-wider">Strategy</span>
          </button>

          <button
            onClick={() => setCurrentTab("intel")}
            className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
              currentTab === "intel" ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Zap className="w-5 h-5" />
            <span className="text-[10px] font-bold tracking-wider">Intel</span>
          </button>

          <button
            onClick={() => setCurrentTab("logs")}
            className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
              currentTab === "logs" ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <History className="w-5 h-5" />
            <span className="text-[10px] font-bold tracking-wider">Logs</span>
          </button>
        </nav>
      </div>
    </div>
  );
}
