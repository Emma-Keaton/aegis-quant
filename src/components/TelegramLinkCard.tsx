import { useState, useEffect } from "react";
import { Link2, Phone, KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { apiFetch } from "../api/client";

/**
 * Telegram account link (phone + OTP) for reading *private* channels in the
 * copy-trade pipeline. Public channels are fetched via RSS automatically.
 */
export default function TelegramLinkCard() {
  const [status, setStatus] = useState<{ linked: boolean; status: string; phone?: string }>({ linked: false, status: "loading" });
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [step, setStep] = useState<"idle" | "code">("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const load = async () => {
    try {
      const j = await (await apiFetch("/api/telegram/link/status")).json();
      setStatus({ linked: !!j.linked, status: j.status, phone: j.phone });
    } catch {
      setStatus({ linked: false, status: "unknown" });
    }
  };
  useEffect(() => { load(); }, []);

  const sendCode = async () => {
    setBusy(true); setError(null); setOk(null);
    try {
      const j = await (await apiFetch("/api/telegram/link/connect", {
        method: "POST", body: JSON.stringify({ phone }),
      })).json();
      if (j.status === "success" || j.ok) { setStep("code"); setOk("Verification code sent to your Telegram."); }
      else setError(j.error || "Failed to send code");
    } catch (e: any) { setError(String(e?.message || e)); } finally { setBusy(false); }
  };

  const verify = async () => {
    setBusy(true); setError(null); setOk(null);
    try {
      const j = await (await apiFetch("/api/telegram/link/otp", {
        method: "POST", body: JSON.stringify({ code, password }),
      })).json();
      if (j.status === "success" || j.ok) { setOk("Telegram account linked ✓"); setStep("idle"); setCode(""); setPassword(""); await load(); }
      else setError(j.error === "2fa_required" ? "2FA enabled — enter your password below." : (j.error || "Verification failed"));
    } catch (e: any) { setError(String(e?.message || e)); } finally { setBusy(false); }
  };

  const logout = async () => {
    await apiFetch("/api/telegram/link/logout", { method: "POST" });
    await load();
  };

  const linked = !!status.linked;

  if (status.status === "loading") {
    return (
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-3">
        <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
          <Phone className="w-4 h-4 text-[#c6ff34]" /> TELEGRAM ACCOUNT
        </p>
        <div className="h-10 bg-zinc-900/60 rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-5 space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
          <Phone className="w-4 h-4 text-[#c6ff34]" /> TELEGRAM ACCOUNT
        </p>
        <span
          className={`text-[8px] font-black uppercase px-2 py-1 rounded-md border ${
            linked
              ? "bg-[#c6ff34]/10 text-[#c6ff34] border-[#c6ff34]/20"
              : "bg-zinc-900 text-zinc-500 border-zinc-800"
          }`}
        >
          {linked ? "LINKED" : "NOT LINKED"}
        </span>
      </div>

      <p className="text-[11px] text-zinc-400 leading-relaxed">
        Private channels are read through your own Telegram session (phone + one-time code).
        Public channels are fetched via RSS automatically &mdash; this makes private channels readable too.
      </p>

      {linked ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2.5">
            <ShieldCheck className="w-4 h-4 text-[#c6ff34] shrink-0" />
            <p className="text-xs font-mono text-zinc-300 truncate">{status.phone || "Connected"}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="w-full border border-zinc-700 text-white text-xs py-3 rounded-xl hover:bg-zinc-900 transition-all font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" /> DISCONNECT
          </button>
        </div>
      ) : step === "idle" ? (
        <div className="space-y-3">
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+2348... (phone with country code)"
            inputMode="tel"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
          />
          <button
            type="button"
            onClick={sendCode}
            disabled={!phone || busy}
            className="w-full bg-[#c6ff34] text-[#101416] font-black text-xs py-3.5 px-4 rounded-xl hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <KeyRound className="w-3.5 h-3.5" /> {busy ? "SENDING..." : "CONNECT (SEND CODE)"}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Verification code"
            inputMode="numeric"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="2FA password (if enabled)"
            type="password"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 placeholder-zinc-600 focus:outline-none focus:border-[#c6ff34]"
          />
          <button
            type="button"
            onClick={verify}
            disabled={!code || busy}
            className="w-full bg-[#c6ff34] text-[#101416] font-black text-xs py-3.5 px-4 rounded-xl hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            <KeyRound className="w-3.5 h-3.5" /> {busy ? "VERIFYING..." : "VERIFY CODE"}
          </button>
        </div>
      )}

      {error && <p className="text-[11px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>}
      {ok && <p className="text-[11px] text-[#c6ff34] bg-[#c6ff34]/10 border border-[#c6ff34]/20 rounded-lg px-3 py-2">{ok}</p>}

      <div className="flex items-center gap-1.5 text-zinc-500">
        <Link2 className="w-3 h-3" />
        <p className="text-[9px]">Session is encrypted with AES-256 on our server. Public channels never need this.</p>
      </div>
    </div>
  );
}