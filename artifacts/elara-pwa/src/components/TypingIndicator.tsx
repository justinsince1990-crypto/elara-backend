import React from "react";

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-2 px-4 py-2 msg-bubble">
      <div className="mt-2 shrink-0">
        <div className="w-1.5 h-1.5 rounded-full bg-[rgba(139,63,168,0.7)]" />
      </div>
      <div className="bg-[#2A1245] rounded-[20px] rounded-tl-[4px] px-4 py-3 border border-[rgba(139,63,168,0.15)]">
        <div className="flex gap-1 items-center h-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-[rgba(200,180,220,0.5)]"
              style={{ animation: `typing-dot 1.2s ${i * 0.2}s ease-in-out infinite` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
