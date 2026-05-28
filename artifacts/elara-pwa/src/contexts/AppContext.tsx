import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, type Conversation, type Message } from "@/lib/api";
import { storage } from "@/lib/storage";

type MoodCategory = "playful" | "heavy" | "tender" | "sharp" | "neutral";
type Page = "login" | "chat";

const MOOD_KEYWORDS: Record<MoodCategory, string[]> = {
  playful: ["playful", "light", "bright", "joyful", "curious", "silly", "excited", "cheerful"],
  heavy: ["heavy", "dark", "brooding", "melancholy", "somber", "tired", "serious", "introspective"],
  tender: ["tender", "soft", "warm", "gentle", "caring", "loving", "intimate", "vulnerable"],
  sharp: ["sharp", "alert", "focused", "intense", "restless", "electric", "urgent"],
  neutral: [],
};

export const MOOD_COLORS: Record<MoodCategory, string> = {
  playful: "rgba(80,40,120,0.5)",
  heavy: "rgba(20,10,40,0.7)",
  tender: "rgba(100,20,40,0.45)",
  sharp: "rgba(40,20,80,0.55)",
  neutral: "rgba(14,4,30,0.0)",
};

function detectMood(text: string): MoodCategory {
  const lower = text.toLowerCase();
  for (const [cat, keywords] of Object.entries(MOOD_KEYWORDS)) {
    if (cat === "neutral") continue;
    if (keywords.some((k) => lower.includes(k))) return cat as MoodCategory;
  }
  return "neutral";
}

interface AppContextType {
  page: Page;
  setPage: (p: Page) => void;
  authed: boolean;
  setAuthed: (v: boolean) => void;
  conversationId: string | null;
  setConversationId: (id: string) => void;
  conversations: Conversation[];
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  mood: MoodCategory;
  moodColor: string;
  moodVisible: boolean;
  setMoodFromText: (text: string) => void;
  isLongAway: boolean;
  setIsLongAway: (v: boolean) => void;
  healthOk: boolean;
  setHealthOk: (v: boolean) => void;
  drawerOpen: boolean;
  setDrawerOpen: (v: boolean) => void;
  loadConversation: (id: string) => Promise<void>;
  refreshConversations: () => Promise<void>;
  initialized: boolean;
  voiceEnabled: boolean;
  setVoiceEnabled: (v: boolean) => void;
}

const AppContext = createContext<AppContextType | null>(null);

let msgCounter = 0;
export function genId() {
  return `msg-${Date.now()}-${++msgCounter}-${Math.random().toString(36).slice(2, 8)}`;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState<Page>("login");
  const [authed, setAuthedState] = useState(false);
  const [conversationId, setConversationIdState] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [mood, setMood] = useState<MoodCategory>("neutral");
  const [moodColor, setMoodColor] = useState(MOOD_COLORS.neutral);
  const [moodVisible, setMoodVisible] = useState(false);
  const [isLongAway, setIsLongAway] = useState(false);
  const [healthOk, setHealthOk] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [voiceEnabled, setVoiceEnabledState] = useState(true);
  const moodTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setMoodFromText = useCallback((text: string) => {
    const cat = detectMood(text);
    setMood(cat);
    setMoodColor(MOOD_COLORS[cat]);
    setMoodVisible(false);
    requestAnimationFrame(() => setMoodVisible(true));
    if (moodTimeoutRef.current) clearTimeout(moodTimeoutRef.current);
    moodTimeoutRef.current = setTimeout(() => setMoodVisible(false), 8000);
  }, []);

  const setAuthed = useCallback(
    (v: boolean) => {
      storage.setAuthed(v);
      setAuthedState(v);
      if (v) setPage("chat");
      else setPage("login");
    },
    [],
  );

  const setVoiceEnabled = useCallback((v: boolean) => {
    storage.setVoiceEnabled(v);
    setVoiceEnabledState(v);
  }, []);

  const setConversationId = useCallback((id: string) => {
    storage.setConversationId(id);
    setConversationIdState(id);
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const res = await api.getConversation(id);
      const rawMessages = (res.conversation.messages as Message[] | undefined) || [];
      let c = 0;
      setMessages(
        rawMessages.map((m) => ({
          id: `loaded-${Date.now()}-${++c}`,
          role: m.role,
          content: m.content || "",
          ts: m.ts,
        })),
      );
    } catch {
      setMessages([]);
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const res = await api.listConversations();
      setConversations(res.conversations || []);
    } catch {}
  }, []);

  useEffect(() => {
    const authedVal = storage.isAuthed();
    const storedId = storage.getConversationId();
    const voiceVal = storage.getVoiceEnabled();
    setAuthedState(authedVal);
    if (authedVal) setPage("chat");
    if (storedId) setConversationIdState(storedId);
    setVoiceEnabledState(voiceVal);
    setInitialized(true);
  }, []);

  return (
    <AppContext.Provider
      value={{
        page,
        setPage,
        authed,
        setAuthed,
        conversationId,
        setConversationId,
        conversations,
        setConversations,
        messages,
        setMessages,
        mood,
        moodColor,
        moodVisible,
        setMoodFromText,
        isLongAway,
        setIsLongAway,
        healthOk,
        setHealthOk,
        drawerOpen,
        setDrawerOpen,
        loadConversation,
        refreshConversations,
        initialized,
        voiceEnabled,
        setVoiceEnabled,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be inside AppProvider");
  return ctx;
}
