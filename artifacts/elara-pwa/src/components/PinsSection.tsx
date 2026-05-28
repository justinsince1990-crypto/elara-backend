import React, { useCallback, useEffect, useState } from "react";
import { api, type Pin } from "@/lib/api";

export function PinsSection() {
  const [pins, setPins] = useState<Pin[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getPins();
      setPins(res.pins || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const dismiss = useCallback(
    async (id: string) => {
      setPins((prev) => prev.filter((p) => p.id !== id));
      try {
        await api.deletePin(id);
      } catch {
        load();
      }
    },
    [load],
  );

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[10px] tracking-[2px] text-[rgba(144,128,168,0.7)] font-semibold uppercase">
        FROM ELARA
      </span>
      {loading ? (
        <div className="w-4 h-4 rounded-full border-2 border-[rgba(139,63,168,0.5)] border-t-transparent animate-spin" />
      ) : pins.length === 0 ? (
        <p className="text-[12px] italic text-[rgba(144,128,168,0.5)]">nothing pinned yet</p>
      ) : (
        pins.slice(0, 6).map((pin) => (
          <div
            key={pin.id}
            className="bg-[rgba(42,18,69,0.7)] rounded-xl p-3 border border-[rgba(139,63,168,0.12)] flex flex-col gap-2"
          >
            <p className="text-[13px] text-[#D8C8F0] leading-[19px] italic">{pin.text}</p>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-[rgba(144,128,168,0.6)]">
                {pin.ts?.slice(0, 10) || ""}
              </span>
              <button
                onClick={() => dismiss(pin.id)}
                className="text-[13px] text-[rgba(144,128,168,0.6)] active:opacity-50"
              >
                ✕
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
