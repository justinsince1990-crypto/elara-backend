import React, { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";

export function HealthDot() {
  const { healthOk, setHealthOk } = useApp();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        await api.health();
        setHealthOk(true);
      } catch {
        setHealthOk(false);
      }
    };
    check();
    timerRef.current = setInterval(check, 30000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [setHealthOk]);

  return (
    <div className="relative w-2.5 h-2.5 flex items-center justify-center">
      <div
        className="w-2 h-2 rounded-full transition-colors duration-500"
        style={{ backgroundColor: healthOk ? "#22c55e" : "#ef4444" }}
      />
      {healthOk && (
        <div
          className="absolute inset-0 rounded-full"
          style={{
            backgroundColor: "rgba(34,197,94,0.35)",
            animation: "pulse-ring 2.5s ease-out infinite",
          }}
        />
      )}
    </div>
  );
}
