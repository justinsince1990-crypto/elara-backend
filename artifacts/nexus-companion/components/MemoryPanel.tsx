import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { api, type MemoryItem } from "@/lib/api";

export function MemoryPanel() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [addText, setAddText] = useState("");
  const [adding, setAdding] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (q?: string) => {
    setLoading(true);
    try {
      const res = await api.getMemory(q);
      setItems(res.items || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleQueryChange = (text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(text || undefined), 400);
  };

  const handleAdd = async () => {
    const fact = addText.trim();
    if (!fact) return;
    setAdding(true);
    try {
      await api.addMemory(fact);
      setAddText("");
      await load(query || undefined);
    } catch {}
    setAdding(false);
  };

  const handleDelete = async (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    try {
      await api.deleteMemory(id);
    } catch {
      load(query || undefined);
    }
  };

  const handleReindex = async () => {
    try {
      await api.reindexMemory();
    } catch {}
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.sectionTitle}>MEMORY</Text>
        <Pressable onPress={handleReindex} hitSlop={8}>
          <Text style={styles.reindex}>REINDEX</Text>
        </Pressable>
      </View>

      <TextInput
        style={styles.searchInput}
        value={query}
        onChangeText={handleQueryChange}
        placeholder="search..."
        placeholderTextColor="rgba(144,128,168,0.4)"
        testID="memory-search"
      />

      <View style={styles.addRow}>
        <TextInput
          style={[styles.searchInput, { flex: 1 }]}
          value={addText}
          onChangeText={setAddText}
          placeholder="add a fact..."
          placeholderTextColor="rgba(144,128,168,0.4)"
          testID="memory-add-input"
        />
        <Pressable
          onPress={handleAdd}
          disabled={adding || !addText.trim()}
          style={({ pressed }) => [styles.addBtn, pressed && { opacity: 0.7 }]}
          testID="memory-add-btn"
        >
          {adding ? (
            <ActivityIndicator size="small" color="#E8D8FF" />
          ) : (
            <Text style={{ fontSize: 16, color: "#E8D8FF" }}>+</Text>
          )}
        </Pressable>
      </View>

      {loading ? (
        <ActivityIndicator color="rgba(139,63,168,0.7)" size="small" />
      ) : items.length === 0 ? (
        <Text style={styles.empty}>no facts found</Text>
      ) : (
        items.slice(0, 12).map((item) => (
          <View key={item.id} style={styles.item}>
            <Text style={styles.itemText} numberOfLines={2}>{item.text}</Text>
            <Pressable
              onPress={() => handleDelete(item.id)}
              hitSlop={8}
              style={({ pressed }) => [{ opacity: pressed ? 0.5 : 1 }]}
              testID={`delete-memory-${item.id}`}
            >
              <Text style={{ fontSize: 12, color: "rgba(144,128,168,0.5)" }}>✕</Text>
            </Pressable>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: {
    color: "rgba(144,128,168,0.7)",
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
  },
  reindex: {
    color: "rgba(139,63,168,0.7)",
    fontSize: 9,
    letterSpacing: 1.5,
    fontFamily: "Inter_600SemiBold",
  },
  searchInput: {
    backgroundColor: "rgba(26,11,46,0.8)",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: "#D8C8F0",
    fontSize: 13,
    fontFamily: "Inter_400Regular",
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.15)",
  },
  addRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
  },
  addBtn: {
    backgroundColor: "rgba(139,63,168,0.5)",
    width: 36,
    height: 36,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  empty: {
    color: "rgba(144,128,168,0.5)",
    fontSize: 12,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
  },
  item: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(139,63,168,0.06)",
    gap: 8,
  },
  itemText: {
    flex: 1,
    color: "rgba(200,180,220,0.8)",
    fontSize: 12,
    lineHeight: 17,
    fontFamily: "Inter_400Regular",
  },
});
