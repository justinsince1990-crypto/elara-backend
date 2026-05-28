import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  useFonts,
} from "@expo-google-fonts/inter";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import React, { useEffect, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppProvider } from "@/contexts/AppContext";

const CRASH_KEY = "nexus_crash_log";

try {
  SplashScreen.preventAutoHideAsync();
} catch {}

const queryClient = new QueryClient();

function CrashOverlay({
  crash,
  onDismiss,
}: {
  crash: string;
  onDismiss: () => void;
}) {
  return (
    <View style={crashStyles.container}>
      <Text style={crashStyles.title}>⚠ JS Error from previous launch</Text>
      <Text style={crashStyles.hint}>
        Screenshot this and share it to help diagnose the crash.
        {"\n"}If this shows, the crash is in JavaScript (not native).
      </Text>
      <ScrollView style={crashStyles.scroll}>
        <Text style={crashStyles.message} selectable>
          {crash}
        </Text>
      </ScrollView>
      <TouchableOpacity style={crashStyles.btn} onPress={onDismiss}>
        <Text style={crashStyles.btnText}>DISMISS</Text>
      </TouchableOpacity>
    </View>
  );
}

const crashStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1a0a2e",
    padding: 20,
    paddingTop: 60,
  },
  title: {
    color: "#ff6060",
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 8,
  },
  hint: {
    color: "rgba(200,180,220,0.7)",
    fontSize: 12,
    marginBottom: 12,
    lineHeight: 18,
  },
  scroll: {
    flex: 1,
    backgroundColor: "rgba(255,255,255,0.05)",
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  message: {
    color: "#e0d0ff",
    fontSize: 11,
  },
  btn: {
    backgroundColor: "rgba(139,63,168,0.6)",
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  btnText: {
    color: "#E8D8FF",
    fontWeight: "bold",
    letterSpacing: 2,
  },
});

function useCrashLogger() {
  const [previousCrash, setPreviousCrash] = useState<string | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(CRASH_KEY)
      .then((val) => {
        if (val) {
          setPreviousCrash(val);
          AsyncStorage.removeItem(CRASH_KEY).catch(() => {});
        }
      })
      .catch(() => {});

    const prevHandler = ErrorUtils.getGlobalHandler();
    ErrorUtils.setGlobalHandler((error: Error, isFatal?: boolean) => {
      const log =
        `[${new Date().toISOString()}] ${isFatal ? "FATAL" : "Error"}\n` +
        `${error?.message ?? "unknown"}\n\n${error?.stack ?? ""}`;
      AsyncStorage.setItem(CRASH_KEY, log).catch(() => {});
      prevHandler?.(error, isFatal);
    });
  }, []);

  return {
    previousCrash,
    clearCrash: () => setPreviousCrash(null),
  };
}

function RootLayoutNav() {
  return (
    <Stack screenOptions={{ headerShown: false, animation: "fade" }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="chat" />
    </Stack>
  );
}

export default function RootLayout() {
  const { previousCrash, clearCrash } = useCrashLogger();

  const [fontsLoaded, fontError] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
  });

  useEffect(() => {
    if (fontsLoaded || fontError) {
      try {
        SplashScreen.hideAsync();
      } catch {}
    }
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) return null;

  if (previousCrash) {
    return <CrashOverlay crash={previousCrash} onDismiss={clearCrash} />;
  }

  return (
    <SafeAreaProvider>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <GestureHandlerRootView style={{ flex: 1 }}>
            <AppProvider>
              <RootLayoutNav />
            </AppProvider>
          </GestureHandlerRootView>
        </QueryClientProvider>
      </ErrorBoundary>
    </SafeAreaProvider>
  );
}
