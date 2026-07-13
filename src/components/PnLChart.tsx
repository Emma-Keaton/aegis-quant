import React, { useEffect, useRef, useState } from "react";
import { createChart, IChartApi, ISeriesApi, UTCTimestamp, AreaSeries, LineSeries } from "lightweight-charts";
import { Maximize2, Minimize2, X, Info } from "lucide-react";
import { UserState } from "../types";

interface PnLChartProps {
  userState: UserState;
  backtestResult?: {
    backtestCurve: any[];
    benchmarkCurve: any[];
    metrics: any;
    active: boolean;
  } | null;
}

interface DataPoint {
  time: UTCTimestamp;
  value: number;
}

// Generate static baseline datasets relative to a 10,000 baseline
const baseMockData: Record<string, DataPoint[]> = {
  "1D": [
    { time: (Math.floor(Date.now() / 1000) - 86400) as UTCTimestamp, value: 12100 },
    { time: (Math.floor(Date.now() / 1000) - 64800) as UTCTimestamp, value: 12250 },
    { time: (Math.floor(Date.now() / 1000) - 43200) as UTCTimestamp, value: 11950 },
    { time: (Math.floor(Date.now() / 1000) - 21600) as UTCTimestamp, value: 12400 },
    { time: Math.floor(Date.now() / 1000) as UTCTimestamp, value: 12450 }
  ],
  "7D": [
    { time: (Math.floor(Date.now() / 1000) - 7 * 86400) as UTCTimestamp, value: 11500 },
    { time: (Math.floor(Date.now() / 1000) - 6 * 86400) as UTCTimestamp, value: 11800 },
    { time: (Math.floor(Date.now() / 1000) - 5 * 86400) as UTCTimestamp, value: 12050 },
    { time: (Math.floor(Date.now() / 1000) - 4 * 86400) as UTCTimestamp, value: 11900 },
    { time: (Math.floor(Date.now() / 1000) - 3 * 86400) as UTCTimestamp, value: 12200 },
    { time: (Math.floor(Date.now() / 1000) - 2 * 86400) as UTCTimestamp, value: 12150 },
    { time: (Math.floor(Date.now() / 1000) - 1 * 86400) as UTCTimestamp, value: 12380 },
    { time: Math.floor(Date.now() / 1000) as UTCTimestamp, value: 12450 }
  ],
  "30D": [
    { time: (Math.floor(Date.now() / 1000) - 30 * 86400) as UTCTimestamp, value: 10200 },
    { time: (Math.floor(Date.now() / 1000) - 25 * 86400) as UTCTimestamp, value: 10800 },
    { time: (Math.floor(Date.now() / 1000) - 20 * 86400) as UTCTimestamp, value: 11200 },
    { time: (Math.floor(Date.now() / 1000) - 15 * 86400) as UTCTimestamp, value: 11500 },
    { time: (Math.floor(Date.now() / 1000) - 10 * 86400) as UTCTimestamp, value: 12100 },
    { time: (Math.floor(Date.now() / 1000) - 5 * 86400) as UTCTimestamp, value: 12050 },
    { time: Math.floor(Date.now() / 1000) as UTCTimestamp, value: 12450 }
  ],
  "ALL": [
    { time: (Math.floor(Date.now() / 1000) - 90 * 86400) as UTCTimestamp, value: 8500 },
    { time: (Math.floor(Date.now() / 1000) - 75 * 86400) as UTCTimestamp, value: 9200 },
    { time: (Math.floor(Date.now() / 1000) - 60 * 86400) as UTCTimestamp, value: 9900 },
    { time: (Math.floor(Date.now() / 1000) - 45 * 86400) as UTCTimestamp, value: 10800 },
    { time: (Math.floor(Date.now() / 1000) - 30 * 86400) as UTCTimestamp, value: 11500 },
    { time: (Math.floor(Date.now() / 1000) - 15 * 86400) as UTCTimestamp, value: 12000 },
    { time: Math.floor(Date.now() / 1000) as UTCTimestamp, value: 12450 }
  ]
};

