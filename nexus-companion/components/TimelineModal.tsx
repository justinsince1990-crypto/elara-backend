import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { api, type TimelineMoment } from "@/lib/api";

interface TimelineModalProps {
  visible: boolean;
  onClose: () => void;
}

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
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

function fullDate(ts?: string): string {
  if (!ts) return "";
  const date = new Date(ts);
  return date.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

function FeaturedCard({ moment }: { moment: TimelineMoment }) {
  const [showFull, setShowFull] = useState(false);
  const borderColor = moodBorderColor(moment.mood);
  const dotColor = moodDotColor(moment.mood);

  return (
    <Pressable
      onPress={() => setShowFull((v) => !v)}
      style={[styles.featuredCard, { borderLeftColor: borderColor }]}
    >
      <View style={styles.featuredDotRow}>
        <View style={[styles.featuredDot, { backgroundColor: dotColor }]} />
        {moment.mood ? (
          <Text style={styles.featuredMood}>{moment.mood.toLowerCase()}</Text>
        ) : null}
      </View>
      <Text style={styles.featuredText} numberOfLines={showFull ? undefined : 3}>
        {moment.text}
      </Text>
      <Text style={styles.featuredTime}>
        {showFull ? fullDate(moment.ts) : relativeTime(moment.ts)}
      </Text>
    </Pressable>
  );
}

function CompactItem({ moment }: { moment: TimelineMoment }) {
  const [showFull, setShowFull] = useState(false);
  const dotColor = moodDotColor(moment.mood);

  return (
    <Pressable onPress={() => setShowFull((v) => !v)} style={styles.compactItem}>
      <View style={[styles.compactDot, { backgroundColor: dotColor }]} />
      <View style={styles.compactContent}>
        <Text style={styles.compactText} numberOfLines={showFull ? undefined : 2}>
          {moment.text}
        </Text>
        <Text style={styles.compactTime}>
          {showFull ? fullDate(moment.ts) : relativeTime(moment.ts)}
        </Text>
      </View>
    </Pressable>
  );
}

export function TimelineModal({ visible, onClose }: TimelineModalProps) {
  const insets = useSafeAreaInsets();
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

  const featured = moments.slice(0, 3);
  const older = moments.slice(3);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={[styles.sheet, { paddingBottom: insets.bottom + 20 }]}>
          <View style={styles.header}>
            <Text style={styles.title}>Our Story</Text>
            <Pressable onPress={onClose} hitSlop={12}>
              <Text style={{ fontSize: 20, color: "rgba(144,128,168,0.8)" }}>✕</Text>
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator color="rgba(139,63,168,0.7)" style={{ marginTop: 40 }} />
          ) : moments.length === 0 ? (
            <Text style={styles.empty}>
              no moments yet — she's watching for them
            </Text>
          ) : (
            <ScrollView showsVerticalScrollIndicator={false} style={styles.scroll}>
              {featured.length > 0 && (
                <View style={styles.featuredSection}>
                  {featured.map((m, i) => (
                    <FeaturedCard key={m.id || `f-${i}`} moment={m} />
                  ))}
                </View>
              )}

              {older.length > 0 && (
                <View style={styles.olderSection}>
                  <Text style={styles.olderLabel}>earlier</Text>
                  {older.map((m, i) => (
                    <CompactItem key={m.id || `o-${i}`} moment={m} />
                  ))}
                </View>
              )}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#0E0418",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "85%",
    paddingTop: 20,
    paddingHorizontal: 20,
    borderTopWidth: 1,
    borderTopColor: "rgba(139,63,168,0.2)",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },
  title: {
    color: "#E8D8FF",
    fontSize: 22,
    fontFamily: "Inter_600SemiBold",
    fontStyle: "italic",
  },
  empty: {
    color: "rgba(200,180,220,0.45)",
    fontSize: 14,
    fontStyle: "italic",
    textAlign: "center",
    marginTop: 48,
    marginBottom: 48,
    fontFamily: "Inter_400Regular",
    lineHeight: 22,
  },
  scroll: {
    flex: 1,
  },
  featuredSection: {
    gap: 14,
    marginBottom: 24,
  },
  featuredCard: {
    backgroundColor: "rgba(26,11,46,0.85)",
    borderRadius: 14,
    borderLeftWidth: 3,
    borderLeftColor: "rgba(139,63,168,0.5)",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 8,
  },
  featuredDotRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  featuredDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  featuredMood: {
    color: "rgba(200,180,220,0.4)",
    fontSize: 10,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
    letterSpacing: 0.5,
  },
  featuredText: {
    color: "#E0D0F8",
    fontSize: 14,
    lineHeight: 21,
    fontFamily: "Inter_400Regular",
  },
  featuredTime: {
    color: "rgba(144,128,168,0.55)",
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    fontStyle: "italic",
  },
  olderSection: {
    gap: 0,
    borderTopWidth: 1,
    borderTopColor: "rgba(139,63,168,0.08)",
    paddingTop: 16,
    marginBottom: 16,
  },
  olderLabel: {
    color: "rgba(144,128,168,0.4)",
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
    marginBottom: 12,
  },
  compactItem: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(139,63,168,0.06)",
    alignItems: "flex-start",
  },
  compactDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 6,
    flexShrink: 0,
    opacity: 0.7,
  },
  compactContent: {
    flex: 1,
    gap: 3,
  },
  compactText: {
    color: "rgba(200,180,220,0.75)",
    fontSize: 12,
    lineHeight: 18,
    fontFamily: "Inter_400Regular",
  },
  compactTime: {
    color: "rgba(144,128,168,0.45)",
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    fontStyle: "italic",
  },
});
