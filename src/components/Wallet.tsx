import React, { useState, useEffect } from "react";
import { connectEVM, connectEVMWallet } from "../crypto/evmConnector";
import { connectSolana, connectSolanaWallet, signSolanaTransaction } from "../crypto/solanaConnector";
import { WALLET_APPS, EVM_FAST_LINKS, SOLANA_FAST_LINKS } from "../crypto/walletLinks";
import { Link, Wallet as WalletIcon, Shield, Check, ExternalLink, HelpCircle, Eye, Trash2 } from "lucide-react";
import { useTonConnectUI } from "@tonconnect/ui-react";
import WalletConnectUI from "./WalletConnectUI";
import SetupInfoModal from "./SetupInfoModal";
import { UserState } from "../types";
import { apiFetch } from "../api/client";

interface WalletProps {
  userState: UserState;
  onConnectWallet: (network: string, address: string) => void;
  onLinkExchangeManual: (exchange: string, key: string, secret: string) => void;
  onDisconnectExchange: (exchange: string) => void;
  onNavigateToLogs: () => void;
  networkOffline: boolean;
}

export default function Wallet({ 
  userState, 
  onConnectWallet, 
  onLinkExchangeManual, 
  onDisconnectExchange, 
  onNavigateToLogs, 
  networkOffline
}: WalletProps) {
  const [fallbackNetwork, setFallbackNetwork] = useState<string>("TON");
  const [fallbackAddress, setFallbackAddress] = useState<string>("");
  const [exchange, setExchange] = useState<string>("bybit");
  const [apiKey, setApiKey] = useState<string>("");
  const [apiSecret, setApiKeySecret] = useState<string>("");

  const [simulatedConnecting, setSimulatedConnecting] = useState<boolean>(false);
  const [connectionSuccess, setConnectionSuccess] = useState<boolean>(false);

  // Live on-chain balance for the connected wallet (via /api/wallet/balance).
  const [liveBalance, setLiveBalance] = useState<number | null>(null);
  const [liveUsd, setLiveUsd] = useState<number | null>(null);
  const [liveSymbol, setLiveSymbol] = useState<string>("");
  const [spotMargin, setSpotMargin] = useState<boolean>(true);

  // Load the Spot & Margin permission from the live risk settings.
  useEffect(() => {
    apiFetch("/api/risk")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (j && typeof j.spot_margin_enabled === "boolean") setSpotMargin(j.spot_margin_enabled); })
      .catch(() => {});
  }, []);

  // Fetch the live balance whenever a wallet is connected.
  useEffect(() => {
    if (!userState.walletConnected || !userState.walletAddress) {
      setLiveBalance(null); setLiveUsd(null); setLiveSymbol("");
      return;
    }
    let cancelled = false;
    const n = (userState.network || "").toLowerCase();
    const net = userState.network === "TON"
      ? "ton"
      : n.includes("bsc") || n.includes("bnb") || n.includes("smart chain")
        ? "bsc"
        : n.includes("polygon") ? "polygon"
          : n.includes("sol") ? "solana" : "evm";
    apiFetch(`/api/wallet/balance?network=${net}&address=${encodeURIComponent(userState.walletAddress)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!cancelled && j && j.status === "success") {
          setLiveBalance(j.balance ?? null);
          setLiveUsd(j.usdEstimate ?? null);
          setLiveSymbol(j.symbol || "");
        }
      })
      .catch(() => {});
    // ?? Per-user Solana wallet-signed trade + autonomous key ?????
  const [solTradeAmount, setSolTradeAmount] = useState<string>("");
  const [solTradeToken, setSolTradeToken] = useState<string>("BONK");
  const [solTradeBusy, setSolTradeBusy] = useState<boolean>(false);
  const [solTradeMsg, setSolTradeMsg] = useState<string | null>(null);
  const [solTradeErr, setSolTradeErr] = useState<string | null>(null);
  const [solKey, setSolKey] = useState<string>("");
  const [solShowKey, setSolShowKey] = useState<boolean>(false);
  const [showSetupInfo, setShowSetupInfo] = useState<boolean>(false);
  const [solKeyStatus, setSolKeyStatus] = useState<{ user_key_set: boolean; server_key_set: boolean; active_source: string } | null>(null);

  useEffect(() => {
    apiFetch("/api/wallet/solana/key")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (j) setSolKeyStatus({ user_key_set: !!j.user_key_set, server_key_set: !!j.server_key_set, active_source: j.active_source }); })
      .catch(() => {});
  }, []);

  const handleSaveSolKey = async () => {
    try {
      const res = await apiFetch("/api/wallet/solana/key", {
        method: "POST",
        body: JSON.stringify({ private_key: solKey }),
      });
      const j = await res.json();
      if (res.ok) {
        setSolKey("");
        setSolKeyStatus((p) => ({ ...(p || { server_key_set: false, active_source: "" }), user_key_set: true, active_source: "user" }));
        setSolTradeMsg("Solana private key saved (AES-256 encrypted).");
      } else {
        setSolTradeErr(j.detail || "Failed to save key");
      }
    } catch (e: any) {
      setSolTradeErr(String(e?.message || e));
    }
  };

  const handleDeleteSolKey = async () => {
    try {
      await apiFetch("/api/wallet/solana/key", { method: "DELETE" });
      setSolKeyStatus((p) => (p ? { ...p, user_key_set: false, active_source: p.server_key_set ? "server" : "none" } : p));
      setSolTradeMsg("Solana private key removed.");
    } catch (e: any) {
      setSolTradeErr(String(e?.message || e));
    }
  };

  const handleSolanaTrade = async (token: string, _side: "buy") => {
    if (!userState.walletConnected || !userState.walletAddress) {
      setSolTradeErr("Connect a Solana wallet first");
      return;
    }
    const amount = parseFloat(solTradeAmount);
    if (!amount || amount <= 0) {
      setSolTradeErr("Enter a USD amount greater than 0");
      return;
    }
    setSolTradeBusy(true);
    setSolTradeMsg(null);
    setSolTradeErr(null);
    try {
      const swap = await apiFetch("/api/solana/swap", {
        method: "POST",
        body: JSON.stringify({ token_symbol: token, amount_usd: amount, wallet_address: userState.walletAddress }),
      });
      const swapJson = await swap.json();
      if (!swap.ok || !swapJson.success) {
        setSolTradeErr(swapJson.detail || "Failed to build swap");
        return;
      }
      const signedRaw = await signSolanaTransaction(swapJson.swap_transaction, userState.walletAddress);
      const confirm = await apiFetch("/api/solana/confirm", {
        method: "POST",
        body: JSON.stringify({ signed_transaction: signedRaw, wallet_address: userState.walletAddress, symbol: token, side: "buy", size: amount }),
      });
      const confirmJson = await confirm.json();
      if (!confirm.ok) {
        setSolTradeErr(confirmJson.detail || "Broadcast failed");
        return;
      }
      setSolTradeMsg(`SOLANA ${token} SWAP confirmed ? ${confirmJson.tx_hash}`);
    } catch (e: any) {
      setSolTradeErr(e?.message ? String(e.message) : "Solana trade cancelled or failed");
    } finally {
      setSolTradeBusy(false);
    }
  };

  return () => { cancelled = true; };
  }, [userState.walletConnected, userState.walletAddress, userState.network]);

  const toggleSpotMargin = async (val: boolean) => {
    setSpotMargin(val);
    try {
      await apiFetch("/api/risk", { method: "PATCH", body: JSON.stringify({ spot_margin_enabled: val }) });
    } catch (e) {
      console.error("Failed to update spot/margin permission", e);
    }
  };

  const [tonConnectUI] = useTonConnectUI();

  const currency = userState.currency || "USD";
  const nairaRate = userState.nairaRate;

  const formatVal = (usdAmount: number) => {
    if (currency === "NGN") {
      if (!nairaRate) return "₦—"; // live rate not loaded yet
      const ngnAmount = usdAmount * nairaRate;
      return `₦${ngnAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return `$${usdAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const handleTonConnect = async () => {
    try {
      // Fast-link straight to the TonKeeper app (native deep link via TonConnect).
      await tonConnectUI.connectWallet({ tonkeeper: [] });
      // TonConnectUI handles the UI modal; after success we refresh state
      setConnectionSuccess(true);
    } catch (e) {
      console.error('TON connect failed', e);
    }
  };

  const handleConnectEVM = async () => {
    setSimulatedConnecting(true);
    try {
      const result = await connectEVM();
      await onConnectWallet(result.network, result.address);
      setConnectionSuccess(true);
    } catch (e) {
      console.error('EVM connection failed', e);
    } finally {
      setSimulatedConnecting(false);
      setTimeout(() => setConnectionSuccess(false), 3000);
    }
  };

  const handleConnectSolana = async () => {
    setSimulatedConnecting(true);
    try {
      const result = await connectSolana();
      await onConnectWallet(result.network, result.address);
      setConnectionSuccess(true);
    } catch (e) {
      console.error('Solana connection failed', e);
    } finally {
      setSimulatedConnecting(false);
      setTimeout(() => setConnectionSuccess(false), 3000);
    }
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

  // Fast-link: connect through a *specific* wallet app (deep-link into its
  // native/in-browser app), falling back to the wallet's install/own app page
  // when the connector or injected provider isn't available.
  const handleFastConnect = async (walletId: string) => {
    if (networkOffline) return;
    setSimulatedConnecting(true);
    try {
      const app = WALLET_APPS[walletId];
      const result =
        app?.chain === "solana"
          ? await connectSolanaWallet(walletId)
          : await connectEVMWallet(walletId);
      await onConnectWallet(result.network, result.address);
      setConnectionSuccess(true);
    } catch (e) {
      // Specific wallet not available -> the connector already opened the app.
      console.error(`Failed to fast-connect ${walletId}:`, e);
    } finally {
      setSimulatedConnecting(false);
      setTimeout(() => setConnectionSuccess(false), 3000);
    }
  };

  // ── Per-user TON trading (per-trade approval via Ton Connect) ─────────────
  const [tonTradeAmount, setTonTradeAmount] = useState<string>("");
  const [tonTradeBusy, setTonTradeBusy] = useState<boolean>(false);
  const [tonTradeMsg, setTonTradeMsg] = useState<string | null>(null);
  const [tonTradeErr, setTonTradeErr] = useState<string | null>(null);

  const handleTonTrade = async (symbol: string, side: "buy" | "sell") => {
    if (!userState.walletConnected || !userState.walletAddress) {
      setTonTradeErr("Connect a TON wallet first");
      return;
    }
    const amount = parseFloat(tonTradeAmount);
    if (!amount || amount <= 0) {
      setTonTradeErr("Enter a TON amount greater than 0");
      return;
    }
    setTonTradeBusy(true);
    setTonTradeMsg(null);
    setTonTradeErr(null);
    try {
      // 1) Ask the backend for an unsigned TonConnect transfer request.
      const build = await apiFetch("/api/wallet/ton/build", {
        method: "POST",
        body: JSON.stringify({
          address: userState.walletAddress,
          amount,
          comment: `${side.toUpperCase()} ${symbol} (Aegis Quant)`,
        }),
      });
      const buildJson = await build.json();
      if (!build.ok || !buildJson.ok) {
        setTonTradeErr(buildJson.detail || buildJson.message || "Failed to build TON transfer");
        return;
      }

      // 2) Approve in the user's own wallet app (Tonkeeper/Tonhub/...).
      const signed = await tonConnectUI.sendTransaction({
        validUntil: buildJson.validUntil,
        messages: buildJson.messages,
      });

      // 3) Broadcast the signed boc and persist the trade.
      const broadcast = await apiFetch("/api/wallet/ton/broadcast", {
        method: "POST",
        body: JSON.stringify({
          boc: typeof signed === "string" ? signed : (signed as any)?.boc,
          symbol,
          side,
          size: amount,
          price: 0,
        }),
      });
      const broadcastJson = await broadcast.json();
      if (!broadcast.ok) {
        setTonTradeErr(broadcastJson.detail || "Broadcast failed");
        return;
      }
      setTonTradeMsg(`TON ${side.toUpperCase()} approved & broadcast — ${broadcastJson.tx_hash}`);
      setTonTradeAmount("");
    } catch (e: any) {
      setTonTradeErr(e?.message ? String(e.message) : "TON trade cancelled or failed");
    } finally {
      setTonTradeBusy(false);
    }
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
                {liveBalance !== null
                  ? `${liveBalance.toLocaleString(undefined, { maximumFractionDigits: 4 })} ${liveSymbol}`
                  : "—"}
              </p>
              <p className="text-[10px] text-zinc-400">
                {liveUsd !== null
                  ? `~${formatVal(liveUsd)}`
                  : "Live balance unavailable"}
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

      {/* Web3 wallet Connection triggers */}
      <WalletConnectUI />

      {/* Web3 wallet Connection triggers */}
      {/* Connected Networks Overview */}
      {userState.walletConnected && (
        <div className="mt-4 p-3 bg-[#0f1113] border border-[#c6ff34]/20 rounded-lg text-xs text-[#c6ff34]">
          Connected to {userState.network} network at address {userState.walletAddress.slice(0, 6)}...{userState.walletAddress.slice(-6)}
        </div>
      )}
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Method 1: Telegram & TON Ecosystem</p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-zinc-400">Native, instant integration with TON wallet on Telegram ecosystem.</p>
            <button
              disabled={simulatedConnecting}
              onClick={handleTonConnect}
              className="w-full bg-[#c6ff34] text-[#101416] font-bold text-xs py-3.5 px-4 rounded-xl hover:brightness-110 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              {simulatedConnecting ? "Authorizing..." : connectionSuccess ? "TON Wallet Connected!" : "CONNECT TON KEEPER / WALLET"}
            </button>

            {/* Per-user TON trade (approve in your own wallet) — only when TON is connected */}
            {userState.walletConnected && (userState.network || "").toLowerCase().includes("ton") && (
              <div className="pt-3 border-t border-zinc-800 space-y-2">
                <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">
                  TRADE TON (APPROVE IN YOUR WALLET)
                </p>
                <div className="flex gap-2">
                  <input
                    value={tonTradeAmount}
                    onChange={(e) => setTonTradeAmount(e.target.value)}
                    placeholder="TON amount"
                    inputMode="decimal"
                    className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
                  />
                  <button
                    disabled={tonTradeBusy}
                    onClick={() => handleTonTrade("TON", "buy")}
                    className="bg-[#c6ff34]/10 text-[#c6ff34] border border-[#c6ff34]/20 font-black text-[10px] px-3 rounded-xl hover:bg-[#c6ff34]/20 transition-all uppercase cursor-pointer disabled:opacity-40"
                  >
                    {tonTradeBusy ? "..." : "SEND"}
                  </button>
                </div>
                {tonTradeMsg && (
                  <p className="text-[11px] text-[#c6ff34] bg-[#c6ff34]/10 border border-[#c6ff34]/20 rounded-lg px-3 py-2 break-all">{tonTradeMsg}</p>
                )}
                {tonTradeErr && (
                  <p className="text-[11px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{tonTradeErr}</p>
                )}
                <p className="text-[9px] text-zinc-500">
                  Your Tonkeeper/Tonhub app will pop up for approval. Funds stay in your wallet — you approve each send.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Method 2: EVM Multi-Chain</p>
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-zinc-400">Connect Trust Wallet, MetaMask, or Safepal using multi-chain standard.</p>
            <button
              disabled={simulatedConnecting}
              onClick={handleConnectEVM}
              className="w-full border border-zinc-700 text-white font-bold text-xs py-3.5 px-4 rounded-xl hover:bg-zinc-900 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              {simulatedConnecting ? "Connecting..." : "CONNECT VIA WALLETCONNECT"}
            </button>

            {/* Specific EVM wallet fast links (incl. CeFi Web3 wallets) */}
            <div className="flex flex-wrap gap-1.5">
              {EVM_FAST_LINKS.map((wid) => {
                const app = WALLET_APPS[wid];
                return (
                  <button
                    key={wid}
                    type="button"
                    disabled={simulatedConnecting || networkOffline}
                    onClick={() => handleFastConnect(wid)}
                    className="px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 hover:border-[#c6ff34]/40 rounded-lg text-[9px] font-black uppercase tracking-wider text-zinc-300 hover:text-[#c6ff34] transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                  >
                    {app.name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Solana Wallet Connection */}
      <div className="space-y-1">
        <p className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold px-1">Method 3: Solana (Phantom, Solflare, Torus)</p>
        <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
          <p className="text-xs text-zinc-400">Connect a Solana wallet using the Solana Wallet Adapter (Phantom, Solflare, Torus, etc.).</p>
          <button
            disabled={simulatedConnecting}
            onClick={handleConnectSolana}
            className="w-full border border-zinc-700 text-white font-bold text-xs py-3.5 px-4 rounded-xl hover:bg-zinc-900 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
          >
            CONNECT SOLANA WALLET
          </button>

          {/* Specific Solana wallet fast links */}
          <div className="flex flex-wrap gap-1.5">
            {SOLANA_FAST_LINKS.map((wid) => {
              const app = WALLET_APPS[wid];
              return (
                <button
                  key={wid}
                  type="button"
                  disabled={simulatedConnecting || networkOffline}
                  onClick={() => handleFastConnect(wid)}
                  className="px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 hover:border-[#c6ff34]/40 rounded-lg text-[9px] font-black uppercase tracking-wider text-zinc-300 hover:text-[#c6ff34] transition-all active:scale-95 cursor-pointer disabled:opacity-40"
                >
                  {app.name}
                </button>
              );
            })}
          </div>

          {/* Wallet-signed Solana trade (no private key needed) */}
          {userState.walletConnected && (userState.network || "").toLowerCase().includes("sol") && (
            <div className="pt-3 border-t border-zinc-800 space-y-2">
              <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">TRADE SOLANA (WALLET-SIGNED)</p>
              <div className="flex gap-2">
                <input
                  value={solTradeAmount}
                  onChange={(e) => setSolTradeAmount(e.target.value)}
                  placeholder="USD amount"
                  inputMode="decimal"
                  className="flex-1 w-1/2 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
                />
                <select
                  value={solTradeToken}
                  onChange={(e) => setSolTradeToken(e.target.value)}
                  className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 focus:outline-none focus:border-[#c6ff34]"
                >
                  <option value="BONK">BONK</option>
                  <option value="WIF">WIF</option>
                  <option value="POPCAT">POPCAT</option>
                </select>
                <button
                  disabled={solTradeBusy}
                  onClick={() => handleSolanaTrade(solTradeToken, "buy")}
                  className="bg-[#c6ff34]/10 text-[#c6ff34] border border-[#c6ff34]/20 font-black text-[10px] px-3 rounded-xl hover:bg-[#c6ff34]/20 transition-all uppercase cursor-pointer disabled:opacity-40"
                >
                  {solTradeBusy ? "..." : "SWAP"}
                </button>
              </div>
              {solTradeMsg && <p className="text-[11px] text-[#c6ff34] bg-[#c6ff34]/10 border border-[#c6ff34]/20 rounded-lg px-3 py-2 break-all">{solTradeMsg}</p>}
              {solTradeErr && <p className="text-[11px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{solTradeErr}</p>}
              <p className="text-[9px] text-zinc-500">Your wallet signs the transaction — your key never leaves the wallet.</p>
            </div>
          )}

          {/* Per-user Solana private key (for autonomous trading only) */}
          <div className="pt-3 border-t border-zinc-800 space-y-2">
            <p className="text-[9px] uppercase tracking-widest text-zinc-500 font-bold">SOLANA PRIVATE KEY (AUTONOMOUS TRADING)</p>
            <p className="text-[9px] text-zinc-500 leading-relaxed">
              For server-side autonomous trades the agent places while you're away. Wallet-connected trades always use your on-device signature instead — no key stored. This key is AES-256 encrypted and used only for auto-execution.
            </p>
            <div className="flex gap-2">
              <input
                value={solKey}
                onChange={(e) => setSolKey(e.target.value)}
                placeholder={solKeyStatus?.user_key_set ? "•••••••• (replace)" : "base58 or hex private key"}
                type={solShowKey ? "text" : "password"}
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-2.5 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
              />
              <button
                disabled={!solKey || networkOffline}
                onClick={() => handleSaveSolKey()}
                className="bg-[#c6ff34] text-[#101416] font-black text-[10px] px-3 rounded-xl hover:brightness-110 transition-all uppercase cursor-pointer disabled:opacity-40"
              >
                SAVE
              </button>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded border ${solKeyStatus?.user_key_set ? "bg-[#c6ff34]/10 text-[#c6ff34] border-[#c6ff34]/20" : "bg-zinc-900 text-zinc-500 border-zinc-800"}`}>
                {solKeyStatus?.user_key_set ? "USER KEY SET" : "NO USER KEY"}
              </span>
              <button onClick={() => setSolShowKey(v => !v)} className="text-[9px] text-zinc-400 hover:text-[#c6ff34] underline cursor-pointer">
                {solShowKey ? "Hide" : "Reveal"}
              </button>
              {solKeyStatus?.user_key_set && (
                <button onClick={() => handleDeleteSolKey()} className="text-[9px] text-red-400 hover:text-red-300 underline cursor-pointer">
                  REMOVE
                </button>
              )}
              <button onClick={() => setShowSetupInfo(true)} className="text-[9px] text-[#c6ff34] hover:text-white underline cursor-pointer">
                HOW TO GET YOUR KEY
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* "How to get your keys" setup info modal */}
      {showSetupInfo && <SetupInfoModal onClose={() => setShowSetupInfo(false)} />}

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
                onClick={() => handleFastConnect("bybit")}
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
                onClick={() => handleFastConnect("okx")}
                className="text-[10px] font-black uppercase text-[#101416] bg-[#c6ff34] px-3 py-1.5 rounded-lg hover:brightness-110 active:scale-95 transition-all shadow-md shadow-[#c6ff34]/15 cursor-pointer"
              >
                FAST LINK
              </button>
            )}
          </div>

          {/* Binance Card */}
          <div className={`p-4 rounded-2xl border bg-zinc-900/30 flex items-center justify-between transition-all ${
            userState.connectedCeFi.binance.connected ? "border-[#c6ff34]/40 bg-zinc-950/40" : "border-zinc-800"
          }`}>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${userState.connectedCeFi.binance.connected ? "bg-[#c6ff34]" : "bg-zinc-600"}`}></span>
                <span className="text-sm font-black text-white">Binance (Nigerian Supported Broker)</span>
              </div>
              <p className="text-[10px] text-zinc-400 font-mono flex items-center gap-2">
                {userState.connectedCeFi.binance.connected 
                  ? "Vault ID: AEC-BIN-••••7f1e" 
                  : "Status: Standby Vault"}
                {userState.connectedCeFi.binance.connected && (
                  <span className="bg-emerald-500/10 text-emerald-400 text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border border-emerald-500/10">READ & TRADE</span>
                )}
              </p>
            </div>
            {userState.connectedCeFi.binance.connected ? (
              <button
                onClick={() => onDisconnectExchange("binance")}
                className="p-2.5 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 active:scale-95 transition-all cursor-pointer"
                title="Disconnect Exchange"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={() => handleFastConnect("binance")}
                className="text-[10px] font-black uppercase text-[#101416] bg-[#c6ff34] px-3 py-1.5 rounded-lg hover:brightness-110 active:scale-95 transition-all shadow-md shadow-[#c6ff34]/15 cursor-pointer"
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
                <input type="checkbox" checked={spotMargin} onChange={(e) => toggleSpotMargin(e.target.checked)} className="rounded border-zinc-800 bg-zinc-950 text-[#c6ff34] focus:ring-[#c6ff34]/30 accent-[#c6ff34]" />
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