export const PnLChart: React.FC<PnLChartProps> = ({ userState, backtestResult }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const fullscreenContainerRef = useRef<HTMLDivElement>(null);

  const inlineChartRef = useRef<IChartApi | null>(null);
  const inlineSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const inlineBacktestSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const inlineBenchmarkSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const fullscreenChartRef = useRef<IChartApi | null>(null);
  const fullscreenSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const fullscreenBacktestSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const fullscreenBenchmarkSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const [timeframe, setTimeframe] = useState<string>("7D");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const currency = userState.currency || "USD";
  const nairaRate = userState.nairaRate || 1520;

  // Render Inline Chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 220,
      layout: {
        background: { color: "#171717" },
        textColor: "#a1a1aa",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.03)" },
        horzLines: { color: "rgba(255, 255, 255, 0.03)" },
      },
      rightPriceScale: {
        borderVisible: true,
        borderColor: "rgba(255, 255, 255, 0.15)",
        visible: true,
        scaleMargins: {
          top: 0.15,
          bottom: 0.15,
        },
      },
      timeScale: {
        borderVisible: true,
        borderColor: "rgba(255, 255, 255, 0.15)",
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number) => {
          const date = new Date(time * 1000);
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: true,
      }
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: "rgba(198, 255, 52, 0.22)",
      bottomColor: "rgba(198, 255, 52, 0.01)",
      lineColor: "rgba(198, 255, 52, 1)",
      lineWidth: 2,
    });

    inlineChartRef.current = chart;
    inlineSeriesRef.current = areaSeries;

    const handleResize = () => {
      if (chartContainerRef.current && inlineChartRef.current) {
        inlineChartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      inlineChartRef.current = null;
      inlineSeriesRef.current = null;
    };
  }, []);

  // Render Fullscreen Chart
  useEffect(() => {
    if (!isFullscreen || !fullscreenContainerRef.current) return;

    const chart = createChart(fullscreenContainerRef.current, {
      width: fullscreenContainerRef.current.clientWidth,
      height: Math.min(window.innerHeight - 180, 500),
      layout: {
        background: { color: "#171717" },
        textColor: "#e4e4e7", // Brighter label colors for full screen readability
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.05)" },
        horzLines: { color: "rgba(255, 255, 255, 0.05)" },
      },
      rightPriceScale: {
        borderVisible: true,
        borderColor: "rgba(255, 255, 255, 0.2)",
        visible: true,
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderVisible: true,
        borderColor: "rgba(255, 255, 255, 0.2)",
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number) => {
          const date = new Date(time * 1000);
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit" });
        }
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        vertTouchDrag: true,
        horzTouchDrag: true,
      }
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: "rgba(198, 255, 52, 0.25)",
      bottomColor: "rgba(198, 255, 52, 0.00)",
      lineColor: "rgba(198, 255, 52, 1)",
      lineWidth: 2,
    });

    fullscreenChartRef.current = chart;
    fullscreenSeriesRef.current = areaSeries;

    const handleResize = () => {
      if (fullscreenContainerRef.current && fullscreenChartRef.current) {
        fullscreenChartRef.current.applyOptions({
          width: fullscreenContainerRef.current.clientWidth,
          height: Math.min(window.innerHeight - 180, 500),
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      fullscreenChartRef.current = null;
      fullscreenSeriesRef.current = null;
    };
  }, [isFullscreen]);

  // Sync data and currency-switched values across both chart instances
  useEffect(() => {
    const scale = currency === "NGN" ? nairaRate : 1;
    const rawData = baseMockData[timeframe] || baseMockData["7D"];

    // Format Data
    const mappedData = rawData.map((d) => ({
      time: d.time,
      value: Math.round(d.value * scale * 100) / 100,
    }));

    // Setup formatters
    const priceFormatter = (val: number) => {
      if (currency === "NGN") {
        return `₦${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
      }
      return `$${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    };

    // Update Inline Chart Series
    if (inlineSeriesRef.current && inlineChartRef.current) {
      inlineSeriesRef.current.setData(mappedData);
      inlineSeriesRef.current.applyOptions({
        priceFormat: {
          type: "price",
          precision: 2,
          minMove: 0.01,
          formatter: priceFormatter,
        }
      });
      inlineChartRef.current.timeScale().fitContent();
    }

    // Update Fullscreen Chart Series
    if (fullscreenSeriesRef.current && fullscreenChartRef.current) {
      fullscreenSeriesRef.current.setData(mappedData);
      fullscreenSeriesRef.current.applyOptions({
        priceFormat: {
          type: "price",
          precision: 2,
          minMove: 0.01,
          formatter: priceFormatter,
        }
      });
      fullscreenChartRef.current.timeScale().fitContent();
    }

    // Render Backtest Overlay on Inline Chart
    if (inlineChartRef.current) {
      if (backtestResult && backtestResult.active && backtestResult.backtestCurve?.length > 0) {
        // Create backtest series if not exists
        if (!inlineBacktestSeriesRef.current) {
          inlineBacktestSeriesRef.current = inlineChartRef.current.addSeries(LineSeries, {
            color: "#14b8a6", // Neon Teal
            lineWidth: 2.5,
            lineStyle: 2, // Dashed
          });
        }
        // Set data
        const bData = backtestResult.backtestCurve.map((d: any) => ({
          time: d.time as UTCTimestamp,
          value: Math.round(d.value * scale * 100) / 100,
        }));
        inlineBacktestSeriesRef.current.setData(bData);

        // Create benchmark series if not exists
        if (!inlineBenchmarkSeriesRef.current && backtestResult.benchmarkCurve?.length > 0) {
          inlineBenchmarkSeriesRef.current = inlineChartRef.current.addSeries(LineSeries, {
            color: "#f59e0b", // Amber / Orange
            lineWidth: 1.5,
            lineStyle: 3, // Dotted
          });
        }
        if (inlineBenchmarkSeriesRef.current && backtestResult.benchmarkCurve?.length > 0) {
          const mData = backtestResult.benchmarkCurve.map((d: any) => ({
            time: d.time as UTCTimestamp,
            value: Math.round(d.value * scale * 100) / 100,
          }));
          inlineBenchmarkSeriesRef.current.setData(mData);
        }
        inlineChartRef.current.timeScale().fitContent();
      } else {
        // Remove them if not active
        if (inlineBacktestSeriesRef.current) {
          inlineChartRef.current.removeSeries(inlineBacktestSeriesRef.current);
          inlineBacktestSeriesRef.current = null;
        }
        if (inlineBenchmarkSeriesRef.current) {
          inlineChartRef.current.removeSeries(inlineBenchmarkSeriesRef.current);
          inlineBenchmarkSeriesRef.current = null;
        }
      }
    }

    // Render Backtest Overlay on Fullscreen Chart
    if (fullscreenChartRef.current) {
      if (backtestResult && backtestResult.active && backtestResult.backtestCurve?.length > 0) {
        if (!fullscreenBacktestSeriesRef.current) {
          fullscreenBacktestSeriesRef.current = fullscreenChartRef.current.addSeries(LineSeries, {
            color: "#14b8a6",
            lineWidth: 2.5,
            lineStyle: 2,
          });
        }
        const bData = backtestResult.backtestCurve.map((d: any) => ({
          time: d.time as UTCTimestamp,
          value: Math.round(d.value * scale * 100) / 100,
        }));
        fullscreenBacktestSeriesRef.current.setData(bData);

        if (!fullscreenBenchmarkSeriesRef.current && backtestResult.benchmarkCurve?.length > 0) {
          fullscreenBenchmarkSeriesRef.current = fullscreenChartRef.current.addSeries(LineSeries, {
            color: "#f59e0b",
            lineWidth: 1.5,
            lineStyle: 3,
          });
        }
        if (fullscreenBenchmarkSeriesRef.current && backtestResult.benchmarkCurve?.length > 0) {
          const mData = backtestResult.benchmarkCurve.map((d: any) => ({
            time: d.time as UTCTimestamp,
            value: Math.round(d.value * scale * 100) / 100,
          }));
          fullscreenBenchmarkSeriesRef.current.setData(mData);
        }
        fullscreenChartRef.current.timeScale().fitContent();
      } else {
        if (fullscreenBacktestSeriesRef.current) {
          fullscreenChartRef.current.removeSeries(fullscreenBacktestSeriesRef.current);
          fullscreenBacktestSeriesRef.current = null;
        }
        if (fullscreenBenchmarkSeriesRef.current) {
          fullscreenChartRef.current.removeSeries(fullscreenBenchmarkSeriesRef.current);
          fullscreenBenchmarkSeriesRef.current = null;
        }
      }
    }
  }, [timeframe, currency, nairaRate, isFullscreen, backtestResult]);

  return (
    <>
      {/* Inline Portfolio Chart Panel */}
      <div className="bg-zinc-950/40 border border-zinc-800 rounded-2xl p-4 space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-[10px] font-black text-[#c6ff34] uppercase tracking-widest block">PORTFOLIO TIME-SERIES</span>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Timeframe Selectors */}
            <div className="flex bg-zinc-900/60 p-1 rounded-xl border border-zinc-800">
              {["1D", "7D", "30D", "ALL"].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 text-[10px] font-black rounded-lg transition-all ${
                    timeframe === tf
                      ? "bg-[#c6ff34] text-black shadow-lg shadow-[#c6ff34]/20"
                      : "text-zinc-500 hover:text-white"
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>

            {/* Maximize to full-screen mode */}
            <button
              onClick={() => setIsFullscreen(true)}
              className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Fullscreen Chart"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="relative w-full rounded-xl overflow-hidden bg-[#171717] p-2 border border-zinc-900">
          <div ref={chartContainerRef} className="w-full" style={{ minHeight: "220px" }} />
        </div>
      </div>

      {/* Fullscreen Overlay Modal (Responsive Mobile Mode) */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-[#171717] flex flex-col p-5 md:p-8 animate-fade-in overflow-hidden justify-between">
          
          {/* Header Controls */}
          <div className="flex justify-between items-start gap-4 mb-4">
            <div>
              <span className="text-[11px] font-black text-[#c6ff34] uppercase tracking-widest block">AEGIS QUANT</span>
              <h2 className="text-xl font-black text-white tracking-tight uppercase">PORTFOLIO DYNAMIC ANALYSIS</h2>
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5 uppercase">
                Interactive Multi-touch enabled • Live Currency ({currency})
              </p>
            </div>

            <button
              onClick={() => setIsFullscreen(false)}
              className="bg-[#c6ff34] text-black font-black text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 hover:bg-[#b0f020] active:scale-95 transition-all cursor-pointer shadow-lg shadow-[#c6ff34]/20"
            >
              <Minimize2 className="w-4 h-4" />
              <span className="hidden sm:inline">EXIT FULLSCREEN</span>
            </button>
          </div>

          {/* Interactive Chart Area */}
          <div className="flex-1 flex flex-col justify-center bg-zinc-950/40 border border-zinc-800 rounded-3xl p-4 md:p-6 my-2">
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-1.5 text-zinc-400 font-bold text-xs">
                <Info className="w-4 h-4 text-[#c6ff34]" />
                <span className="text-[11px]">Pinch to Zoom • Drag with Touch to Scroll/Pan</span>
              </div>

              {/* Modal Timeframe Selectors */}
              <div className="flex bg-zinc-900 p-1 rounded-xl border border-zinc-800">
                {["1D", "7D", "30D", "ALL"].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`px-4 py-1.5 text-xs font-black rounded-lg transition-all ${
                      timeframe === tf
                        ? "bg-[#c6ff34] text-black shadow-md shadow-[#c6ff34]/15"
                        : "text-zinc-500 hover:text-white"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 min-h-[300px] relative w-full rounded-2xl overflow-hidden bg-[#171717] p-2 border border-zinc-900 flex items-center justify-center">
              <div ref={fullscreenContainerRef} className="w-full h-full" />
            </div>
          </div>

          {/* Bottom stats/metadata info bar */}
          <div className="mt-4 flex flex-col sm:flex-row justify-between items-center border-t border-zinc-900 pt-4 gap-3 text-center sm:text-left">
            <div>
              <p className="text-[10px] text-zinc-500 uppercase font-black">ACTIVE INTEGRATIONS</p>
              <p className="text-xs text-white font-bold mt-0.5">TON Keeper Wallet • API Connection Verified</p>
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase font-black">EXCHANGE RATE</p>
              <p className="text-xs text-zinc-400 font-bold mt-0.5">
                1 USD = <span className="text-[#c6ff34]">₦{nairaRate.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </p>
            </div>
          </div>

        </div>
      )}
    </>
  );
};
