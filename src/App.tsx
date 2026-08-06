import React, { useState, useEffect } from "react";
import { UserState, RiskSettings } from "./types";
import Dashboard from "./components/Dashboard";
import Wallet from "./components/Wallet";
import Strategy from "./components/Strategy";
import Intel from "./components/Intel";
import Logs from "./components/Logs";
import { setSessionToken, getSessionToken, clearSession, apiJson, apiFetch, getInitData, getApiBase } from "./api/client";
import { Home, Wallet as WalletIcon, Sliders, Zap, History, RefreshCw } from "lucide-react";

const DEFAULT_USER_STATE: UserState = {
  walletConnected: false,
  walletAddress: "",
  network: "TON",
  balance: 0,
  portfolioValue: 0,
  dailyProfitLoss: 0,
  pnlPercentage: 0,
  agentActive: false,
  agentTarget: "Trend Scrape + Kronos",
  riskLimit: 10,
  tradeMode: "PAPER",
  currency: "USD",
  nairaRate: 1520,
  positions: [],
  connectedCeFi: {
    bybit: { connected: false, encryptedKeys: null },
    okx: { connected: false, encryptedKeys: null }
  }
};

export default function App() {
  const [currentTab, setCurrentTab] = useState<"home" | "wallet" | "strategy" | "intel" | "logs" | "admin">("home");
  const [loading, setLoading] = useState<boolean>(true);
  const [stateError, setStateError] = useState<string | null>(null);

  // App core state — initialized empty, populated from API
  const [userState, setUserState] = useState<UserState>({ ...DEFAULT_USER_STATE });
  const [riskSettings, setRiskSettings] = useState<RiskSettings>({
    maxAllocation: 15,
    maxConcurrentTrades: 3,
    riskLevel: "AGGRESSIVE",
    stopLoss: 3.0,
    takeProfit: 6.5,
    trailingStop: 1.0,
    whitelist: ["SOL", "TON", "ETH", "BTC", "PEPE", "BONK", "WIF"],
    baseTradeUsd: 10.0
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

  // ── Auth / Session Init ────────────────────────────────────────

  const initSession = async (): Promise<boolean> => {
    // If we already have a valid token, try to refresh it
    const existingToken = getSessionToken();
    if (existingToken) {
      try {
        const res = await apiFetch("/api/auth/refresh", { method: "POST" });
        if (res.ok) {
          const json = await res.json();
          if (json.status === "success") {
            setSessionToken(json.session_token);
            return true;
          }
        }
      } catch {
        // Token stale, will re-init below
      }
      // Token is invalid, clear it
      clearSession();
    }

    // No token or stale — send Telegram initData for /auth/init
    const initData = getInitData();

    if (!initData) {
      console.warn("[Auth] No Telegram initData found — running in demo mode");
      return false;
    }

    try {
      const res = await apiFetch("/api/auth/init", {
        method: "POST",
        body: JSON.stringify({}),
      });

      if (res.ok) {
        const json = await res.json();
        if (json.status === "success" && json.session_token) {
          setSessionToken(json.session_token);
          return true;
        }
      }
    } catch (e) {
      console.error("[Auth] init failed:", e);
    }

    return false;
  };

  // ── Data Fetch ────────────────────────────────────────────────

  const fetchState = async () => {
    try {
      const [stateRes, riskRes] = await Promise.all([
        apiJson<any>("/api/state"),
        apiJson<any>("/api/risk-profile")
      ]);
      
      if (stateRes.data || stateRes.userState) {
        const uState = stateRes.data || stateRes.userState;
        setUserState(prev => ({ ...prev, ...uState }));
      }
      if (riskRes.data) {
        setRiskSettings(riskRes.data);
      }
    } catch (err) {
      console.error("[State] Could not load user state:", err);
      setStateError("Failed to load state");
    } finally {
      setLoading(false);
    }
  };

  // ── Connectivity Monitoring ───────────────────────────────────

  useEffect(() => {
    const checkConnectivity = async () => {
      if (!window.navigator.onLine) {
        setNetworkOffline(true);
        return;
      }
      try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 2500);
        const res = await fetch(`${getApiBase()}/health`, { signal: controller.signal, cache: "no-store" });
        clearTimeout(id);
        setNetworkOffline(!res.ok);
      } catch {
        setNetworkOffline(true);
      }
    };

    checkConnectivity();
    window.addEventListener("online", () => checkConnectivity());
    window.addEventListener("offline", () => setNetworkOffline(true));
    const interval = setInterval(checkConnectivity, 5000);

    return () => {
      window.removeEventListener("online", () => checkConnectivity());
      window.removeEventListener("offline", () => setNetworkOffline(true));
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!networkOffline) {
      fetchState();
    }
  }, [networkOffline]);

  // ── On Mount: init session + fetch data ────────────────────────

  useEffect(() => {
    // Tell Telegram the Mini App is ready and expand to full height.
    try {
      const webapp = window.Telegram?.WebApp;
      webapp?.ready();
      webapp?.expand();
      webapp?.setHeaderColor("#171717");
      webapp?.setBackgroundColor("#171717");
    } catch {}
  }, []);

  useEffect(() => {
    let mounted = true;
    initSession().then(authenticated => {
      if (mounted) {
        setLoading(true); // reset loading for real fetch
        fetchState();
      }
    }).catch(() => {
      if (mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  // ── Handlers ──────────────────────────────────────────────────

  const handleToggleAgent = async (active: boolean) => {
    setUserState(prev => ({ ...prev, agentActive: active }));
    try {
      await apiJson("/api/toggle-agent", { method: "POST", body: JSON.stringify({ active }) });
      fetchState();
    } catch (err) {
      console.error("Agent toggle failed", err);
      setUserState(prev => ({ ...prev, agentActive: !active })); // revert
    }
  };

  const handleUpdateRiskSettings = async (updates: Partial<RiskSettings>) => {
    setRiskSettings(prev => ({ ...prev, ...updates }));
    try {
      await apiJson("/api/risk-profile", { method: "POST", body: JSON.stringify(updates) });
    } catch (err) {
      console.error("Strategy update failed", err);
    }
  };

  const handleToggleTradeMode = async (mode: "PAPER" | "LIVE") => {
    setUserState(prev => ({ ...prev, tradeMode: mode }));
    try {
      await apiJson("/api/toggle-mode", { method: "POST", body: JSON.stringify({ mode }) });
    } catch (err) {
      console.error("Mode toggle failed", err);
    }
  };

  const handleToggleCurrency = async (currency: "USD" | "NGN") => {
    setUserState(prev => ({ ...prev, currency }));
    try {
      const json = await apiJson<any>("/api/toggle-currency", {
        method: "POST", body: JSON.stringify({ currency })
      });
      setUserState(prev => ({ ...prev, nairaRate: json.nairaRate || prev.nairaRate }));
    } catch (err) {
      console.error("Currency toggle failed", err);
    }
  };

  const handleUpdatePaperBalance = async (newBalance: number) => {
    setUserState(prev => ({ ...prev, balance: newBalance }));
    try {
      await apiJson("/api/update-paper-balance", { method: "POST", body: JSON.stringify({ balance: newBalance }) });
    } catch (err) {
      console.error("Failed to update paper balance", err);
    }
  };

  const handleResetSettings = async () => {
    try {
      const json = await apiJson<any>("/api/reset-settings", { method: "POST" });
      if (json.status === "success" && json.data) {
        setRiskSettings(json.data);
      }
    } catch (err) {
      console.error("Reset settings failed", err);
    }
  };

  const handlePanic = async () => {
    setUserState(prev => ({ ...prev, positions: [], agentActive: false }));
    try {
      await apiJson("/api/panic", { method: "POST" });
      fetchState();
    } catch (err) {
      console.error("Panic trigger failed", err);
    }
  };

  const handleConnectWallet = async (network: string, address: string) => {
    setUserState(prev => ({
      ...prev, walletConnected: true, walletAddress: address, network
    }));
    try {
      await apiJson("/api/wallet-connect", {
        method: "POST",
        body: JSON.stringify({ network, address }),
      });
    } catch (err) {
      console.error("Manual wallet connect failed", err);
    }
  };

  const handleLinkExchangeManual = async (exchange: string, apiKey: string, apiSecret: string) => {
    try {
      await apiJson("/api/exchange-manual", {
        method: "POST",
        body: JSON.stringify({ exchange, apiKey, apiSecret }),
      });
      fetchState();
    } catch (err) {
      console.error("Manual keys save failed", err);
    }
  };

  const handleDisconnectExchange = async (exchange: string) => {
    try {
      await apiJson("/api/exchange-disconnect", {
        method: "POST",
        body: JSON.stringify({ exchange }),
      });
      fetchState();
    } catch (err) {
      console.error("Disconnect exchange failed", err);
    }
  };

  const handleActivateSignalAgent = async (ticker: string, size: number) => {
    try {
      const res = await apiFetch("/api/logs", {
        method: "POST",
        body: JSON.stringify({
          type: "BUY", pair: `${ticker}/USDT`, volume: `$${size.toFixed(2)}`, status: "Filled"
        })
      });
      
      // Optimistic position add — server will also create DB entry
      const newPosition = {
        id: String(Date.now()),
        pair: `${ticker}/USDT`,
        size,
        pnl: 0,
        buyPrice: 0,
        currentPrice: 0,
        logo: ticker.slice(0, 1).toUpperCase()
      };
      setUserState(prev => ({
        ...prev,
        positions: [...prev.positions, newPosition]
      }));
      setCurrentTab("home");
    } catch (err) {
      console.error("Failed to activate agent", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#101416] text-zinc-100 flex justify-center selection:bg-[#c6ff34] selection:text-black">
      <div className="w-full max-w-[480px] min-h-screen flex flex-col bg-[#171717] relative shadow-2xl shadow-black border-x border-zinc-900 px-4">
        
        {/* Main Content Render Area */}
        <div className="flex-1 overflow-y-auto no-scrollbar pt-2 relative">
          {/* Offline Banner */}
          {networkOffline && (
            <div className="absolute inset-0 z-50 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center space-y-5 animate-fade-in">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center animate-pulse shadow-lg shadow-amber-500/5">
                <span className="text-3xl">🔌</span>
              </div>
              <div className="space-y-2">
                <h3 className="font-sans text-sm font-black uppercase tracking-wider text-amber-400">CONNECTIVITY STANDBY</h3>
                <p className="text-xs text-zinc-400 max-w-[280px] mx-auto leading-relaxed">
                  The connection node was interrupted. All trading vectors have been secured. Restore connection to resume.
                </p>
              </div>

              <button 
                onClick={async () => {
                  try {
                    const res = await fetch(`${getApiBase()}/health`, { cache: "no-store" });
                    if (res.ok) {
                      setNetworkOffline(false);
                      fetchState();
                    }
                  } catch {}
                }}
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

        {/* Bottom Fixed Navigation Bar */}
        <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] h-[72px] bg-[#1c2023] border-t border-zinc-800 flex items-center justify-around px-2 z-50 shadow-2xl shadow-black rounded-t-2xl">
          {[
            { tab: "home" as const, icon: Home, label: "Home" },
            { tab: "wallet" as const, icon: WalletIcon, label: "Wallet" },
            { tab: "strategy" as const, icon: Sliders, label: "Strategy" },
            { tab: "intel" as const, icon: Zap, label: "Intel" },
            { tab: "logs" as const, icon: History, label: "Logs" },
          ].map(({ tab, icon: Icon, label }) => (
            <button
              key={tab}
              onClick={() => setCurrentTab(tab)}
              className={`flex flex-col items-center justify-center gap-1 w-14 transition-all duration-200 ${
                currentTab === tab ? "text-[#c6ff34] scale-105" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-bold tracking-wider">{label}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
