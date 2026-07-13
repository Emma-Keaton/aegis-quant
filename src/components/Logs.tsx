import React, { useState, useEffect } from "react";
import { History, Search, ArrowUpRight, ArrowDownRight, RefreshCw, ExternalLink, Calendar, Filter } from "lucide-react";
import { TransactionLog } from "../types";

export default function Logs() {
  const [logs, setLogs] = useState<TransactionLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [timeframeFilter, setTimeframeFilter] = useState<string>("ALL");

  const fetchLogs = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const url = typeFilter === "ALL" ? "/api/logs" : `/api/logs?type=${typeFilter}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error("Failed to load execution logs");
      }
      const json = await res.json();
      if (json.status === "success" && json.data) {
        setLogs(json.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [typeFilter]);

  const handleSimulateInboundLog = async () => {
    try {
      // Post a new simulated filled buy position to verify state is fully linked
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "BUY",
          pair: "SOL/USDT",
          volume: `$${(Math.random() * 300 + 100).toFixed(2)}`,
          status: "Filled"
        })
      });
      if (res.ok) {
        fetchLogs(false);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6 pb-24 font-sans" id="logs_screen">
      {/* Header */}
      <div className="flex justify-between items-center h-14 border-b border-zinc-800 px-1">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-[#c6ff34]" />
          <h2 className="text-lg font-black tracking-wider uppercase text-[#c6ff34]">TRANSACTION LOGS</h2>
        </div>
        <button
          onClick={handleSimulateInboundLog}
          className="bg-zinc-900 border border-zinc-800 hover:border-[#c6ff34]/40 text-white font-bold text-xs px-3 py-1.5 rounded-xl transition-all font-mono"
        >
          + TEST TRADE EVENT
        </button>
      </div>

      {/* Filter Section Dropdowns */}
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black px-1 flex items-center gap-1">
          <Filter className="w-3.5 h-3.5" />
          FILTER LOG CONTROLS
        </p>

        <div className="grid grid-cols-2 gap-2">
          {/* Type Dropdown */}
          <div className="space-y-1">
            <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block px-1">TX TYPE</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 font-semibold focus:outline-none focus:border-[#c6ff34]"
            >
              <option value="ALL">All Actions</option>
              <option value="BUY">BUY</option>
              <option value="SWAP">SWAP</option>
              <option value="DEPOSIT">DEPOSIT</option>
              <option value="CEFI_LINK">CEFI LINK</option>
            </select>
          </div>

          {/* Timeframe Dropdown */}
          <div className="space-y-1">
            <label className="text-[9px] uppercase tracking-wider text-zinc-500 font-bold block px-1">DATE RANGE</label>
            <select
              value={timeframeFilter}
              onChange={(e) => setTimeframeFilter(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-white p-3 font-semibold focus:outline-none focus:border-[#c6ff34]"
            >
              <option value="ALL">All-Time</option>
              <option value="TODAY">Today Only</option>
              <option value="7D">Past 7 Days</option>
              <option value="30D">Past 30 Days</option>
            </select>
          </div>
        </div>
      </div>

      {/* Execution Logs List */}
      <div className="space-y-2">
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-[#1c2023]/50 rounded-xl border border-zinc-800 animate-pulse"></div>
            ))}
          </div>
        ) : logs.length === 0 ? (
          <div className="bg-zinc-900/20 border border-dashed border-zinc-800 p-8 rounded-2xl text-center space-y-1">
            <p className="text-sm font-bold text-zinc-500">No Logs Matching Selection</p>
            <p className="text-xs text-zinc-600">Simulate a trade event or link exchange keys to generate activity entries.</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {logs.map((log) => {
              const isFilled = log.status === "Filled";
              const isFailed = log.status === "Failed";
              const isPending = log.status === "Pending";

              return (
                <div
                  key={log.id}
                  className="bg-[#1c2023] border border-zinc-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-zinc-700 transition-all"
                >
                  <div className="flex items-center gap-3">
                    {/* Arrow Icons reflecting Transaction Directions */}
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs ${
                      log.type === "BUY" ? "bg-[#c6ff34]/10 text-[#c6ff34]" : 
                      log.type === "DEPOSIT" ? "bg-blue-500/10 text-blue-400" :
                      log.type === "PANIC_SELL" ? "bg-red-500/10 text-red-400" :
                      "bg-zinc-950 text-zinc-400 border border-zinc-800"
                    }`}>
                      {log.type === "BUY" ? <ArrowUpRight className="w-4 h-4" /> : 
                       log.type === "PANIC_SELL" ? <ArrowDownRight className="w-4 h-4" /> :
                       <History className="w-4 h-4" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-black text-white uppercase tracking-wider">{log.type}</span>
                        <span className="text-zinc-500 text-[10px] font-bold">• {log.pair}</span>
                      </div>
                      <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
                        {new Date(log.timestamp).toLocaleDateString()} {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>

                  {/* Status & Volume display */}
                  <div className="flex items-center justify-between sm:justify-end gap-6 sm:text-right border-t border-zinc-800/40 sm:border-none pt-2 sm:pt-0">
                    <div className="sm:hidden text-[9px] uppercase text-zinc-500 font-black">Details</div>
                    <div className="flex items-center sm:flex-col gap-4 sm:gap-1.5">
                      <p className="text-xs font-mono text-zinc-300 font-extrabold">{log.volume}</p>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          isFilled ? "bg-[#c6ff34]" : isFailed ? "bg-red-500" : "bg-zinc-500"
                        }`}></span>
                        <span className={`text-[10px] font-black uppercase tracking-wider ${
                          isFilled ? "text-[#c6ff34]" : isFailed ? "text-red-400" : "text-zinc-500"
                        }`}>
                          {log.status}
                        </span>
                      </div>
                    </div>

                    <a
                      href={`https://tonviewer.com/${log.hash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-400 hover:text-[#c6ff34] p-1 bg-zinc-950 rounded border border-zinc-800 hover:border-zinc-700 transition-all"
                      title="View on block explorer"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
