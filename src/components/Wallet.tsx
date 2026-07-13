import React, { useState } from "react";
import { Link, Wallet as WalletIcon, Shield, Check, ExternalLink, HelpCircle, Eye, Trash2 } from "lucide-react";
import { UserState } from "../types";

interface WalletProps {
  userState: UserState;
  onConnectWallet: (network: string, address: string) => void;
  onLinkExchangeManual: (exchange: string, key: string, secret: string) => void;
  onDisconnectExchange: (exchange: string) => void;
  onNavigateToLogs: () => void;
  networkOffline: boolean;
  onUpdatePaperBalance?: (balance: number) => void;
}

export default function Wallet({ 
  userState, 
  onConnectWallet, 
  onLinkExchangeManual, 
  onDisconnectExchange, 
  onNavigateToLogs, 
  networkOffline,
  onUpdatePaperBalance 
}: WalletProps) {
  const [fallbackNetwork, setFallbackNetwork] = useState<string>("TON");
  const [fallbackAddress, setFallbackAddress] = useState<string>("");
  const [exchange, setExchange] = useState<string>("bybit");
  const [apiKey, setApiKey] = useState<string>("");
  const [apiSecret, setApiKeySecret] = useState<string>("");

  const [simulatedConnecting, setSimulatedConnecting] = useState<boolean>(false);
  const [connectionSuccess, setConnectionSuccess] = useState<boolean>(false);

  const currency = userState.currency || "USD";
  const nairaRate = userState.nairaRate || 1520;

  const formatVal = (usdAmount: number) => {
    if (currency === "NGN") {
      const ngnAmount = usdAmount * nairaRate;
      return `₦${ngnAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `$${usdAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const handleSimulateNativeConnect = () => {
    setSimulatedConnecting(true);
    setTimeout(() => {
      onConnectWallet("TON", "UQAzf88d7H6kR39_TqW7Lp93mJ21_z_Xy89Yd");
      setSimulatedConnecting(false);
      setConnectionSuccess(true);
      setTimeout(() => setConnectionSuccess(false), 3000);
    }, 1500);
  };

  const handleSimulateEVMConnect = () => {
    setSimulatedConnecting(true);
    setTimeout(() => {
      onConnectWallet("ETH", "0x71C7656EC7ab88b098defB751B7401B5f6d8976F");
      setSimulatedConnecting(false);
      setConnectionSuccess(true);
      setTimeout(() => setConnectionSuccess(false), 3000);
    }, 1500);
  };

  const handleFallbackSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fallbackAddress) return;
    onConnectWallet(fallbackNetwork, fallbackAddress);
    setFallbackAddress("");
  };

  const handleManualKeysSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey || !apiSecret) return;
    onLinkExchangeManual(exchange, apiKey, apiSecret);
    setApiKey("");
    setApiKeySecret("");
  };

  const handleFastConnectBybit = () => {
    // Standard URL redirect helper for simulated Bybit FAST connect callback
    window.open("/auth/bybit/callback?code=fast-connect-code-92810", "_self");
  };

  const handleFastConnectOKX = () => {
    alert("Fast connect for OKX account is coming soon! Please use the CeFi Fallback Manual Input below.");
  };

  return (
    <div className="space-y-6 pb-24" id="wallet_screen">
      {/* Title */}
      <div className="flex items-center gap-2 h-14 border-b border-zinc-800 px-1">
        <WalletIcon className="w-5 h-5 text-[#c6ff34]" />
        <h2 className="font-sans text-lg font-black tracking-wider uppercase text-[#c6ff34]">WALLET & API HUB</h2>
      </div>

      {/* Web3 Connected Status Module */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
        <div className="flex justify-between items-start">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${userState.walletConnected ? "bg-[#c6ff34]" : "bg-red-500"} animate-pulse`}></span>
              <p className="font-mono text-xs font-bold text-[#c6ff34]">
                {userState.walletConnected ? `Connected (${userState.network})` : "Disconnected"}
              </p>
            </div>
            <p className="text-xs text-zinc-500 font-medium">
              {userState.network === "TON" ? "TON Mainnet" : "Ethereum L1 Mainnet"}
            </p>
          </div>
          {userState.walletConnected && (
            <div className="text-right">
              <p className="text-lg font-black text-white">
                {userState.network === "TON" ? `${userState.balance.toFixed(2)} TON` : "0.342 ETH"}
              </p>
              <p className="text-[10px] text-zinc-400">
                {userState.network === "TON" ? `~${formatVal(userState.balance * 7.0)}` : `~${formatVal(1120.40)}`}
              </p>
            </div>
          )}
        </div>

        {userState.walletConnected && (
          <div className="pt-3 border-t border-zinc-800 flex justify-between items-center text-xs">
            <span className="font-mono text-zinc-500 bg-zinc-950 px-2 py-1 rounded border border-zinc-800 text-[10px]">
              {userState.walletAddress.slice(0, 6)}...{userState.walletAddress.slice(-6)}
            </span>
            <button
              onClick={onNavigateToLogs}
              className="text-[#c6ff34] font-bold hover:underline flex items-center gap-1 text-[11px]"
            >
              View Transaction History →
            </button>
          </div>
        )}
      </div>

      {/* Paper Trading Balance Adjuster */}
      {userState.tradeMode === "PAPER" && (
        <div className="bg-[#1c2023] border border-[#c6ff34]/20 rounded-2xl p-5 space-y-4 animate-fade-in relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-[#c6ff34]/10 text-[#c6ff34] font-mono text-[8px] uppercase tracking-widest font-black px-2 py-1 rounded-bl-lg border-l border-b border-[#c6ff34]/20">
            SIMULATION MODE
          </div>
          <div className="space-y-1">
            <h3 className="font-sans text-xs font-black tracking-wider uppercase text-zinc-300">
              SET PAPER TRADING BALANCE
            </h3>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              You are currently running in <span className="text-[#c6ff34] font-bold">Paper Demo Trading</span>. Use the controls below to adjust your simulated Web3 wallet balance to test any size portfolio.
            </p>
          </div>
          
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 flex items-center justify-between">
              <span className="text-[10px] text-zinc-500 font-bold font-sans">PAPER BALANCE</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="0"
                  max="1000000"
                  step="1"
                  value={userState.balance}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    if (onUpdatePaperBalance) {
                      onUpdatePaperBalance(isNaN(val) ? 0 : val);
                    }
                  }}
                  className="bg-transparent text-right text-sm font-black font-mono text-[#c6ff34] focus:outline-none w-28 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <span className="text-[10px] text-[#c6ff34] font-black font-mono">{userState.network || "TON"}</span>
              </div>
            </div>

            {/* Quick preset chips */}
            <div className="grid grid-cols-3 gap-1">
              {[100, 500, 1000, 5000, 10000, 50000].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => onUpdatePaperBalance && onUpdatePaperBalance(preset)}
                  className="px-2 py-1.5 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 hover:border-zinc-700 rounded-lg text-[9px] font-mono font-bold text-zinc-400 hover:text-[#c6ff34] transition-all cursor-pointer active:scale-95 text-center"
                >
                  {preset >= 1000 ? `${preset/1000}k` : preset}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Web3 wallet Connection triggers */}
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Method 1: Telegram & TON Ecosystem</p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-zinc-400">Native, instant integration with TON wallet on Telegram ecosystem.</p>
            <button
              disabled={simulatedConnecting}
              onClick={handleSimulateNativeConnect}
              className="w-full bg-[#c6ff34] text-[#101416] font-bold text-xs py-3.5 px-4 rounded-xl hover:brightness-110 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              {simulatedConnecting ? "Authorizing..." : connectionSuccess ? "TON Wallet Connected!" : "CONNECT TON KEEPER / WALLET"}
            </button>
          </div>
        </div>

        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Method 2: EVM Multi-Chain</p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-zinc-400">Connect Trust Wallet, MetaMask, or Safepal using multi-chain standard.</p>
            <button
              disabled={simulatedConnecting}
              onClick={handleSimulateEVMConnect}
              className="w-full border border-zinc-700 text-white font-bold text-xs py-3.5 px-4 rounded-xl hover:bg-zinc-900 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              {simulatedConnecting ? "Connecting..." : "CONNECT VIA WALLETCONNECT"}
            </button>
          </div>
        </div>
      </div>

      {/* Watch only address fallback */}
      <div className="space-y-1">
        <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Web3 Fallback</p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
          <p className="text-xs text-zinc-400 leading-relaxed">
            If native Web3 wallet connection fails or is unavailable inside your Telegram sandbox, supply a public watch-only address to monitor signals.
          </p>
          <form onSubmit={handleFallbackSubmit} className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <select
                value={fallbackNetwork}
                onChange={(e) => setFallbackNetwork(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 font-semibold focus:outline-none focus:border-[#c6ff34]"
              >
                <option value="TON">TON</option>
                <option value="BSC">BSC</option>
                <option value="ETH">ETH</option>
              </select>
              <input
                type="text"
                value={fallbackAddress}
                onChange={(e) => setFallbackAddress(e.target.value)}
                placeholder="Paste Public Address..."
                className="col-span-2 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
              />
            </div>
            <button
              type="submit"
              className="w-full border border-zinc-800 text-zinc-300 font-bold text-xs py-3 px-4 rounded-xl hover:bg-zinc-900 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              <Eye className="w-3.5 h-3.5 text-[#c6ff34]" />
              MONITOR ADDRESS (READ-ONLY)
            </button>
          </form>
        </div>
      </div>

      {/* CeFi Link integration section */}
      <div className="space-y-4">
        <div className="flex justify-between items-center px-1">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">CeFi Key Vault & Permissions Manager</p>
          <span className="text-[9px] bg-[#c6ff34]/10 text-[#c6ff34] px-2 py-0.5 rounded font-black border border-[#c6ff34]/10">AES-256 SECURED</span>
        </div>
        
        {/* Connection Status & Disconnect Cards */}
        <div className="space-y-2">
          {/* Bybit Card */}
          <div className={`p-4 rounded-2xl border bg-zinc-900/30 flex items-center justify-between transition-all ${
            userState.connectedCeFi.bybit.connected ? "border-[#c6ff34]/40 bg-zinc-950/40" : "border-zinc-800"
          }`}>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${userState.connectedCeFi.bybit.connected ? "bg-[#c6ff34]" : "bg-zinc-600"}`}></span>
                <span className="text-sm font-black text-white">Bybit (Nigerian Supported Broker)</span>
              </div>
              <p className="text-[10px] text-zinc-400 font-mono flex items-center gap-2">
                {userState.connectedCeFi.bybit.connected 
                  ? "Vault ID: AEC-BYB-••••3a9d" 
                  : "Status: Standby Vault"}
                {userState.connectedCeFi.bybit.connected && (
                  <span className="bg-emerald-500/10 text-emerald-400 text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border border-emerald-500/10">READ & TRADE</span>
                )}
              </p>
            </div>
            {userState.connectedCeFi.bybit.connected ? (
              <button
                onClick={() => onDisconnectExchange("bybit")}
                className="p-2.5 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 active:scale-95 transition-all cursor-pointer"
                title="Disconnect Exchange"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleFastConnectBybit}
                className="text-[10px] font-black uppercase text-[#101416] bg-[#c6ff34] px-3 py-1.5 rounded-lg hover:brightness-110 active:scale-95 transition-all shadow-md shadow-[#c6ff34]/15 cursor-pointer"
              >
                FAST LINK
              </button>
            )}
          </div>

          {/* OKX Card */}
          <div className={`p-4 rounded-2xl border bg-zinc-900/30 flex items-center justify-between transition-all ${
            userState.connectedCeFi.okx.connected ? "border-[#c6ff34]/40 bg-zinc-950/40" : "border-zinc-800"
          }`}>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${userState.connectedCeFi.okx.connected ? "bg-[#c6ff34]" : "bg-zinc-600"}`}></span>
                <span className="text-sm font-black text-white">OKX (Nigerian Supported Broker)</span>
              </div>
              <p className="text-[10px] text-zinc-400 font-mono flex items-center gap-2">
                {userState.connectedCeFi.okx.connected 
                  ? "Vault ID: AEC-OKX-••••48c2" 
                  : "Status: Standby Vault"}
                {userState.connectedCeFi.okx.connected && (
                  <span className="bg-emerald-500/10 text-emerald-400 text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border border-emerald-500/10">READ & TRADE</span>
                )}
              </p>
            </div>
            {userState.connectedCeFi.okx.connected ? (
              <button
                onClick={() => onDisconnectExchange("okx")}
                className="p-2.5 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 active:scale-95 transition-all cursor-pointer"
                title="Disconnect Exchange"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleFastConnectOKX}
                className="text-[10px] font-black uppercase text-zinc-300 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900 px-3 py-1.5 rounded-lg active:scale-95 transition-all cursor-pointer"
              >
                FAST LINK
              </button>
            )}
          </div>
        </div>

        {/* Manual Input Credentials Settings & Permission Guards */}
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-xl">
          <div>
            <h4 className="text-xs uppercase tracking-wider text-white font-black">API Credential Vault Panel</h4>
            <p className="text-[10px] text-zinc-500 mt-0.5">Securely map keys for high-performance Nigerian accepted crypto brokers</p>
          </div>
          <form onSubmit={handleManualKeysSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase font-black text-zinc-400 px-1">Exchange Provider</label>
              <select
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 font-semibold focus:outline-none focus:border-[#c6ff34]"
              >
                <option value="bybit">Bybit (Accepted / Recommended)</option>
                <option value="okx">OKX (Accepted / Recommended)</option>
                <option value="binance">Binance (Accepted / Recommended)</option>
                <option value="dydx">dYdX (Accepted / Fully Decentralized)</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[10px] uppercase font-black text-zinc-400 px-1">API Key</label>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="e.g. ab837a29dc..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase font-black text-zinc-400 px-1">API Secret</label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiKeySecret(e.target.value)}
                  placeholder="••••••••••••••••••••"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
                />
              </div>
            </div>

            {/* Optional Passphrase/Memo Field */}
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase font-black text-zinc-400 px-1">Optional Passphrase / Memo (OKX / dYdX)</label>
              <input
                type="password"
                placeholder="Passphrase (leave blank if Bybit/Binance)"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-700 focus:outline-none focus:border-[#c6ff34]"
              />
            </div>

            {/* Security Guardrails Toggle switches */}
            <div className="bg-zinc-950/60 p-4 rounded-xl border border-zinc-800 space-y-3">
              <p className="text-[9px] uppercase tracking-wider text-zinc-400 font-bold border-b border-zinc-800 pb-1.5">
                SECURITY GUARDRAILS & API PERMISSIONS
              </p>

              {/* Read Only Toggle */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-white block">Enable Read-Only Access</span>
                  <span className="text-[9px] text-zinc-500 block">Allows agent to read account balance and order book depth</span>
                </div>
                <div className="relative inline-flex items-center">
                  <input type="checkbox" defaultChecked disabled className="rounded border-zinc-800 bg-zinc-950 text-[#c6ff34] focus:ring-[#c6ff34]/30" />
                  <span className="text-[9px] text-[#c6ff34] font-black uppercase ml-1.5">LOCKED ON</span>
                </div>
              </div>

              {/* Spot/Margin Trading Toggle */}
              <div className="flex items-center justify-between border-t border-zinc-900 pt-2.5">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-white block">Enable Spot & Margin Trading</span>
                  <span className="text-[9px] text-zinc-500 block">Allows automated execution agent to place and cancel trade vectors</span>
                </div>
                <input type="checkbox" defaultChecked className="rounded border-zinc-800 bg-zinc-950 text-[#c6ff34] focus:ring-[#c6ff34]/30 accent-[#c6ff34]" />
              </div>

              {/* strictly locked-out Disable Withdrawals warning */}
              <div className="flex items-center justify-between border-t border-zinc-900 pt-2.5 text-red-400">
                <div className="space-y-0.5 pr-2">
                  <span className="text-xs font-black text-red-400 block flex items-center gap-1">
                    <Shield className="w-3.5 h-3.5" /> WITHDRAWALS ARE BLOCKED
                  </span>
                  <span className="text-[9px] text-zinc-500 block">Withdrawal permission is strictly locked out. Aegis has zero fund-transfer capabilities.</span>
                </div>
                <div className="text-right">
                  <span className="bg-red-500/10 text-red-400 text-[8px] font-black px-2 py-0.5 rounded border border-red-500/20 whitespace-nowrap">
                    SECURED LOCKOUT
                  </span>
                </div>
              </div>
            </div>

            {/* Simulated Encrypted Masking Visual Box */}
            {apiKey && (
              <div className="bg-[#171717] border border-zinc-800/80 p-3 rounded-xl space-y-1">
                <p className="text-[9px] uppercase font-black text-zinc-500">AES-256 Masked Preview</p>
                <p className="text-xs font-mono text-[#c6ff34] tracking-widest truncate">
                  ••••••••••••••••{apiKey.slice(-4) || "a8df"}
                </p>
              </div>
            )}

            <button
              type="submit"
              className="w-full bg-[#c6ff34] text-[#101416] font-bold text-xs py-3.5 px-4 rounded-xl hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider mt-2 cursor-pointer shadow-lg shadow-[#c6ff34]/10"
            >
              COMMIT SECURE CREDENTIALS
            </button>
          </form>

          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 pt-1">
            <Shield className="w-3.5 h-3.5 text-[#c6ff34] shrink-0" />
            <span>Exchange keys encrypted with AES-256-CBC at database layer. Standby Node verified.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
