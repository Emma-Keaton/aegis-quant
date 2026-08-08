import React from "react";

interface SkeletonLoaderProps {
  /** Controls whether the skeleton draws its own full-screen app frame. */
  frame?: boolean;
  /** Optional status/caption rendered at the bottom (Inter font by default). */
  label?: string;
  /** Shows the brand logo block in the skeleton header. */
  logo?: boolean;
}

/**
 * Reusable shimmer skeleton that mirrors the mini-app layout
 * (title bar -> hero/balance card -> chart block -> list rows).
 * Used for the boot / loading screen in place of a spinner.
 */
export default function SkeletonLoader({
  frame = true,
  label = "AEGIS QUANT",
  logo = true,
}: SkeletonLoaderProps) {
  const content = (
    <div className="flex flex-col min-h-[inherit]">
      {/* Header / title bar */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-6">
        <div className="flex items-center gap-2.5 h-7">
          {logo && <div className="w-7 h-7 rounded-lg skeleton-shimmer" />}
          <div className="h-5 w-28 skeleton-shimmer" />
        </div>
        <div className="flex items-center gap-2">
          <div className="w-12 h-7 rounded-lg skeleton-shimmer" />
          <div className="w-12 h-7 rounded-lg skeleton-shimmer" />
        </div>
      </div>

      {/* Hero / balance card */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 space-y-4">
        <div className="w-1/3 h-3 skeleton-shimmer" />
        <div className="w-2/3 h-9 rounded-lg skeleton-shimmer" />
        <div className="w-full h-24 rounded-xl skeleton-shimmer" />
      </div>

      {/* Chart block */}
      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
        <div className="h-32 rounded-xl skeleton-shimmer" />
      </div>

      {/* List rows */}
      <div className="mt-6 space-y-3">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 flex items-center justify-between"
          >
            <div className="w-1/4 h-4 rounded-md skeleton-shimmer" />
            <div className="w-1/5 h-4 rounded-md skeleton-shimmer" />
          </div>
        ))}
      </div>

      {label && (
        <div className="mt-auto pt-8 text-center">
          <p className="font-sans text-[10px] font-black uppercase tracking-[0.35em] text-[#c6ff34]">
            {label}
          </p>
        </div>
      )}
    </div>
  );

  if (!frame) {
    return content;
  }

  return (
    <div className="min-h-[100dvh] bg-[#101416] flex justify-center">
      <div className="w-full max-w-[480px] min-h-[100dvh] bg-[#171717] border-x border-zinc-900 px-5 py-6 flex flex-col">
        {content}
      </div>
    </div>
  );
}
