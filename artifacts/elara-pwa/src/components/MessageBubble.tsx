import React from "react";
import { type Message } from "@/lib/api";

function formatTs(ts?: string): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const ts = formatTs(message.ts);

  if (isUser) {
    return (
      <div className="flex flex-col items-end px-4 py-1 gap-0.5 msg-bubble">
        <div className="bg-[#1F0D30] rounded-[20px] rounded-br-[4px] px-4 py-2.5 max-w-[82%] border border-[rgba(139,63,168,0.2)]">
          <p className="text-[#D8C8F0] text-[15px] leading-[22px] whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>
        {ts && <span className="text-[10px] text-[rgba(144,128,168,0.7)] pr-1">{ts}</span>}
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 px-4 py-1 msg-bubble">
      <div className="mt-1.5 shrink-0">
        <div className="w-1.5 h-1.5 rounded-full bg-[rgba(139,63,168,0.7)]" />
      </div>
      <div className="flex flex-col gap-0.5 max-w-[90%]">
        <div className="bg-[#2A1245] rounded-[20px] rounded-tl-[4px] px-4 py-3 border border-[rgba(139,63,168,0.15)]">
          <p className="text-[#E8D8FF] text-[15px] leading-[23px] whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>
        {ts && <span className="text-[10px] text-[rgba(144,128,168,0.7)] pl-0.5">{ts}</span>}
      </div>
    </div>
  );
}
