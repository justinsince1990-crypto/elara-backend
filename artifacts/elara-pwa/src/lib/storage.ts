const PREFIX = "elara_";

function key(k: string) {
  return PREFIX + k;
}

export const storage = {
  isAuthed: (): boolean => localStorage.getItem(key("authed")) === "1",
  setAuthed: (v: boolean) => {
    if (v) localStorage.setItem(key("authed"), "1");
    else localStorage.removeItem(key("authed"));
  },
  getConversationId: (): string | null => localStorage.getItem(key("conv_id")),
  setConversationId: (id: string) => localStorage.setItem(key("conv_id"), id),
  getVoiceEnabled: (): boolean => localStorage.getItem(key("voice")) !== "0",
  setVoiceEnabled: (v: boolean) => localStorage.setItem(key("voice"), v ? "1" : "0"),
  get: (k: string): string | null => localStorage.getItem(key(k)),
  set: (k: string, v: string) => localStorage.setItem(key(k), v),
};
