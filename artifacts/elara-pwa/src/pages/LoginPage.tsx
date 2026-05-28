import React, { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";

const PASSCODE = "nexus123";

export default function LoginPage() {
  const { setAuthed } = useApp();
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<"idle" | "checking" | "error">("idle");
  const [shake, setShake] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    api.health().catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (status === "checking") return;
    setStatus("checking");
    await new Promise((r) => setTimeout(r, 220));
    if (input.trim() === PASSCODE) {
      setAuthed(true);
    } else {
      setStatus("error");
      setShake(true);
      setTimeout(() => setShake(false), 400);
      setTimeout(() => setStatus("idle"), 1200);
      setInput("");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full bg-[#0E0418] px-8 select-none">
      <div className="mb-12 text-center">
        <div className="w-16 h-16 rounded-full bg-[rgba(139,63,168,0.12)] border border-[rgba(139,63,168,0.25)] flex items-center justify-center mx-auto mb-6">
          <div className="w-3 h-3 rounded-full bg-[rgba(139,63,168,0.7)]" />
        </div>
        <p className="text-[rgba(200,180,220,0.5)] text-xs tracking-[6px] uppercase">
          e l a r a
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className={`w-full max-w-xs ${shake ? "animate-shake" : ""}`}
      >
        <input
          ref={inputRef}
          type="password"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="passcode"
          autoComplete="off"
          autoCapitalize="none"
          disabled={status === "checking"}
          className={[
            "w-full bg-[rgba(26,11,46,0.9)] text-[#D8C8F0] text-center text-lg",
            "tracking-[0.3em] rounded-2xl px-5 py-4 border outline-none transition-all duration-300",
            "placeholder:text-[rgba(144,128,168,0.3)] placeholder:tracking-[0.15em]",
            status === "error"
              ? "border-[rgba(220,60,100,0.6)] animate-glow"
              : "border-[rgba(139,63,168,0.2)] focus:border-[rgba(139,63,168,0.5)]",
          ].join(" ")}
        />
        <button
          type="submit"
          disabled={!input.trim() || status === "checking"}
          className="w-full mt-4 py-4 rounded-2xl bg-[rgba(139,63,168,0.18)] border border-[rgba(139,63,168,0.25)]
            text-[rgba(200,180,220,0.7)] text-xs tracking-[3px] uppercase
            disabled:opacity-30 transition-opacity active:opacity-60"
        >
          {status === "checking" ? "···" : "enter"}
        </button>
      </form>
    </div>
  );
}
