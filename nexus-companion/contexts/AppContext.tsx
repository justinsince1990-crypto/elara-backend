import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Animated, Platform } from "react-native";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { api, type Conversation, type Message } from "@/lib/api";
import { storage } from "@/lib/storage";

type MoodCategory = "playful" | "heavy" | "tender" | "sharp" | "neutral";

const MOOD_KEYWORDS: Record<MoodCategory, string[]> = {
  playful: ["playful", "light", "bright", "joyful", "curious", "silly", "excited", "cheerful"],
  heavy: ["heavy", "dark", "brooding", "melancholy", "somber", "tired", "serious", "introspective"],
  tender: ["tender", "soft", "warm", "gentle", "caring", "loving", "intimate", "vulnerable"],
  sharp: ["sharp", "alert", "focused", "intense", "restless", "electric", "urgent"],
  neutral: [],
};

const MOOD_COLORS: Record<MoodCategory, string> = {
  playful: "rgba(80,40,120,0.5)",
  heavy: "rgba(20,10,40,0.7)",
  tender: "rgba(100,20,40,0.45)",
  sharp: "rgba(40,20,80,0.55)",
  neutral: "rgba(14,4,30,0.0)",
};

const MOOD_TO_SOUNDSCAPE: Record<MoodCategory, string> = {
  heavy: "rain",
  tender: "fire",
  playful: "forest",
  sharp: "city",
  neutral: "off",
};

function detectMood(moodText: string): MoodCategory {
  const lower = moodText.toLowerCase();
  for (const [cat, keywords] of Object.entries(MOOD_KEYWORDS)) {
    if (cat === "neutral") continue;
    if (keywords.some((k) => lower.includes(k))) {
      return cat as MoodCategory;
    }
  }
  return "neutral";
}


interface AppContextType {
  authed: boolean;
  setAuthed: (v: boolean) => void;
  conversationId: string | null;
  setConversationId: (id: string) => void;
  conversations: Conversation[];
  setConversations: (c: Conversation[]) => void;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  mood: MoodCategory;
  moodColor: string;
  moodOpacity: Animated.Value;
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
  autoSoundscape: string | null;
  soundscapeManualOverride: boolean;
  setSoundscapeManualOverride: (v: boolean) => void;
  pendingNotificationMessage: string | null;
  clearPendingNotificationMessage: () => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [authed, setAuthedState] = useState(false);
  const [conversationId, setConversationIdState] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [mood, setMood] = useState<MoodCategory>("neutral");
  const [moodColor, setMoodColor] = useState<string>(MOOD_COLORS.neutral);
  const [isLongAway, setIsLongAway] = useState(false);
  const [healthOk, setHealthOk] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [voiceEnabled, setVoiceEnabledState] = useState(true);
  const [autoSoundscape, setAutoSoundscape] = useState<string | null>(null);
  const [soundscapeManualOverride, setSoundscapeManualOverride] = useState(false);
  const [pendingNotificationMessage, setPendingNotificationMessage] = useState<string | null>(null);

  const moodOpacity = useRef(new Animated.Value(0)).current;

  const setMoodFromText = useCallback((text: string) => {
    const cat = detectMood(text);
    setMood(cat);
    const color = MOOD_COLORS[cat];
    setMoodColor(color);
    moodOpacity.setValue(0);
    Animated.timing(moodOpacity, {
      toValue: 1,
      duration: 1500,
      useNativeDriver: false,
    }).start();

    setSoundscapeManualOverride((override) => {
      if (!override) {
        setAutoSoundscape(MOOD_TO_SOUNDSCAPE[cat]);
      }
      return override;
    });
  }, [moodOpacity]);

  const setAuthed = useCallback(async (v: boolean) => {
    await storage.setAuthed(v);
    setAuthedState(v);
  }, []);

  const setVoiceEnabled = useCallback(async (v: boolean) => {
    await storage.setVoiceEnabled(v);
    setVoiceEnabledState(v);
  }, []);

