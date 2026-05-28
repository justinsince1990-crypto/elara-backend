import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Constants from "expo-constants";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "@/contexts/AppContext";
import { api, type Conversation } from "@/lib/api";
import { MemoryPanel } from "./MemoryPanel";
import { PinsSection } from "./PinsSection";
import { SoundscapePlayer } from "./SoundscapePlayer";
import { TimelineModal } from "./TimelineModal";

const DRAWER_WIDTH = Dimensions.get("window").width * 0.85;

interface DrawerPanelProps {
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

export function DrawerPanel({ onSelectConversation, onNewConversation }: DrawerPanelProps) {
  const {
    drawerOpen,
    setDrawerOpen,
    conversationId,
    conversations,
    setConversations,
    refreshConversations,
    voiceEnabled,
    setVoiceEnabled,
    mood,
  } = useApp();

  const MOOD_LABELS: Record<string, string> = {
    tender: "feeling tender right now",
    heavy: "in a heavy mood",
    playful: "feeling playful right now",
    sharp: "feeling sharp right now",
    neutral: "",
  };

  const insets = useSafeAreaInsets();
  const slideAnim = useRef(new Animated.Value(DRAWER_WIDTH)).current;
  const [timelineVisible, setTimelineVisible] = useState(false);
  const [pushTesting, setPushTesting] = useState(false);
  const [pushResult, setPushResult] = useState<string | null>(null);
  const isStandalone = Constants.appOwnership !== "expo";

  const handleTestPush = async () => {
    setPushTesting(true);
    setPushResult(null);
    try {
      const res = await api.pushTest();
      setPushResult(res.ok ? "sent" : res.message || "failed");
    } catch {
      setPushResult("Could not reach the server.");
    } finally {
      setPushTesting(false);
    }
  };

  useEffect(() => {
    Animated.timing(slideAnim, {
      toValue: drawerOpen ? 0 : DRAWER_WIDTH,
      duration: 280,
      useNativeDriver: true,
    }).start();

    if (drawerOpen) {
      refreshConversations();
    }
  }, [drawerOpen, slideAnim, refreshConversations]);

  if (!drawerOpen) return null;

  return (
    <>
      <Pressable style={styles.backdrop} onPress={() => setDrawerOpen(false)} />
      <Animated.View
        style={[
          styles.drawer,
          {
            transform: [{ translateX: slideAnim }],
            paddingTop: insets.top + 16,
            paddingBottom: insets.bottom + 20,
          },
        ]}
      >
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <View style={styles.drawerHeader}>
            <Text style={styles.drawerTitle}>e l a r a</Text>
            <Pressable onPress={() => setDrawerOpen(false)} hitSlop={12}>
              <Text style={styles.iconText}>✕</Text>
            </Pressable>
          </View>

          <SoundscapePlayer />

          {MOOD_LABELS[mood] ? (
            <Text style={styles.moodLabel}>{MOOD_LABELS[mood]}</Text>
          ) : null}

          <Pressable
            onPress={() => setVoiceEnabled(!voiceEnabled)}
            style={styles.voiceRow}
            hitSlop={8}
          >
            <Text style={styles.sectionTitle}>VOICE</Text>
            <View style={[styles.toggle, voiceEnabled && styles.toggleOn]}>
              <View style={[styles.toggleThumb, voiceEnabled && styles.toggleThumbOn]} />
            </View>
          </Pressable>

          <View style={styles.divider} />

          <PinsSection />

          <View style={styles.divider} />

          <Pressable
            onPress={() => setTimelineVisible(true)}
            style={({ pressed }) => [styles.storyBtn, pressed && { opacity: 0.7 }]}
            testID="our-story-btn"
          >
            <Text style={[styles.iconText, { fontSize: 13, color: "rgba(139,63,168,0.8)" }]}>◷</Text>
            <Text style={styles.storyBtnText}>OUR STORY</Text>
          </Pressable>

          {isStandalone && (
            <>
              <View style={styles.divider} />
              <View style={styles.pushSection}>
                <Text style={styles.sectionTitle}>NOTIFICATIONS</Text>
                <Pressable
                  onPress={handleTestPush}
                  disabled={pushTesting}
                  style={({ pressed }) => [styles.storyBtn, pressed && { opacity: 0.7 }]}
                  testID="test-push-btn"
                >
                  {pushTesting ? (
                    <ActivityIndicator size="small" color="rgba(139,63,168,0.8)" />
                  ) : (
                    <Text style={[styles.iconText, { fontSize: 13, color: "rgba(139,63,168,0.8)" }]}>{">"}</Text>
                  )}
                  <Text style={styles.storyBtnText}>TEST PUSH</Text>
                </Pressable>
                {pushResult && (
                  <Text style={[styles.empty, { marginTop: -4 }]}>
                    {pushResult === "sent" ? "push delivered" : pushResult}
                  </Text>
                )}
              </View>
            </>
          )}

          <View style={styles.divider} />

          <View style={styles.convSection}>
            <View style={styles.convHeader}>
              <Text style={styles.sectionTitle}>CONVERSATIONS</Text>
              <Pressable
                onPress={onNewConversation}
                hitSlop={8}
                style={({ pressed }) => [{ opacity: pressed ? 0.6 : 1 }]}
                testID="new-conversation-btn"
              >
                <Text style={[styles.iconText, { fontSize: 16, color: "rgba(139,63,168,0.8)" }]}>+</Text>
              </Pressable>
            </View>
            {conversations.length === 0 ? (
              <Text style={styles.empty}>no conversations</Text>
            ) : (
              conversations.slice(0, 12).map((conv) => (
                <Pressable
                  key={conv.id}
                  onPress={() => {
                    onSelectConversation(conv.id);
                    setDrawerOpen(false);
                  }}
                  style={({ pressed }) => [
                    styles.convItem,
                    conv.id === conversationId && styles.convItemActive,
                    pressed && { opacity: 0.7 },
                  ]}
                  testID={`conversation-${conv.id}`}
                >
                  <Text style={styles.convTitle} numberOfLines={1}>
                    {conv.title || "Untitled"}
                  </Text>
                  {conv.updated_at ? (
                    <Text style={styles.convDate}>
                      {conv.updated_at.slice(0, 10)}
                    </Text>
                  ) : null}
                </Pressable>
              ))
            )}
          </View>

          <View style={styles.divider} />

          <MemoryPanel />

          {isStandalone && (
            <>
              <View style={styles.divider} />
              <View style={styles.pushSection}>
                <Text style={styles.sectionTitle}>REBUILD APK</Text>
                <Text style={styles.buildInstructions}>
                  {"From Termux on the Pixel:\n\n"}
                  {"rm -rf nexus-companion && \\\n"}
                  {"curl -L https://nexus-companion.replit.app/source.zip \\\n"}
                  {"  -o src.zip && \\\n"}
                  {"unzip src.zip -d nexus-companion && \\\n"}
                  {"cd nexus-companion && npm install && \\\n"}
                  {"git init && git add -A && \\\n"}
                  {"git commit -m \"init\" && \\\n"}
                  {"EAS_SKIP_AUTO_FINGERPRINT=1 \\\n"}
                  {"  eas build --platform android \\\n"}
                  {"  --profile preview --no-wait \\\n"}
                  {"  --non-interactive"}
                </Text>
              </View>
            </>
          )}
        </ScrollView>
      </Animated.View>

      <TimelineModal visible={timelineVisible} onClose={() => setTimelineVisible(false)} />
    </>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.5)",
    zIndex: 10,
  },
  drawer: {
    position: "absolute",
    right: 0,
    top: 0,
    bottom: 0,
    width: DRAWER_WIDTH,
    backgroundColor: "#0A0218",
    zIndex: 11,
    borderLeftWidth: 1,
    borderLeftColor: "rgba(139,63,168,0.15)",
  },
  content: {
    paddingHorizontal: 20,
    gap: 16,
    paddingBottom: 20,
  },
  drawerHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  drawerTitle: {
    color: "rgba(200,180,220,0.6)",
    fontSize: 14,
    letterSpacing: 6,
    fontFamily: "Inter_400Regular",
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(139,63,168,0.1)",
    marginVertical: 4,
  },
  sectionTitle: {
    color: "rgba(144,128,168,0.7)",
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
  },
  storyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
  },
  storyBtnText: {
    color: "rgba(200,180,220,0.8)",
    fontSize: 11,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
  },
  pushSection: {
    gap: 6,
  },
  buildInstructions: {
    color: "rgba(144,128,168,0.55)",
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    lineHeight: 16,
    marginTop: 4,
  },
  convSection: {
    gap: 8,
  },
  convHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  convItem: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(139,63,168,0.06)",
  },
  convItemActive: {
    borderLeftWidth: 2,
    borderLeftColor: "rgba(139,63,168,0.6)",
    paddingLeft: 8,
  },
  convTitle: {
    color: "rgba(200,180,220,0.8)",
    fontSize: 13,
    fontFamily: "Inter_400Regular",
  },
  convDate: {
    color: "rgba(144,128,168,0.5)",
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    marginTop: 2,
  },
  empty: {
    color: "rgba(144,128,168,0.5)",
    fontSize: 12,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
  },
  moodLabel: {
    color: "rgba(144,128,168,0.55)",
    fontSize: 11,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
    marginTop: -6,
  },
  iconText: {
    fontSize: 18,
    color: "rgba(144,128,168,0.7)",
    lineHeight: 20,
  },
  voiceRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  toggle: {
    width: 44,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(144,128,168,0.2)",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  toggleOn: {
    backgroundColor: "rgba(139,63,168,0.7)",
  },
  toggleThumb: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "rgba(200,180,220,0.5)",
    alignSelf: "flex-start",
  },
  toggleThumbOn: {
    alignSelf: "flex-end",
    backgroundColor: "#D9D9E0",
  },
});
