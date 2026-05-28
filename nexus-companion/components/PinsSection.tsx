import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api, type Pin } from "@/lib/api";

export function PinsSection() {
  const [pins, setPins] = useState<Pin[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getPins();
      setPins(res.pins || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const dismiss = useCallback(
    async (id: string) => {
      setPins((prev) => prev.filter((p) => p.id !== id));
      try {
        await api.deletePin(id);
      } catch {
        load();
      }
    },
    [load]
  );

  return (
    <View style={styles.container}>
      <Text style={styles.sectionTitle}>FROM ELARA</Text>
      {loading ? (
        <ActivityIndicator color="rgba(139,63,168,0.7)" size="small" />
      ) : pins.length === 0 ? (
        <Text style={styles.empty}>nothing pinned yet</Text>
      ) : (
        pins.slice(0, 6).map((pin) => (
          <View key={pin.id} style={styles.card}>
            <Text style={styles.cardText}>{pin.text}</Text>
            <View style={styles.cardFooter}>
              {pin.ts ? (
                <Text style={styles.cardDate}>{pin.ts.slice(0, 10)}</Text>
              ) : (
                <View />
              )}
              <Pressable
                onPress={() => dismiss(pin.id)}
                hitSlop={8}
                style={({ pressed }) => [{ opacity: pressed ? 0.5 : 1 }]}
                testID={`dismiss-pin-${pin.id}`}
              >
                <Text style={{ fontSize: 14, color: "rgba(144,128,168,0.6)" }}>✕</Text>
              </Pressable>
            </View>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 8,
  },
  sectionTitle: {
    color: "rgba(144,128,168,0.7)",
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
  },
  empty: {
    color: "rgba(144,128,168,0.5)",
    fontSize: 12,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
  },
  card: {
    backgroundColor: "rgba(42,18,69,0.7)",
    borderRadius: 12,
    padding: 12,
    gap: 8,
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.12)",
  },
  cardText: {
    color: "#D8C8F0",
    fontSize: 13,
    lineHeight: 19,
    fontFamily: "Inter_400Regular",
    fontStyle: "italic",
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardDate: {
    color: "rgba(144,128,168,0.6)",
    fontSize: 10,
    fontFamily: "Inter_400Regular",
  },
});
