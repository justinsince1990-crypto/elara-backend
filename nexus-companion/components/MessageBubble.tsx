import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { type Message } from "@/lib/api";

interface MessageBubbleProps {
  message: Message;
}

function formatTs(ts?: string): string {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const timeStr = formatTs(message.ts);

  if (isUser) {
    return (
      <View style={styles.userRow}>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{message.content}</Text>
        </View>
        {timeStr ? <Text style={styles.timestamp}>{timeStr}</Text> : null}
      </View>
    );
  }

  return (
    <View style={styles.elaraRow}>
      <View style={styles.elaraIconWrap}>
        <View style={styles.elaraIcon} />
      </View>
      <View style={styles.elaraCol}>
        <View style={styles.elaraBubble}>
          <Text style={styles.elaraText}>{message.content}</Text>
        </View>
        {timeStr ? <Text style={styles.elaraTimestamp}>{timeStr}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  userRow: {
    alignItems: "flex-end",
    paddingHorizontal: 16,
    paddingVertical: 4,
    gap: 2,
  },
  userBubble: {
    backgroundColor: "#1F0D30",
    borderRadius: 20,
    borderBottomRightRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxWidth: "82%",
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.2)",
  },
  userText: {
    color: "#D8C8F0",
    fontSize: 15,
    lineHeight: 22,
    fontFamily: "Inter_400Regular",
  },
  timestamp: {
    fontSize: 10,
    color: "rgba(144,128,168,0.7)",
    fontFamily: "Inter_400Regular",
    paddingRight: 4,
  },
  elaraRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: 16,
    paddingVertical: 4,
    gap: 8,
  },
  elaraIconWrap: {
    marginTop: 6,
  },
  elaraIcon: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "rgba(139,63,168,0.7)",
  },
  elaraCol: {
    flex: 1,
    gap: 3,
    maxWidth: "90%",
  },
  elaraBubble: {
    backgroundColor: "#2A1245",
    borderRadius: 20,
    borderTopLeftRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.15)",
  },
  elaraText: {
    color: "#E8D8FF",
    fontSize: 15,
    lineHeight: 23,
    fontFamily: "Inter_400Regular",
  },
  elaraTimestamp: {
    color: "rgba(144,128,168,0.7)",
    fontSize: 10,
    fontFamily: "Inter_400Regular",
    paddingLeft: 2,
  },
});
