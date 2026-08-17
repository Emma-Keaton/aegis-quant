import { useState, useEffect } from "react";
import { X, ChevronRight, ChevronLeft } from "lucide-react";
import { apiFetch } from "../api/client";

interface OnboardingStep {
  title: string;
  body: string;
}

const PAGE_STEPS: Record<string, OnboardingStep[]> = {
  home: [
    { title: "At a Glance", body: "Your portfolio value, PnL chart, and live positions live here. Use the switch card to activate the agent, and the panic button to halt everything instantly." },
    { title: "Mode & Risk", body: "PAPER vs LIVE is set in Settings. The risk gauge shows your max allocation per trade." },
  ],
  wallet: [
    { title: "Connect a Wallet", body: "Link TON (Method 1, opens Tonkeeper), EVM (Method 2), or Solana. Per-user TON trades require on-device approval." },
    { title: "Link Exchange Keys", body: "Add Bybit/OKX/Binance API keys for CEX execution. Keys are AES-256 encrypted and withdrawals stay blocked." },
  ],
  strategy: [
    { title: "Execution Mode", body: "Choose PAPER (demo, uses your paper balance) or LIVE (real funds). Paper balance is set below the capsule." },
    { title: "Risk & Whitelist", body: "Set allocation, stop-loss/take-profit, your risk profile, and which tokens the agent is allowed to trade." },
  ],
  intel: [
    { title: "Signal Convergence", body: "All parsed signals from all sources converge here. The agent acts on the highest-confidence ones." },
    { title: "Source Linking", body: "Link Telegram, Reddit, or RSS sources. Connect your Telegram account to read private channels." },
  ],
  logs: [
    { title: "Transaction Logs", body: "Every buy/sell is recorded with size, price, status, and a link to the block explorer." },
  ],
};

interface OnboardingOverlayProps {
  page: "home" | "wallet" | "strategy" | "intel" | "logs";
  completedPages: string[];
  onPageCompleted: (page: string) => void;
}

export default function OnboardingOverlay({
  page,
  completedPages,
  onPageCompleted,
}: OnboardingOverlayProps) {
  const [visible, setVisible] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  const steps = PAGE_STEPS[page] || [];
  const completed = completedPages.includes(page);

  useEffect(() => {
    if (completed) {
      setVisible(false);
      return;
    }
    if (steps.length > 0) {
      setStepIndex(0);
      setVisible(true);
    }
  }, [page, completed]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!visible || dismissed) return null;

  const finish = async () => {
    setVisible(false);
    try {
      await apiFetch("/api/onboarding/complete", {
        method: "POST",
        body: JSON.stringify({ page }),
      });
    } catch {
      /* non-blocking */
    }
    onPageCompleted(page);
  };

  const step = steps[stepIndex];
  const isLast = stepIndex === steps.length - 1;

  return (
    <div className="fixed z-40 left-1/2 -translate-x-1/2 top-16 w-[calc(100%-2rem)] max-w-[440px] pointer-events-auto">
      <div className="bg-[#1c2023] border border-[#c6ff34]/30 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden">
        {/* header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c6ff34] animate-pulse" /> TOUR
          </p>
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono text-zinc-500">
              {stepIndex + 1}/{steps.length}
            </span>
            <button
              onClick={finish}
              aria-label="close tour"
              className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-all cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* body */}
        <div className="px-4 py-3 space-y-1">
          <p className="text-sm font-black text-white">{step.title}</p>
          <p className="text-xs text-zinc-300 leading-relaxed">{step.body}</p>
        </div>

        {/* footer */}
        <div className="px-4 pb-4 flex items-center justify-between gap-2">
          <button
            onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
            disabled={stepIndex === 0}
            className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-zinc-400 hover:text-white disabled:opacity-30 transition-all cursor-pointer disabled:cursor-default"
          >
            <ChevronLeft className="w-3 h-3" /> Back
          </button>
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <span
                key={i}
                className={`w-1.5 h-1.5 rounded-full ${i === stepIndex ? "bg-[#c6ff34]" : "bg-zinc-700"}`}
              />
            ))}
          </div>
          {isLast ? (
            <button
              onClick={finish}
              className="bg-[#c6ff34] text-[#101416] text-[10px] font-black uppercase tracking-wider px-3 py-2 rounded-lg hover:brightness-110 transition-all cursor-pointer"
            >
              Done
            </button>
          ) : (
            <button
              onClick={() => setStepIndex((i) => Math.min(steps.length - 1, i + 1))}
              className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#c6ff34] hover:text-white transition-all cursor-pointer"
            >
              Next <ChevronRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}