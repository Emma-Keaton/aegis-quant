"""Admin panel for QuantDinger integration.

Provides:
- List of agent tokens (via `/quantdinger-admin/tokens`).
- Button to refresh market data.
- Button to kill the entire backend (admin only).

All requests include the `X‑Telegram‑Init‑Data` header automatically via the
`apiJson` helper which reads `window.Telegram.WebApp.initData` from the page
URL (the same mechanism used for normal auth).
"""

import React, { useEffect, useState } from "react";
import { XCircle, RefreshCw, Zap } from "lucide-react";
import { apiJson } from "../api/client";

interface Token {
  id: number;
  created_at: string;
  status: string;
  token_hash: string;
}

export default function AdminPanel() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadTokens = async () => {
    setLoading(true);
    try {
      const res = await apiJson<any>("/quantdinger-admin/tokens");
      if (res.status === "success") {
        setTokens(res.data || []);
        setError(null);
      } else {
        setError(res.message || "Failed to load tokens");
      }
    } catch (e) {
      setError("Error fetching tokens");
    } finally {
      setLoading(false);
    }
  };

  const refreshMarket = async () => {
    try {
      await apiJson<any>("/quantdinger-admin/refresh-market", { method: "POST" });
      alert("Market data refreshed");
    } catch (e) {
      alert("Failed to refresh market data");
    }
  };

  const killBackend = async () => {
    if (!window.confirm("Are you sure you want to terminate the entire backend? This cannot be undone until the process is restarted.")) {
      return;
    }
    try {
      await apiJson<any>("/quantdinger-admin/kill-backend", { method: "POST" });
      // The process should exit; if not, we inform the user.
      alert("Kill command sent. If the backend does not shut down, check server logs.");
    } catch (e) {
      alert("Failed to send kill command");
    }
  };

  useEffect(() => {
    loadTokens();
  }, []);

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <h2 className="text-xl font-black text-[#c6ff34] mb-4">QuantDinger Admin Panel</h2>
      {error && (
        <div className="bg-red-500/10 text-red-400 p-2 rounded mb-4 flex items-center">
          <XCircle className="w-4 h-4 mr-2" /> {error}
        </div>
      )}
      <div className="space-y-4">
        <button
          onClick={refreshMarket}
          className="flex items-center gap-2 px-4 py-2 bg-[#1c2023] border border-[#c6ff34]/20 hover:bg-[#c6ff34]/10 text-[#c6ff34] rounded"
        >
          <RefreshCw className="w-4 h-4" /> Refresh Market Data
        </button>
        <button
          onClick={killBackend}
          className="flex items-center gap-2 px-4 py-2 bg-red-900 border border-red-600 hover:bg-red-800 text-red-300 rounded"
        >
          <Zap className="w-4 h-4" /> Kill Backend Process
        </button>
      </div>
      <hr className="my-6 border-zinc-800" />
      <h3 className="text-lg font-bold text-white mb-2">Agent Tokens</h3>
      {loading ? (
        <p className="text-zinc-500">Loading tokens…</p>
      ) : (
        <ul className="space-y-2">
          {tokens.length === 0 && <li className="text-zinc-500">No tokens found.</li>}
          {tokens.map(tok => (
            <li key={tok.id} className="bg-zinc-900 p-2 rounded text-sm text-zinc-300 border border-zinc-800">
              <div>ID: {tok.id}</div>
              <div>Status: {tok.status}</div>
              <div>Created: {new Date(tok.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
