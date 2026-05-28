import { fetch, type FetchRequestInit } from "expo/fetch";

const getBackendUrl = (): string => {
  return process.env.EXPO_PUBLIC_BACKEND_URL || "http://45.32.201.59";
};

export interface Conversation {
  id: string;
  title: string;
  updated_at?: string;
  created_at?: string;
  message_count?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts?: string;
  isImage?: boolean;
}

export interface MemoryItem {
  id: string;
  text: string;
  created_at: string;
  updated_at: string;
}

export interface Pin {
  id: string;
  text: string;
  ts?: string;
}

export interface TimelineMoment {
  id?: string;
  text: string;
  mood?: string;
  ts: string;
}

const API_TIMEOUT_MS = 22000;

async function apiFetch(path: string, options?: Omit<FetchRequestInit, "body"> & { body?: string }, timeoutMs = API_TIMEOUT_MS): Promise<unknown> {
  const url = `${getBackendUrl()}${path}`;
  const init: FetchRequestInit = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers as Record<string, string> || {}),
    },
  };
  if (options?.body !== undefined) {
    init.body = options.body;
  }

  const timeoutPromise = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error("Request timed out")), timeoutMs)
  );

  const res = await Promise.race([fetch(url, init), timeoutPromise]);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  health: async (): Promise<{ ok: boolean }> => {
    return apiFetch("/health", undefined, 8000) as Promise<{ ok: boolean }>;
  },

  listConversations: async (): Promise<{ conversations: Conversation[] }> => {
    return apiFetch("/conversations") as Promise<{ conversations: Conversation[] }>;
  },

  createConversation: async (title: string): Promise<{ conversation: Conversation & { messages?: Message[] } }> => {
    return apiFetch("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }) as Promise<{ conversation: Conversation & { messages?: Message[] } }>;
  },

  getConversation: async (id: string): Promise<{ conversation: Conversation & { messages?: Message[] } }> => {
    return apiFetch(`/conversations/${id}`) as Promise<{ conversation: Conversation & { messages?: Message[] } }>;
  },

  renameConversation: async (id: string, title: string): Promise<void> => {
    await apiFetch(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  deleteConversation: async (id: string): Promise<void> => {
    await apiFetch(`/conversations/${id}`, { method: "DELETE" });
  },

  initiate: async (conversationId: string): Promise<{ text: string; hours_away: number }> => {
    return apiFetch("/chat/initiate", {
      method: "POST",
      body: JSON.stringify({ conversation_id: conversationId }),
    }, 30000) as Promise<{ text: string; hours_away: number }>;
  },

  streamChat: async (
    message: string,
    conversationId: string,
    image: string | null,
    onToken: (t: string) => void,
    onDone: (text: string, memorySuggestions: string[]) => void,
    onError: (msg: string) => void,
  ): Promise<void> => {
    const url = `${getBackendUrl()}/chat/stream`;
    const body: Record<string, unknown> = {
      message,
      conversation_id: conversationId,
    };
    if (image) body.image = image;

    let res: Awaited<ReturnType<typeof fetch>>;
    const connectTimeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Connection timed out")), 25000)
    );

    try {
      res = await Promise.race([
        fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          body: JSON.stringify(body),
        }),
        connectTimeout,
      ]);
    } catch (e) {
      onError((e as Error).message || "Connection failed");
      return;
    }

    if (!res.ok) {
      onError(`HTTP ${res.status}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError("No response body");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let eventType = "";
    let firstTokenReceived = false;
    let streamTimeoutId: ReturnType<typeof setTimeout> | null = null;

    const resetStreamTimeout = () => {
      if (streamTimeoutId) clearTimeout(streamTimeoutId);
      streamTimeoutId = setTimeout(() => {
        reader.cancel().catch(() => {});
        onError("Elara took too long to respond — try again");
      }, 120000);
    };

    resetStreamTimeout();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        if (!firstTokenReceived) {
          firstTokenReceived = true;
        }
        resetStreamTimeout();

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            if (!data) continue;
            try {
              const parsed = JSON.parse(data) as Record<string, unknown>;
              if (eventType === "token") {
                const t = parsed.t as string | undefined;
                if (t) onToken(t);
              } else if (eventType === "done") {
                const text = (parsed.text as string) || "";
                const suggestions = (parsed.memory_suggestions as string[]) || [];
                onDone(text, suggestions);
              } else if (eventType === "error") {
                onError((parsed.message as string) || "Unknown error");
              }
            } catch {}
            eventType = "";
          }
        }
      }
    } catch (e) {
      if (!firstTokenReceived) {
        onError("Connection dropped before Elara could respond");
      }
    } finally {
      if (streamTimeoutId) clearTimeout(streamTimeoutId);
    }
  },

  getMemory: async (query?: string): Promise<{ items: MemoryItem[] }> => {
    const q = query ? `?query=${encodeURIComponent(query)}` : "";
    return apiFetch(`/memory${q}`) as Promise<{ items: MemoryItem[] }>;
  },

  addMemory: async (fact: string): Promise<{ item: MemoryItem }> => {
    return apiFetch("/memory/add", {
      method: "POST",
      body: JSON.stringify({ fact }),
    }) as Promise<{ item: MemoryItem }>;
  },

  deleteMemory: async (id: string): Promise<void> => {
    await apiFetch(`/memory/${id}`, { method: "DELETE" });
  },

  reindexMemory: async (): Promise<void> => {
    await apiFetch("/memory/reindex", { method: "POST" });
  },

  getPins: async (): Promise<{ pins: Pin[] }> => {
    return apiFetch("/pins") as Promise<{ pins: Pin[] }>;
  },

  deletePin: async (id: string): Promise<void> => {
    await apiFetch(`/pins/${id}`, { method: "DELETE" });
  },

  getTimeline: async (): Promise<{ moments: TimelineMoment[] }> => {
    return apiFetch("/timeline") as Promise<{ moments: TimelineMoment[] }>;
  },

  getAwayState: async (): Promise<{ hours_away: number }> => {
    return apiFetch("/away_state") as Promise<{ hours_away: number }>;
  },

  getSelf: async (): Promise<Record<string, unknown>> => {
    return apiFetch("/self") as Promise<Record<string, unknown>>;
  },

  requestTTS: async (text: string, voice?: string): Promise<{ ok: boolean; hash: string; url: string }> => {
    return apiFetch("/tts", {
      method: "POST",
      body: JSON.stringify({ text, voice: voice || "af_bella" }),
    }, 30000) as Promise<{ ok: boolean; hash: string; url: string }>;
  },

  registerPushToken: async (token: string): Promise<{ ok: boolean }> => {
    return apiFetch("/push_token", {
      method: "POST",
      body: JSON.stringify({ token }),
    }) as Promise<{ ok: boolean }>;
  },

  pushStatus: async (): Promise<{ ok: boolean; registered: boolean; token_preview: string; updated_at: string }> => {
    return apiFetch("/push/status") as Promise<{ ok: boolean; registered: boolean; token_preview: string; updated_at: string }>;
  },

  pushTest: async (): Promise<{ ok: boolean; error?: string; message: string }> => {
    return apiFetch("/push/test", { method: "POST" }) as Promise<{ ok: boolean; error?: string; message: string }>;
  },

  transcribe: async (audioBase64: string, format?: string): Promise<{ ok: boolean; text: string }> => {
    return apiFetch("/transcribe", {
      method: "POST",
      body: JSON.stringify({ audio: audioBase64, format: format || "m4a" }),
    }, 45000) as Promise<{ ok: boolean; text: string }>;
  },
};
