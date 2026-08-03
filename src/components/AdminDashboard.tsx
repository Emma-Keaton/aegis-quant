import React, { useState } from "react";
import { Shield, ShieldAlert, Zap, RefreshCw, LogOut, Users, Command } from "lucide-react";
import { setSessionToken, getSessionToken, clearSession, apiJson } from "../api/client";

interface AdminDashboardProps {
  onLogout: () => void;
}

export default function AdminDashboard({ onLogout }: AdminDashboardProps) {
  const [shutdownConfirmed, setShutdownConfirmed] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<{ status?: string; message?: string; timestamp?: string }>({});
  const [agentExecutions, setAgentExecutions] = useState<any[]>([]);

  const handleShutdown = async () => {
    try {
      await apiJson("/admin/shutdown", {
        method: "POST",
        body: JSON.stringify({ confirm: "SHUTDOWN" }),
      });
      alert("Admin shutdown initiated");
    } catch (err) {
      console.error("Shutdown failed:", err);
      alert("Shutdown failed - check backend logs");
    }
  };

  const handleRefresh = async () => {
    try {
      const res = await apiJson("/admin/refresh-market", { method: "POST" });
      setRefreshStatus({ status: res.status, message: res.message, timestamp: res.timestamp });
    } catch (err) {
      console.error("Refresh failed:", err);
      setRefreshStatus({ status: "error", message: "Market refresh failed" });
    }
  };

  const loadExecutions = async () => {
    try {
      const res = await apiJson("/admin/executions");
      setAgentExecutions(res.executions || []);
    } catch (err) {
      console.error("Load executions failed:", err);
    }
  };

  // Load executions on mount
  useEffect(() => {
    loadExecutions();
  }, []);

  return (
    <div className="space-y-6 pb-24 font-sans" id="admin_dashboard">
      {/* Header */}
      <div className="flex justify-between items-center h-16 border-b border-zinc-800 px-1">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-[#c6ff34]" />
          <h2 className="text-xl font-black tracking-wider uppercase text-[#c6ff34]">ADMIN DASHBOARD</h2>
        </div>
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 text-xs font-bold text-red-400 hover:text-[#c6ff34] transition-all"
        >
          <LogOut className="w-4 h-4" /> Logout
        </button>
      </div>

      {/* Warning Banner */}
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-red-400 flex-shrink-0 animate-pulse" />
        <div>
          <p className="font-bold text-sm text-red-400 mb-1">⚠ ADMIN ACCESS GRANTED</p>
          <p className="text-xs text-zinc-400">This screen contains administrative functions. Proceed with caution.</p>
        </div>
      </div>

      {/* Shutdown Control */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-[#c6ff34] uppercase tracking-wider flex items-center gap-2">
          <Zap className="w-4 h-4" /> System Shutdown
        </h3>
        
        {shutdownConfirmed ? (
          <div className="bg-red-500/10 border border-red-500/40 rounded-xl p-4 text-center">
            <p className="text-red-400 font-bold mb-2">CONFIRMED: SHUTDOWN IN PROGRESS</p>
            <p className="text-xs text-zinc-400">The backend will terminate shortly. Do not refresh this page.</p>
          </div>
        ) : (
          <button
            onClick={() => setShutdownConfirmed(true)}
            className="w-full bg-red-500 text-black font-bold py-3 rounded-xl hover:bg-red-400 active:scale-[0.98] transition-all uppercase tracking-wider flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4" /> Initiate Graceful Shutdown
          </button>
        )}
      </div>

      {/* Market Data Refresh */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-[#c6ff34] uppercase tracking-wider flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Market Data Refresh
        </h3>
        <button onClick={handleRefresh} className="w-full bg-[#c6ff34] text-black font-bold py-3 rounded-xl hover:brightness-110 active:scale-[0.98] transition-all uppercase tracking-wider">
          Trigger Market Refresh
        </button>
        
        {refreshStatus.status && (
          <div className={`mt-3 p-3 rounded-lg text-sm ${
            refreshStatus.status === 'success' 
              ? 'bg-green-500/10 border border-green-500/30 text-green-400' 
              : 'bg-red-500/10 border border-red-500/30 text-red-400'
          }`}>
            <p>{refreshStatus.message}</p>
            {refreshStatus.timestamp && (
              <p className="text-xs mt-1 opacity-75">{new Date(refreshStatus.timestamp).toLocaleTimeString()}</p>
            )}
          </div>
        )}
      </div>

      {/* Agent Executions */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-[#c6ff34] uppercase tracking-wider flex items-center gap-2">
          <Users className="w-4 h-4" /> Agent Executions
        </h3>
        <p className="text-xs text-zinc-500">Recent trade executions from trading agents</p>
        
        {agentExecutions.length === 0 ? (
          <div className="border-dashed border-zinc-700 rounded-lg p-6 text-center text-zinc-500 text-sm">
            No agent executions recorded yet
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="px-4 py-2 text-left text-[#c6ff34]">Symbol</th>
                  <th className="px-4 py-2 text-left text-[#c6ff34]" />
                  <th className="px-4 py-2 text-left text-[#c6ff34]" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {agentExecutions.map((exec, idx) => (
                  <tr key={idx} className="hover:bg-zinc-800/20">
                    <td className="px-4 py-3 text-white">{exec.symbol || "-"}</td>
                    <td className="px-4 py-3 text-zinc-400">{exec.size || "-"}</td>
                    <td className="px-4 py-3 text-zinc-400">{exec.timestamp || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Session Info */}
      <div className="border-t border-zinc-800 pt-4">
        <p className="text-xs text-zinc-500 font-mono">
          Admin session active • Chat ID protected • All actions logged
        </p>
      </div>
    </div>
  );
}
