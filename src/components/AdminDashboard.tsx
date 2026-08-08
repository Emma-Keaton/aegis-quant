import React, { useState, useEffect } from "react";
import { Shield, ShieldAlert, Zap, RefreshCw, LogOut, Activity, TrendingUp, TrendingDown, AlertCircle, Clock } from "lucide-react";
import { apiJson, getApiBase } from "../api/client";

interface AdminDashboardProps {
  onLogout: () => void;
}

interface MetricsData {
  timestamp: string;
  trades_today: number;
  pnl_usd: number;
  open_positions: number;
  win_rate_pct: number;
  errors_total: number;
  uptime_hours: number;
}

interface AppConfig {
  grafanaUrl: string | null;
  prometheusUrl: string | null;
  frontendUrl: string | null;
}

export default function AdminDashboard({ onLogout }: AdminDashboardProps) {
  const [shutdownConfirmed, setShutdownConfirmed] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<{ status?: string; message?: string }>({});
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"monitoring" | "system">("monitoring");
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    fetch(`${getApiBase()}/api/config`, { cache: 'no-store' })
      .then(r => r.ok ? r.json() : null)
      .then(data => setAppConfig(data))
      .catch(() => {});

    loadMetrics();
    const interval = setInterval(loadMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadMetrics = async () => {
    try {
      const res = await apiJson("/admin/metrics");
      setMetrics(res);
    } catch (err) {
      console.error("Failed to load metrics:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleShutdown = async () => {
    try {
      await apiJson("/admin/shutdown", {
        method: "POST",
        body: JSON.stringify({ confirm: "SHUTDOWN" }),
      });
      alert("Admin shutdown initiated");
    } catch (err) {
      alert("Shutdown failed");
    }
  };

  const handleRefresh = async () => {
    try {
      const res = await apiJson("/admin/refresh-market", { method: "POST" });
      setRefreshStatus({ status: res.status, message: res.message });
      loadMetrics();
    } catch (err) {
      setRefreshStatus({ status: "error", message: "Market refresh failed" });
    }
  };

  if (loading) {
    return (
      <div className="space-y-4 p-4">
        <div className="h-6 w-1/3 skeleton-shimmer" />
        <div className="grid grid-cols-2 gap-4">
          <div className="h-24 rounded-2xl skeleton-shimmer" />
          <div className="h-24 rounded-2xl skeleton-shimmer" />
          <div className="h-24 rounded-2xl skeleton-shimmer" />
          <div className="h-24 rounded-2xl skeleton-shimmer" />
        </div>
      </div>
    );
  }

  const grafanaUrl = appConfig?.grafanaUrl || "";
  const prometheusUrl = appConfig?.prometheusUrl || `${appConfig?.frontendUrl || window.location.origin}/metrics`;

  return (
    <div className="space-y-6 pb-6 font-sans p-4">
      {/* Header */}
      <div className="flex justify-between items-center h-16 border-b border-zinc-800 px-1">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-[#c6ff34]" />
          <h2 className="text-xl font-black tracking-wider uppercase text-[#c6ff34]">ADMIN DASHBOARD</h2>
        </div>
        <button onClick={onLogout} className="flex items-center gap-1.5 text-xs font-bold text-red-400 hover:text-[#c6ff34]">
          <LogOut className="w-4 h-4" /> Logout
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-zinc-800">
        <button
          onClick={() => setActiveTab("monitoring")}
          className={`px-4 py-2 font-bold text-sm uppercase tracking-wider ${
            activeTab === "monitoring" ? "text-[#c6ff34] border-b-2 border-[#c6ff34]" : "text-zinc-400 hover:text-white"
          }`}
        >
          <Activity className="w-4 h-4 inline mr-2" />Monitoring
        </button>
        <button
          onClick={() => setActiveTab("system")}
          className={`px-4 py-2 font-bold text-sm uppercase tracking-wider ${
            activeTab === "system" ? "text-[#c6ff34] border-b-2 border-[#c6ff34]" : "text-zinc-400 hover:text-white"
          }`}
        >
          <Zap className="w-4 h-4 inline mr-2" />System
        </button>
      </div>

      {/* Monitoring Tab */}
      {activeTab === "monitoring" && (
        <div className="space-y-6">
          {/* Metrics Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-5 h-5 text-[#c6ff34]" />
                <span className="text-xs font-bold text-zinc-400 uppercase">Trades Today</span>
              </div>
              <p className="text-3xl font-black font-mono text-white">{metrics?.trades_today || 0}</p>
            </div>
            
            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                {metrics?.pnl_usd >= 0 ? <TrendingUp className="w-5 h-5 text-green-400" /> : <TrendingDown className="w-5 h-5 text-red-400" />}
                <span className="text-xs font-bold text-zinc-400 uppercase">PnL Today</span>
              </div>
              <p className={`text-3xl font-black font-mono ${metrics?.pnl_usd >= 0 ? "text-green-400" : "text-red-400"}`}>
                ${metrics?.pnl_usd?.toFixed(2) || 0}
              </p>
            </div>

            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-5 h-5 text-blue-400" />
                <span className="text-xs font-bold text-zinc-400 uppercase">Open Positions</span>
              </div>
              <p className="text-3xl font-black font-mono text-white">{metrics?.open_positions || 0}</p>
            </div>

            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle className="w-5 h-5 text-yellow-400" />
                <span className="text-xs font-bold text-zinc-400 uppercase">Errors (24h)</span>
              </div>
              <p className="text-3xl font-black font-mono text-white">{metrics?.errors_total || 0}</p>
            </div>

            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-5 h-5 text-[#c6ff34]" />
                <span className="text-xs font-bold text-zinc-400 uppercase">Win Rate</span>
              </div>
              <p className="text-3xl font-black font-mono text-[#c6ff34]">{metrics?.win_rate_pct || 0}%</p>
            </div>

            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-5 h-5 text-purple-400" />
                <span className="text-xs font-bold text-zinc-400 uppercase">Uptime</span>
              </div>
              <p className="text-3xl font-black font-mono text-white">{metrics?.uptime_hours ? `${(metrics.uptime_hours / 24).toFixed(1)}d` : "N/A"}</p>
            </div>
          </div>

          {/* Grafana Link */}
          {grafanaUrl && (
            <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
              <h3 className="text-sm font-bold text-[#c6ff34] uppercase tracking-wider mb-4">📊 Grafana Cloud</h3>
              <p className="text-xs text-zinc-400 mb-4">
                View full dashboards, alerts, and historical metrics in Grafana Cloud.
              </p>
              <a
                href={grafanaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#c6ff34] text-black font-bold rounded-xl hover:bg-[#b0f020] transition-all text-sm"
              >
                <Activity className="w-4 h-4" /> Open Grafana Dashboards
              </a>
            </div>
          )}

          {/* Prometheus Endpoint */}
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6">
            <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-wider mb-2">📈 Prometheus Endpoint</h3>
            <p className="text-xs text-zinc-500 mb-3">Raw metrics for scraping:</p>
            <code className="block bg-black/50 p-3 rounded-lg text-xs text-[#c6ff34] font-mono break-all">
              {prometheusUrl}
            </code>
          </div>
        </div>
      )}

      {/* System Tab */}
      {activeTab === "system" && (
        <div className="space-y-6">
          {/* Warning Banner */}
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-red-400 flex-shrink-0 animate-pulse" />
            <div>
              <p className="font-bold text-sm text-red-400 mb-1">⚠ ADMIN ACCESS GRANTED</p>
              <p className="text-xs text-zinc-400">Proceed with caution.</p>
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
                <p className="text-xs text-zinc-400">The backend will terminate shortly.</p>
              </div>
            ) : (
              <button
                onClick={() => setShutdownConfirmed(true)}
                className="w-full bg-red-500 text-black font-bold py-3 rounded-xl hover:bg-red-400 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
              >
                <Zap className="w-4 h-4" /> Initiate Graceful Shutdown
              </button>
            )}
          </div>

          {/* Market Refresh */}
          <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-[#c6ff34] uppercase tracking-wider flex items-center gap-2">
              <RefreshCw className="w-4 h-4" /> Market Data Refresh
            </h3>
            <button
              onClick={handleRefresh}
              className="w-full bg-[#1c2023] border border-[#c6ff34]/30 text-[#c6ff34] font-bold py-3 rounded-xl hover:bg-[#c6ff34]/10 transition-all uppercase tracking-wider flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-4 h-4" /> Refresh Market Data
            </button>
            {refreshStatus.message && (
              <p className="text-xs text-zinc-400 text-center">{refreshStatus.message}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
