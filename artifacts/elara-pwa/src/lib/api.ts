const API = "/api";

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

const TIMEOUT = 22000;

async function apiFetch(path: string, options?: RequestInit, timeoutMs = TIMEOUT): Promise<unknown> {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...((options?.headers as Record<string, string>) || {}),
      },
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(tid);
  }
}

export const api = {
  health: () => apiFetch("/health", undefined, 8000) as Promise<{ ok: boolean }>,

  listConversations: () =>
    apiFetch("/conversations") as Promise<{ conversations: Conversation[] }>,

  createConversation: (title: string) =>
    apiFetch("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }) as Promise<{ conversation: Conversation & { messages?: Message[] } }>,

  getConversation: (id: string) =>
    apiFetch(`/conversations/${id}`) as Promise<{
      conversation: Conversation & { messages?: Message[] };
    }>,

  deleteConversation: (id: string) =>
    apiFetch(`/conversations/${id}`, { method: "DELETE" }),

  initiate: (conversationId: string) =>
    apiFetch(
      "/chat/initiate",
      { method: "POST", body: JSON.stringify({ conversation_id: conversationId }) },
      30000,
    ) as Promise<{ text: string; hours_away: number }>,

  streamChat: async (
    message: string,
    conversationId: string,
    image: string | null,
    onToken: (t: string) => void,
    onDone: (text: string, suggestions: string[]) => void,
    onError: (msg: string) => void,
  ): Promise<void> => {
    const body: Record<string, unknown> = { message, conversation_id: conversationId };
    if (image) body.image = image;

    let res: Response;
    try {
      res = await fetch(`${API}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
      });
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
    let gotFirstToken = false;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        gotFirstToken = true;
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
                onDone(
                  (parsed.text as string) || "",
                  (parsed.memory_suggestions as string[]) || [],
                );
              } else if (eventType === "error") {
                onError((parsed.message as string) || "Unknown error");
              }
            } catch {}
            eventType = "";
          }
        }
      }
    } catch {
      if (!gotFirstToken) onError("Connection dropped before response");
    }
  },

  getMemory: (query?: string) => {
    const q = query ? `?query=${encodeURIComponent(query)}` : "";
    return apiFetch(`/memory${q}`) as Promise<{ items: MemoryItem[] }>;
  },

  addMemory: (fact: string) =>
    apiFetch("/memory/add", {
      method: "POST",
      body: JSON.stringify({ fact }),
    }) as Promise<{ item: MemoryItem }>,

  deleteMemory: (id: string) => apiFetch(`/memory/${id}`, { method: "DELETE" }),

  reindexMemory: () => apiFetch("/memory/reindex", { method: "POST" }),

  getPins: () => apiFetch("/pins") as Promise<{ pins: Pin[] }>,

  deletePin: (id: string) => apiFetch(`/pins/${id}`, { method: "DELETE" }),

  getTimeline: () => apiFetch("/timeline") as Promise<{ moments: TimelineMoment[] }>,

  requestTTS: (text: string) =>
    apiFetch(
      "/tts",
      { method: "POST", body: JSON.stringify({ text, voice: "af_bella" }) },
      30000,
    ) as Promise<{ ok: boolean; hash: string; url: string }>,

  transcribe: (audioBase64: string, format = "webm") =>
    apiFetch(
      "/transcribe",
      { method: "POST", body: JSON.stringify({ audio: audioBase64, format }) },
      45000,
    ) as Promise<{ ok: boolean; text: string }>,
};
