import React, { useState, useEffect } from 'react';
import apiFetch from '../api/client';

interface Channel {
  channelId: string;
  confidenceThreshold: number;
}

export default function CopyTradeManager() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newChannelId, setNewChannelId] = useState('');
  const [newThreshold, setNewThreshold] = useState(80);

  const fetchChannels = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/copytrade/channels');
      const json = await res.json();
      if (json.status === 'success') setChannels(json.data);
      else throw new Error(json.error || 'Failed');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChannels();
  }, []);

  const handleAdd = async () => {
    if (!newChannelId) return;
    try {
      const res = await apiFetch('/api/copytrade/register', {
        method: 'POST',
        body: JSON.stringify({ channelId: newChannelId, confidenceThreshold: newThreshold, parserLlm: 'groq' }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.error || 'Add failed');
      setNewChannelId('');
      setNewThreshold(80);
      await fetchChannels();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleUpdate = async (channelId: string, threshold: number) => {
    try {
      const res = await apiFetch('/api/copytrade/update', {
        method: 'PATCH',
        body: JSON.stringify({ channelId, confidenceThreshold: threshold }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.error || 'Update failed');
      await fetchChannels();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleDelete = async (channelId: string) => {
    try {
      const res = await apiFetch('/api/copytrade/unregister', {
        method: 'DELETE',
        body: JSON.stringify({ channelId }),
      });
      const json = await res.json();
      if (json.status !== 'success') throw new Error(json.error || 'Delete failed');
      await fetchChannels();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="mt-6 space-y-4" id="copytrade_manager">
      <h3 className="text-sm font-bold text-[#c6ff34] uppercase">Copy‑Trade Channels</h3>
      {loading && <p className="text-xs text-zinc-400">Loading…</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
      <ul className="space-y-2">
        {channels.map((c) => (
          <li key={c.channelId} className="flex items-center gap-2 text-xs text-zinc-200">
            <span className="flex-1">{c.channelId}</span>
            <input
              type="number"
              min={0}
              max={100}
              value={c.confidenceThreshold}
              onChange={(e) => {
                const val = Number(e.target.value);
                setChannels((prev) =>
                  prev.map((ch) => (ch.channelId === c.channelId ? { ...ch, confidenceThreshold: val } : ch))
                );
              }}
              className="w-16 bg-zinc-800 text-zinc-100 border border-zinc-600 rounded"
            />
            <button
              onClick={() => handleUpdate(c.channelId, c.confidenceThreshold)}
              className="px-2 py-0.5 bg-[#c6ff34]/20 text-[#c6ff34] rounded hover:bg-[#c6ff34]/30 text-xs"
            >
              Save
            </button>
            <button
              onClick={() => handleDelete(c.channelId)}
              className="px-2 py-0.5 bg-red-600/30 text-red-300 rounded hover:bg-red-600/50 text-xs"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-2 text-xs">
        <input
          placeholder="Channel ID"
          value={newChannelId}
          onChange={(e) => setNewChannelId(e.target.value)}
          className="flex-1 bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1"
        />
        <input
          type="number"
          min={0}
          max={100}
          value={newThreshold}
          onChange={(e) => setNewThreshold(Number(e.target.value))}
          className="w-20 bg-zinc-800 text-zinc-100 border border-zinc-600 rounded px-2 py-1"
        />
        <button
          onClick={handleAdd}
          className="px-3 py-1 bg-[#c6ff34]/20 text-[#c6ff34] rounded hover:bg-[#c6ff34]/30"
        >
          Add
        </button>
      </div>
    </div>
  );
}
