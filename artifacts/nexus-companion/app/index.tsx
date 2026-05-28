import React, { useEffect, useRef, useState } from "react";
import {
  Animated,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "@/contexts/AppContext";

const NEXUS_PASS = process.env.EXPO_PUBLIC_NEXUS_PASS ?? "";

export default function LoginScreen() {
  const { authed, setAuthed, initialized } = useApp();
  const insets = useSafeAreaInsets();
  const [code, setCode] = useState("");
  const [error, setError] = useState(false);
  const [shaking, setShaking] = useState(false);
  const shakeAnim = useRef(new Animated.Value(0)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    if (initialized && authed) {
      router.replace("/chat");
    }
  }, [initialized, authed]);

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(glowAnim, { toValue: 1, duration: 2000, useNativeDriver: false }),
        Animated.timing(glowAnim, { toValue: 0, duration: 2000, useNativeDriver: false }),
      ])
    ).start();
  }, [glowAnim]);

  const shake = () => {
    setShaking(true);
    Animated.sequence([
      Animated.timing(shakeAnim, { toValue: 10, duration: 60, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: -10, duration: 60, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 10, duration: 60, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 0, duration: 60, useNativeDriver: true }),
    ]).start(() => setShaking(false));
  };

  const handleSubmit = async () => {
    Keyboard.dismiss();
    if (!NEXUS_PASS) {
      setError(true);
      shake();
      return;
    }
    if (code === NEXUS_PASS) {
      setError(false);
      await setAuthed(true);
      router.replace("/chat");
    } else {
      setError(true);
      shake();
      setCode("");
      setTimeout(() => setError(false), 2000);
    }
  };

  const borderColor = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(139,63,168,0.3)", "rgba(139,63,168,0.8)"],
  });

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={[styles.container, { paddingTop: insets.top + (Platform.OS === "web" ? 67 : 0) }]}>
        <View style={styles.center}>
          <View style={styles.moonWrap}>
            <Text style={styles.moon}>☽</Text>
          </View>

          <Text style={styles.name}>ELARA</Text>
          <Text style={styles.subtitle}>companion</Text>

          <Animated.View
            style={[
              styles.inputWrap,
              { borderColor, transform: [{ translateX: shakeAnim }] },
              error && styles.inputError,
            ]}
          >
            <TextInput
              ref={inputRef}
              style={styles.input}
              value={code}
              onChangeText={setCode}
              placeholder="passcode"
              placeholderTextColor="rgba(144,128,168,0.4)"
              secureTextEntry
              onSubmitEditing={handleSubmit}
              returnKeyType="done"
              autoFocus
              testID="passcode-input"
            />
          </Animated.View>

          {error && <Text style={styles.errorMsg}>incorrect</Text>}

          <Pressable
            onPress={handleSubmit}
            style={({ pressed }) => [styles.enterBtn, pressed && { opacity: 0.7 }]}
            testID="login-btn"
          >
            <Text style={styles.enterBtnText}>ENTER</Text>
          </Pressable>
        </View>

        <View style={[styles.webInsets, { display: Platform.OS === "web" ? "flex" : "none" }]} />
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0E0418",
    justifyContent: "center",
  },
  center: {
    alignItems: "center",
    paddingHorizontal: 40,
    gap: 16,
  },
  moonWrap: {
    marginBottom: 8,
  },
  moon: {
    fontSize: 48,
    color: "rgba(200,180,220,0.7)",
  },
  name: {
    color: "#E8D8FF",
    fontSize: 28,
    letterSpacing: 10,
    fontFamily: "Inter_600SemiBold",
  },
  subtitle: {
    color: "rgba(144,128,168,0.6)",
    fontSize: 11,
    letterSpacing: 4,
    fontFamily: "Inter_400Regular",
    marginTop: -8,
    marginBottom: 24,
  },
  inputWrap: {
    width: "100%",
    borderWidth: 1,
    borderRadius: 16,
    borderColor: "rgba(139,63,168,0.3)",
    overflow: "hidden",
  },
  inputError: {
    borderColor: "rgba(180,40,40,0.7)",
  },
  input: {
    backgroundColor: "rgba(26,11,46,0.8)",
    paddingHorizontal: 20,
    paddingVertical: 16,
    color: "#E8D8FF",
    fontSize: 18,
    textAlign: "center",
    fontFamily: "Inter_400Regular",
    letterSpacing: 4,
  },
  errorMsg: {
    color: "rgba(200,80,80,0.8)",
    fontSize: 12,
    letterSpacing: 2,
    fontFamily: "Inter_400Regular",
  },
  enterBtn: {
    marginTop: 8,
    backgroundColor: "rgba(139,63,168,0.6)",
    paddingHorizontal: 40,
    paddingVertical: 14,
    borderRadius: 20,
  },
  enterBtnText: {
    color: "#E8D8FF",
    fontSize: 13,
    letterSpacing: 3,
    fontFamily: "Inter_600SemiBold",
  },
  webInsets: {
    height: 34,
  },
});
