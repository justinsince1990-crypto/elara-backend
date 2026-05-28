import React, { useEffect, useRef, useState } from "react";
import { useApp } from "@/contexts/AppContext";
import { MemoryPanel } from "./MemoryPanel";
import { PinsSection } from "./PinsSection";
import { TimelineModal } from "./TimelineModal";

interface DrawerPanelProps {
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

const MOOD_LABELS: Record<string, string> = {
  tender: "feeling tender right now",
  heavy: "in a heavy mood",
  playful: "feeling playful right now",
  sharp: "feeling sharp right now",
  neutral: "",
};

export function DrawerPanel({ onSelectConversation, onNewConversation }: DrawerPanelProps) {
  const {
    drawerOpen,
    setDrawerOpen,
    conversationId,
    conversations,
    refreshConversations,
    voiceEnabled,
    setVoiceEnabled,
    mood,
  } = useApp();

  const [timelineVisible, setTimelineVisible] = useState(false);
  const [visible, setVisible] = useState(false);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    if (drawerOpen) {
      setVisible(true);
      setAnimating(false);
      refreshConversations();
    } else if (visible) {
      setAnimating(true);
      const t = setTimeout(() => {
        setVisible(false);
        setAnimating(false);
      }, 250);
      return () => clearTimeout(t);
    }
  }, [drawerOpen]);

  if (!visible) return null;

  return (
    <>
      <div className="fixed inset-0 z-10 bg-black/50" onClick={() => setDrawerOpen(false)} />
      <div
        className={`fixed top-0 right-0 bottom-0 z-20 w-[85vw] max-w-sm
          bg-[#0A0218] border-l border-[rgba(139,63,168,0.15)] flex flex-col
          ${animating ? "drawer-exit" : "drawer-enter"}`}
      >
        <div className="flex-1 overflow-y-auto px-5 pt-12 pb-8 flex flex-col gap-4">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[14px] tracking-[6px] text-[rgba(200,180,220,0.6)]">
              e l a r a
            </span>
            <button
              onClick={() => setDrawerOpen(false)}
              className="text-[18px] text-[rgba(144,128,168,0.7)] active:opacity-50"
            >
              ✕
            </button>
          </div>

          {MOOD_LABELS[mood] && (
            <p className="text-[11px] italic text-[rgba(144,128,168,0.55)] -mt-2 animate-mood">
              {MOOD_LABELS[mood]}
            </p>
          )}

          <div className="flex justify-between items-center py-1">
            <span className="text-[10px] tracking-[2px] text-[rgba(144,128,168,0.7)] font-semibold uppercase">
              VOICE
            </span>
            <button
              onClick={() => setVoiceEnabled(!voiceEnabled)}
              className={`w-11 h-6 rounded-full flex items-center transition-colors duration-200 px-0.5 ${
                voiceEnabled ? "bg-[rgba(139,63,168,0.7)]" : "bg-[rgba(144,128,168,0.2)]"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full transition-all duration-200 ${
                  voiceEnabled
                    ? "translate-x-5 bg-[#D9D9E0]"
                    : "translate-x-0 bg-[rgba(200,180,220,0.5)]"
                }`}
              />
            </button>
          </div>

          <div className="h-px bg-[rgba(139,63,168,0.1)]" />

          <PinsSection />

          <div className="h-px bg-[rgba(139,63,168,0.1)]" />

          <button
            onClick={() => setTimelineVisible(true)}
            className="flex items-center gap-2 py-2 active:opacity-60"
          >
            <span className="text-[13px] text-[rgba(139,63,168,0.8)]">◷</span>
            <span className="text-[11px] tracking-[2px] text-[rgba(200,180,220,0.8)] font-semibold uppercase">
              OUR STORY
            </span>
          </button>

          <div className="h-px bg-[rgba(139,63,168,0.1)]" />

          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center">
              <span className="text-[10px] tracking-[2px] text-[rgba(144,128,168,0.7)] font-semibold uppercase">
                CONVERSATIONS
              </span>
              <button
                onClick={() => {
                  onNewConversation();
                  setDrawerOpen(false);
                }}
                className="text-[16px] text-[rgba(139,63,168,0.8)] active:opacity-50"
              >
                +
              </button>
            </div>
            {conversations.length === 0 ? (
              <p className="text-[12px] italic text-[rgba(144,128,168,0.5)]">no conversations</p>
            ) : (
              conversations.slice(0, 12).map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => {
                    onSelectConversation(conv.id);
                    setDrawerOpen(false);
                  }}
                  className={`py-2 text-left border-b border-[rgba(139,63,168,0.06)] active:opacity-60
                    ${conv.id === conversationId ? "border-l-2 border-l-[rgba(139,63,168,0.6)] pl-2" : ""}`}
                >
                  <p className="text-[13px] text-[rgba(200,180,220,0.8)] truncate">
                    {conv.title || "Untitled"}
                  </p>
                  {conv.updated_at && (
                    <p className="text-[10px] text-[rgba(144,128,168,0.5)] mt-0.5">
                      {conv.updated_at.slice(0, 10)}
                    </p>
                  )}
                </button>
              ))
            )}
          </div>

          <div className="h-px bg-[rgba(139,63,168,0.1)]" />

          <MemoryPanel />
        </div>
      </div>

      <TimelineModal visible={timelineVisible} onClose={() => setTimelineVisible(false)} />
    </>
  );
}
