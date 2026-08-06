import { useState } from 'react';
import { getStrategies } from '../strategies';
import type { StrategyConfig } from '../strategies';

const STORAGE_KEY = 'aegis_active_strategies';

function readActive(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch {
    /* ignore */
  }
  return new Set(getStrategies().filter((s) => s.default_active).map((s) => s.name));
}

export default function StrategyPlaybook() {
  const [strategies] = useState<StrategyConfig[]>(() => getStrategies());
  const [active, setActive] = useState<Set<string>>(() => readActive());
  const [selected, setSelected] = useState<StrategyConfig | null>(null);

  const toggle = (name: string) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  return (
    <div className="space-y-3">
      <p className="text-[10px] uppercase tracking-widest text-[#c6ff34] font-black flex items-center gap-1.5 px-1">
        <span>📚</span> STRATEGY PLAYBOOK
      </p>
      <div className="bg-[#1c2023] border border-zinc-800 rounded-2xl p-4 space-y-2">
        {strategies.length === 0 && (
          <p className="text-[11px] text-zinc-500">No strategies loaded.</p>
        )}
        {strategies.map((s) => (
          <div
            key={s.name}
            className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2.5"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[12px] font-black text-zinc-100 truncate">{s.display_name}</span>
                <span className="text-[9px] font-mono uppercase text-zinc-500">{s.category}</span>
                {s.default_router && (
                  <span className="text-[9px] font-mono uppercase text-[#c6ff34]/80 border border-[#c6ff34]/30 rounded px-1">router</span>
                )}
              </div>
              <p className="text-[10px] text-zinc-500 truncate mt-0.5">{s.description}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setSelected(s)}
                className="text-[10px] text-zinc-400 hover:text-[#c6ff34] border border-zinc-800 px-2 py-1 rounded font-mono uppercase"
              >
                view
              </button>
              <button
                type="button"
                onClick={() => toggle(s.name)}
                className={`w-9 h-5 rounded-full relative transition-colors ${active.has(s.name) ? 'bg-[#c6ff34]' : 'bg-zinc-700'}`}
                aria-label={`toggle ${s.display_name}`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-zinc-950 transition-all ${active.has(s.name) ? 'left-[18px]' : 'left-0.5'}`}
                />
              </button>
            </div>
          </div>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 p-4" onClick={() => setSelected(null)}>
          <div
            className="bg-[#1c2023] border border-zinc-700 rounded-2xl max-w-lg w-full max-h-[70vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
              <div>
                <h3 className="text-sm font-black text-[#c6ff34] uppercase">{selected.display_name}</h3>
                <p className="text-[10px] font-mono text-zinc-500">{selected.name} · priority {selected.default_priority}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="text-zinc-400 hover:text-white text-lg leading-none"
                aria-label="close"
              >
                ×
              </button>
            </div>
            <div className="px-5 py-4 overflow-y-auto">
              <pre className="text-[11px] leading-relaxed whitespace-pre-wrap text-zinc-300 font-sans">{selected.instructions}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
