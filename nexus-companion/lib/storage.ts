import AsyncStorage from "@react-native-async-storage/async-storage";

const KEYS = {
  AUTHED: "nexus_authed",
  CONVERSATION_ID: "nexus_conversation_id",
  SOUNDSCAPE: "nexus_soundscape",
  VOICE_ENABLED: "nexus_voice_enabled",
  LAST_NOTIF_ID: "nexus_last_notif_id",
} as const;

export const storage = {
  isAuthed: async (): Promise<boolean> => {
    const val = await AsyncStorage.getItem(KEYS.AUTHED);
    return val === "true";
  },

  setAuthed: async (authed: boolean): Promise<void> => {
    await AsyncStorage.setItem(KEYS.AUTHED, authed ? "true" : "false");
  },

  getConversationId: async (): Promise<string | null> => {
    return AsyncStorage.getItem(KEYS.CONVERSATION_ID);
  },

  setConversationId: async (id: string): Promise<void> => {
    await AsyncStorage.setItem(KEYS.CONVERSATION_ID, id);
  },

  getSoundscape: async (): Promise<string> => {
    const val = await AsyncStorage.getItem(KEYS.SOUNDSCAPE);
    return val || "off";
  },

  setSoundscape: async (scene: string): Promise<void> => {
    await AsyncStorage.setItem(KEYS.SOUNDSCAPE, scene);
  },

  getVoiceEnabled: async (): Promise<boolean> => {
    const val = await AsyncStorage.getItem(KEYS.VOICE_ENABLED);
    return val === null ? true : val === "true";
  },

  setVoiceEnabled: async (enabled: boolean): Promise<void> => {
    await AsyncStorage.setItem(KEYS.VOICE_ENABLED, enabled ? "true" : "false");
  },

  getLastNotifId: async (): Promise<string | null> => {
    return AsyncStorage.getItem(KEYS.LAST_NOTIF_ID);
  },

  setLastNotifId: async (id: string): Promise<void> => {
    await AsyncStorage.setItem(KEYS.LAST_NOTIF_ID, id);
  },

  getString: async (key: string): Promise<string | null> => {
    return AsyncStorage.getItem(key);
  },

  set: async (key: string, value: string): Promise<void> => {
    await AsyncStorage.setItem(key, value);
  },
};
