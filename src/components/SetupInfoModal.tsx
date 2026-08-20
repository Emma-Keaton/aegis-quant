import { useState } from "react";
import { X, CircleHelp } from "lucide-react";

interface Method {
  method: string;
  title: string;
  steps: string[];
}

interface SetupInfoModalProps {
  onClose: () => void;
}

export default function SetupInfoModal({ onClose }: SetupInfoModalProps) {
  const [methods, setMethods] = useState<Method[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selected, setSelected] = useState<string>("Solana (keypair)");

  // Lazy-load the how-to instructions from the backend /api/wallet/setup-info.
  if (!loaded) {
    setLoaded(true);
    fetch(
      `${import.meta.env.VITE_API_URL?.replace(/\/$/, "") || ""}/api/wallet/setup-info`,
      { cache: "no-store" },
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (j?.methods) {
          setMethods(j.methods);
          setSelected(j.methods[0]?.method || "Solana (keypair)");
        }
      })
      .catch(() => {});
  }

  const current = methods.find((m) => m.method === selected);

  return (
    <div className="fixed z-50 left-1/2 -translate-x-1/2 top-10 w-[calc(100%-2rem)] max-w-[460px] bg-[#1c2023] border border-[#c6ff34]/30 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5">
          <CircleHelp className="w-4 h-4" /> HOW TO GET YOUR KEYS
        </p>
        <button onClick={onClose} aria-label="close" className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-all cursor-pointer">
          <X className="w-4 h-4" />
        </button>
      </div>

      {methods.length === 0 ? (
        <p className="text-xs text-zinc-500 text-center py-6 px-4">Loading instructions...</p>
      ) : (
        <div className="px-4 py-3 space-y-3 max-h-[60vh] overflow-y-auto">
          {/* Method selector */}
          <div className="flex flex-wrap gap-1.5">
            {methods.map((m) => (
              <button
                key={m.method}
                onClick={() => setSelected(m.method)}
                className={`px-2.5 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider transition-all cursor-pointer border ${
                  selected === m.method
                    ? "bg-[#c6ff34] text-black border-[#c6ff34]/40"
                    : "bg-zinc-950 text-zinc-300 border-zinc-800"
                }`}
              >
                {m.method}
              </button>
            ))}
          </div>

          {current && (
            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3 space-y-2">
              <p className="text-sm font-black text-white">{current.title}</p>
              {current.steps.map((s, i) => (
                <p key={i} className="text-[11px] text-zinc-300 leading-relaxed flex items-start gap-1.5">
                  <span className="text-[#c6ff34] font-mono text-[10px] shrink-0">{i + 1}.</span>
                  {normalizeStep(s)}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="px-4 pb-4">
        <button onClick={onClose} className="w-full border border-zinc-700 text-white text-xs py-3 rounded-xl hover:bg-zinc-900 transition-all font-bold uppercase tracking-wider">
          Close
        </button>
      </div>
    </div>
  );
}

/** Render a step string, preserving bold markers like **read-only**. */
function normalizeStep(s: string) {
  // Very light Markdown handling: convert **bold** to styled spans.
  const parts = s.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <span key={i} className="font-bold text-[#c6ff34]">{part}</span>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}