import React, { useCallback, useEffect, useState } from "react";
import { api, type TimelineMoment } from "@/lib/api";

function moodDotColor(mood?: string): string {
  if (!mood) return "rgba(139,63,168,0.6)";
  const m = mood.toLowerCase();
  if (m.includes("tender") || m.includes("warm")) return "#C05080";
  if (m.includes("heavy") || m.includes("dark")) return "#4A6080";
  if (m.includes("playful") || m.includes("bright")) return "#8050C0";
  if (m.includes("sharp") || m.includes("intense")) return "#7060A0";
  return "rgba(139,63,168,0.7)";
}

function moodBorderColor(mood?: string): string {
  if (!mood) return "rgba(139,63,168,0.4)";
  const m = mood.toLowerCase();
  if (m.includes("tender") || m.includes("warm")) return "rgba(192,80,128,0.6)";
  if (m.includes("heavy") || m.includes("dark")) return "rgba(74,96,128,0.6)";
  if (m.includes("playful") || m.includes("bright")) return "rgba(128,80,192,0.6)";
  if (m.includes("sharp") || m.includes("intense")) return "rgba(112,96,160,0.6)";
  return "rgba(139,63,168,0.4)";
}

function relativeTime(ts?: string): string {
  if (!ts) return "";
  const diffDays = Math.floor((Date.now() - new Date(ts).getTime()) / 86400000);
  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

function fullDate(ts?: string): string {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function FeaturedCard({ moment }: { moment: TimelineMoment }) {
  const [showFull, setShowFull] = useState(false);
  return (
    <button
      onClick={() => setShowFull((v) => !v)}
      className="text-left bg-[rgba(26,11,46,0.85)] rounded-[14px] px-4 py-3.5 border-l-[3px] flex flex-col gap-2 w-full"
      style={{ borderLeftColor: moodBorderColor(moment.mood) }}
    >
      <div className="flex items-center gap-2">
        <div
          className="w-2 h-2 rounded-full shrink-0"
          style={{ backgroundColor: moodDotColor(moment.mood) }}
        />
        {moment.mood && (
          <span className="text-[10px] italic text-[rgba(200,180,220,0.4)]">
            {moment.mood.toLowerCase()}
          </span>
        )}
      </div>
      <p className={`text-[14px] text-[#E0D0F8] leading-[21px] ${showFull ? "" : "line-clamp-3"}`}>
        {moment.text}
      </p>
      <span className="text-[11px] italic text-[rgba(144,128,168,0.55)]">
        {showFull ? fullDate(moment.ts) : relativeTime(moment.ts)}
      </span>
    </button>
  );
}

function CompactItem({ moment }: { moment: TimelineMoment }) {
  const [showFull, setShowFull] = useState(false);
  return (
    <button
      onClick={() => setShowFull((v) => !v)}
      className="flex gap-3 py-2.5 border-b border-[rgba(139,63,168,0.06)] items-start text-left w-full"
    >
      <div
        className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 opacity-70"
        style={{ backgroundColor: moodDotColor(moment.mood) }}
      />
      <div className="flex flex-col gap-0.5">
        <p
          className={`text-[12px] text-[rgba(200,180,220,0.75)] leading-[18px] ${showFull ? "" : "line-clamp-2"}`}
        >
          {moment.text}
        </p>
        <span className="text-[10px] italic text-[rgba(144,128,168,0.45)]">
          {showFull ? fullDate(moment.ts) : relativeTime(moment.ts)}
        </span>
      </div>
    </button>
  );
}

interface TimelineModalProps {
  visible: boolean;
  onClose: () => void;
}

export function TimelineModal({ visible, onClose }: TimelineModalProps) {
  const [moments, setMoments] = useState<TimelineMoment[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getTimeline();
      setMoments((res.moments || []).slice().reverse());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (visible) load();
  }, [visible, load]);

  if (!visible) return null;

  const featured = moments.slice(0, 3);
  const older = moments.slice(3);

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-[#0E0418] rounded-t-[24px] border-t border-[rgba(139,63,168,0.2)] max-h-[85dvh] flex flex-col timeline-enter">
        <div className="flex justify-between items-center px-5 pt-5 pb-4 shrink-0">
          <span className="text-[22px] text-[#E8D8FF] font-semibold italic">Our Story</span>
          <button
            onClick={onClose}
            className="text-[20px] text-[rgba(144,128,168,0.8)] active:opacity-60"
          >
            ✕
          </button>
        </div>
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 rounded-full border-2 border-[rgba(139,63,168,0.5)] border-t-transparent animate-spin" />
          </div>
        ) : moments.length === 0 ? (
          <p className="text-[14px] italic text-[rgba(200,180,220,0.45)] text-center px-8 py-16 leading-[22px]">
            no moments yet — she's watching for them
          </p>
        ) : (
          <div className="overflow-y-auto flex-1 px-5 pb-8">
            <div className="flex flex-col gap-3.5 mb-6">
              {featured.map((m, i) => (
                <FeaturedCard key={m.id || `f-${i}`} moment={m} />
              ))}
            </div>
            {older.length > 0 && (
              <div className="border-t border-[rgba(139,63,168,0.08)] pt-4">
                <p className="text-[10px] tracking-[2px] text-[rgba(144,128,168,0.4)] uppercase mb-3">
                  earlier
                </p>
                {older.map((m, i) => (
                  <CompactItem key={m.id || `o-${i}`} moment={m} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