  const setConversationId = useCallback(async (id: string) => {
    await storage.setConversationId(id);
    setConversationIdState(id);
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const res = await api.getConversation(id);
      const rawMessages = (res.conversation.messages as Message[] | undefined) || [];
      let counter = 0;
      const msgs: Message[] = rawMessages.map((m) => ({
        id: `loaded-${Date.now()}-${++counter}-${Math.random().toString(36).substr(2, 5)}`,
        role: m.role,
        content: m.content || "",
        ts: m.ts,
      }));
      setMessages(msgs);
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

  const clearPendingNotificationMessage = useCallback(() => {
    setPendingNotificationMessage(null);
  }, []);

  const lastProcessedNotifIdRef = useRef<string | null>(null);

  const processNotifResponse = useCallback((response: Notifications.NotificationResponse) => {
    try {
      const id = response.notification.request.identifier;
      if (lastProcessedNotifIdRef.current === id) return;
      lastProcessedNotifIdRef.current = id;
      storage.setLastNotifId(id).catch(() => {});
      const data = response.notification.request.content.data as Record<string, unknown> | undefined;
      const message = data?.message as string | undefined;
      if (message?.trim()) {
        setPendingNotificationMessage(message.trim());
      }
      router.push("/chat");
    } catch {}
  }, []);

  useEffect(() => {
    try {
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowAlert: true,
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: true,
          shouldSetBadge: false,
        }),
      });
    } catch {}
  }, []);

  useEffect(() => {
    (async () => {
      const authedVal = await storage.isAuthed();
      setAuthedState(authedVal);
      const storedId = await storage.getConversationId();
      if (storedId) setConversationIdState(storedId);
      const voiceVal = await storage.getVoiceEnabled();
      setVoiceEnabledState(voiceVal);
      setInitialized(true);
    })();
  }, []);

  // Cold-start + foreground tap: useLastNotificationResponse covers both paths
  // (works with expo-notifications 0.32.x API)
  const lastNotificationResponse = Notifications.useLastNotificationResponse();
  useEffect(() => {
    if (!lastNotificationResponse) return;
    const id = lastNotificationResponse.notification.request.identifier;
    storage.getLastNotifId().then((lastSeenId) => {
      if (id !== lastSeenId) {
        processNotifResponse(lastNotificationResponse);
      }
    }).catch(() => {
      processNotifResponse(lastNotificationResponse);
    });
  }, [lastNotificationResponse, processNotifResponse]);

  const pushRegisteredRef = useRef(false);
  useEffect(() => {
    if (!authed || pushRegisteredRef.current) return;
    if (Constants.appOwnership === "expo") return;
    pushRegisteredRef.current = true;
    const logPush = async (msg: string) => {
      console.log(`[push] ${msg}`);
      try {
        const prev = await storage.getString("push_log");
        const ts = new Date().toISOString().slice(0, 19);
        const entry = `${ts} ${msg}`;
        const lines = prev ? prev.split("\n").slice(-19) : [];
        lines.push(entry);
        await storage.set("push_log", lines.join("\n"));
      } catch {}
    };
    (async () => {
      try {
        let serverHasToken = false;
        try {
          const status = await api.pushStatus();
          serverHasToken = status.registered;
          await logPush(`server status: registered=${status.registered}`);
        } catch {
          await logPush("server status check failed");
        }

        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("default", {
            name: "Elara",
            importance: Notifications.AndroidImportance.MAX,
            vibrationPattern: [0, 250, 250, 250],
          });
        }
        const { status } = await Notifications.requestPermissionsAsync();
        if (status !== "granted") {
          await logPush("permission denied");
          return;
        }
        const tokenData = await Notifications.getExpoPushTokenAsync({
          projectId: "9f89acff-0b23-430f-8fa6-234b7d33c8ad",
        });
        if (!tokenData?.data) {
          await logPush("no token returned from Expo");
          pushRegisteredRef.current = false;
          return;
        }
        const localToken = tokenData.data;
        const res = await api.registerPushToken(localToken);
        if (res.ok) {
          await logPush(`registered: ${serverHasToken ? "refreshed" : "new"} token`);
        } else {
          await logPush("registration call failed");
          pushRegisteredRef.current = false;
        }
      } catch (e) {
        await logPush(`error: ${e}`);
        pushRegisteredRef.current = false;
      }
    })();
  }, [authed]);

  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener(processNotifResponse);
    return () => sub.remove();
  }, [processNotifResponse]);

  return (
    <AppContext.Provider
      value={{
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
        moodOpacity,
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
        autoSoundscape,
        soundscapeManualOverride,
        setSoundscapeManualOverride,
        pendingNotificationMessage,
        clearPendingNotificationMessage,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export { detectMood, MOOD_COLORS, MOOD_TO_SOUNDSCAPE, type MoodCategory };
