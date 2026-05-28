import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, type MemoryItem } from "@/lib/api";

export function MemoryPanel() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [addText, setAddText] = useState("");
  const [adding, setAdding] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (q?: string) => {
    setLoading(true);
    try {
      const res = await api.getMemory(q);
      setItems(res.items || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleQueryChange = (text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(text || undefined), 400);
  };

  const handleAdd = async () => {
    const fact = addText.trim();
    if (!fact) return;
    setAdding(true);
    try {
      await api.addMemory(fact);
      setAddText("");
      await load(query || undefined);
    } catch {}
    setAdding(false);
  };

  const handleDelete = async (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    try {
      await api.deleteMemory(id);
    } catch {
      load(query || undefined);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between items-center">
        <span className="text-[10px] tracking-[2px] text-[rgba(144,128,168,0.7)] font-semibold uppercase">
          MEMORY
        </span>
        <button
          onClick={() => api.reindexMemory().catch(() => {})}
          className="text-[9px] tracking-[1.5px] text-[rgba(139,63,168,0.7)] font-semibold uppercase"
        >
          REINDEX
        </button>
      </div>

      <input
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder="search..."
        className="bg-[rgba(26,11,46,0.8)] rounded-[10px] px-3 py-2 text-[13px] text-[#D8C8F0]
          border border-[rgba(139,63,168,0.15)] outline-none placeholder:text-[rgba(144,128,168,0.4)]"
      />

      <div className="flex gap-2 items-center">
        <input
          value={addText}
          onChange={(e) => setAddText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="add a fact..."
          className="flex-1 bg-[rgba(26,11,46,0.8)] rounded-[10px] px-3 py-2 text-[13px] text-[#D8C8F0]
            border border-[rgba(139,63,168,0.15)] outline-none placeholder:text-[rgba(144,128,168,0.4)]"
        />
        <button
          onClick={handleAdd}
          disabled={adding || !addText.trim()}
          className="w-9 h-9 rounded-[10px] bg-[rgba(139,63,168,0.5)] flex items-center justify-center
            text-[#E8D8FF] text-lg disabled:opacity-30 active:opacity-60"
        >
          {adding ? "·" : "+"}
        </button>
      </div>

      {loading ? (
        <div className="h-5 flex items-center">
          <div className="w-4 h-4 rounded-full border-2 border-[rgba(139,63,168,0.5)] border-t-transparent animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-[12px] italic text-[rgba(144,128,168,0.5)]">no facts found</p>
      ) : (
        items.slice(0, 12).map((item) => (
          <div
            key={item.id}
            className="flex justify-between items-start py-1.5 border-b border-[rgba(139,63,168,0.06)] gap-2"
          >
            <p className="flex-1 text-[12px] text-[rgba(200,180,220,0.8)] leading-[17px] line-clamp-2">
              {item.text}
            </p>
            <button
              onClick={() => handleDelete(item.id)}
              className="text-[11px] text-[rgba(144,128,168,0.5)] active:opacity-50 shrink-0 mt-0.5"
            >
              ✕
            </button>
          </div>
        ))
      )}
    </div>
  );
}
