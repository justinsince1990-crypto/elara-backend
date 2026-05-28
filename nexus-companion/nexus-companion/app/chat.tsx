import * as FileSystem from "expo-file-system/legacy";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { Audio } from "expo-av";
import { router } from "expo-router";
import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { DrawerPanel } from "@/components/DrawerPanel";
import { HealthDot } from "@/components/HealthDot";
import { MessageBubble } from "@/components/MessageBubble";
import { TypingIndicator } from "@/components/TypingIndicator";
import { useApp } from "@/contexts/AppContext";
import { api, type Message } from "@/lib/api";

let messageCounter = 0;
function genId(): string {
  messageCounter++;
  return `msg-${Date.now()}-${messageCounter}-${Math.random().toString(36).substr(2, 9)}`;
}

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8001";

export default function ChatScreen() {
  const {
    authed,
    initialized,
    messages,
    setMessages,
    conversationId,
    setConversationId,
    refreshConversations,
    loadConversation,
    setMoodFromText,
    moodColor,
    moodOpacity,
    isLongAway,
    setIsLongAway,
    healthOk,
    setHealthOk,
    drawerOpen,
    setDrawerOpen,
    voiceEnabled,
    pendingNotificationMessage,
    clearPendingNotificationMessage,
  } = useApp();

  const insets = useSafeAreaInsets();
  const inputRef = useRef<TextInput>(null);
  const [inputText, setInputText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [showTyping, setShowTyping] = useState(false);
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [ttsLoading, setTtsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const soundRef = useRef<Audio.Sound | null>(null);
  const lastElaraTextRef = useRef<string>("");
  const ttsHashCache = useRef<Map<string, string>>(new Map());
  const awayTintAnim = useRef(new Animated.Value(0)).current;
  const initializedRef = useRef(false);
  const [convReady, setConvReady] = useState(false);
  const prevHealthOkRef = useRef(true);
  const needsInitiateRef = useRef(false);
  const pendingRetryRef = useRef<{ msg: string; img: string | null; convId: string } | null>(null);
  const streamSendRef = useRef<(msg: string, img: string | null, convId: string, isRetry?: boolean) => Promise<void>>(async () => {});
  const playTTSRef = useRef<(text: string) => Promise<void>>(async () => {});
  const [pollFast, setPollFast] = useState(false);

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const pulseLoop = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (!authed) {
      router.replace("/");
    }
  }, [authed]);

  useEffect(() => {
    if (isLongAway) {
      Animated.timing(awayTintAnim, {
        toValue: 1,
        duration: 1000,
        useNativeDriver: false,
      }).start();
    } else {
      Animated.timing(awayTintAnim, {
        toValue: 0,
        duration: 600,
        useNativeDriver: false,
      }).start();
    }
  }, [isLongAway, awayTintAnim]);

  const probeHealth = useCallback(async () => {
    try {
      await api.health();
      const wasDown = !prevHealthOkRef.current;
      prevHealthOkRef.current = true;
      setHealthOk(true);
      if (wasDown) {
        setPollFast(false);
        const pending = pendingRetryRef.current;
        pendingRetryRef.current = null;
        if (pending) {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", content: "*(she's back — resending…)*", ts: new Date().toISOString() },
          ]);
          setTimeout(() => streamSendRef.current(pending.msg, pending.img, pending.convId, false), 500);
        } else if (needsInitiateRef.current) {
          needsInitiateRef.current = false;
          const activeId = conversationId;
          if (activeId) {
            // Reload conversation history first (it was empty because brain was down at startup)
            loadConversation(activeId).catch(() => {});
            api.initiate(activeId).then((init) => {
              if (init.hours_away > 4) setIsLongAway(true);
              if (init.text?.trim()) {
                const now = new Date().toISOString();
                lastElaraTextRef.current = init.text;
                setMessages((prev) => [
                  ...prev,
                  { id: genId(), role: "assistant", content: init.text, ts: now },
                ]);
                setMoodFromText(init.text);
                playTTSRef.current(init.text);
              }
            }).catch(() => { needsInitiateRef.current = true; setPollFast(true); });
          }
        } else {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", content: "*(connection restored — I'm back)*", ts: new Date().toISOString() },
          ]);
        }
      }
    } catch {
      prevHealthOkRef.current = false;
      setHealthOk(false);
    }
  }, [setHealthOk, setMessages, conversationId, setIsLongAway, setMoodFromText, loadConversation]);

  useEffect(() => {
    probeHealth();
    const interval = setInterval(probeHealth, pollFast ? 5000 : 30000);
    return () => clearInterval(interval);
  }, [probeHealth, pollFast]);

  const initializeConversation = useCallback(async () => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    try {
      const [convRes] = await Promise.all([api.listConversations(), refreshConversations()]);
      const convs = convRes.conversations || [];
      let activeId = conversationId;

      if (activeId) {
        try {
          await api.getConversation(activeId);
        } catch {
          activeId = null;
        }
      }

      if (!activeId) {
        if (convs.length > 0) {
          activeId = convs[0].id;
        } else {
          const created = await api.createConversation("New chat");
          activeId = created.conversation.id;
        }
      }

      if (activeId) {
        await setConversationId(activeId);
        await loadConversation(activeId);
        setConvReady(true);

        const notifMsg = pendingNotificationMessage;
        const initPromise = api.initiate(activeId);

        if (notifMsg?.trim()) {
          clearPendingNotificationMessage();
          // Still resolve initiate for its side effect (touch_last_seen / clear notification_pending)
          initPromise.then((init) => {
            if (init.hours_away > 4) setIsLongAway(true);
          }).catch(() => {});
          const now = new Date().toISOString();
          lastElaraTextRef.current = notifMsg;
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", content: notifMsg, ts: now },
          ]);
          setMoodFromText(notifMsg);
          playTTS(notifMsg);
        } else {
          initPromise.then((init) => {
            if (init.hours_away > 4) setIsLongAway(true);
            if (init.text?.trim()) {
              const now = new Date().toISOString();
              const initText = init.text;
              lastElaraTextRef.current = initText;
              setMessages((prev) => [
                ...prev,
                { id: genId(), role: "assistant", content: initText, ts: now },
              ]);
              setMoodFromText(initText);
              playTTS(initText);
            }
          }).catch(() => {
            needsInitiateRef.current = true;
            setPollFast(true);
          });
        }
      }
    } catch {
      needsInitiateRef.current = true;
      setPollFast(true);
      setConvReady(true);
    }
  }, [conversationId, loadConversation, refreshConversations, setConversationId, setIsLongAway, setMessages, setMoodFromText, pendingNotificationMessage, clearPendingNotificationMessage]);

  useEffect(() => {
    if (authed && initialized) {
      initializeConversation();
    }
  }, [authed, initialized, initializeConversation]);

  // Backgrounded-tap: inject notification message when app was already running
  // initializeConversation clears pendingNotificationMessage on fresh start, so
  // this only fires when pendingNotificationMessage is set after init (backgrounded taps).
  useEffect(() => {
    if (!pendingNotificationMessage?.trim() || !convReady) return;
    const msg = pendingNotificationMessage;
    clearPendingNotificationMessage();
    const now = new Date().toISOString();
    lastElaraTextRef.current = msg;
    setMessages((prev) => [
      ...prev,
      { id: genId(), role: "assistant", content: msg, ts: now },
    ]);
    setMoodFromText(msg);
    playTTSRef.current(msg).catch(() => {});
    // Fire initiate for side effect (touch_last_seen / clear notification_pending on backend)
    if (conversationId) {
      api.initiate(conversationId).then((init) => {
        if (init.hours_away > 4) setIsLongAway(true);
      }).catch(() => {});
    }
  }, [pendingNotificationMessage, convReady, clearPendingNotificationMessage, setMessages, setMoodFromText, setIsLongAway, conversationId]);

  const stopAudio = useCallback(async () => {
    if (soundRef.current) {
      await soundRef.current.stopAsync().catch(() => {});
      await soundRef.current.unloadAsync().catch(() => {});
      soundRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const playAudioUrl = useCallback(async (url: string) => {
    try {
      await stopAudio();
      const { sound } = await Audio.Sound.createAsync({ uri: url }, { volume: 1.0 });
      soundRef.current = sound;
      setIsPlaying(true);
      await sound.playAsync();
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          sound.unloadAsync().catch(() => {});
          if (soundRef.current === sound) {
            soundRef.current = null;
            setIsPlaying(false);
          }
        }
      });
    } catch {
      setIsPlaying(false);
    }
  }, [stopAudio]);

  const playTTS = useCallback(async (text: string) => {
    if (!voiceEnabled) return;
    if (!text || text.length < 3) return;
    try {
      const cached = ttsHashCache.current.get(text);
      let url: string;
      if (cached) {
        url = `${BACKEND_URL}/audio/${cached}.wav`;
      } else {
        const res = await api.requestTTS(text);
        ttsHashCache.current.set(text, res.hash);
        url = `${BACKEND_URL}${res.url}`;
      }
      await playAudioUrl(url);
    } catch {}
  }, [voiceEnabled, playAudioUrl]);

  const handleSpeakLast = useCallback(async () => {
    const text = lastElaraTextRef.current;
    if (!text || ttsLoading) return;
    setTtsLoading(true);
    try {
      const cached = ttsHashCache.current.get(text);
      let url: string;
      if (cached) {
        url = `${BACKEND_URL}/audio/${cached}.wav`;
      } else {
        const res = await api.requestTTS(text);
        ttsHashCache.current.set(text, res.hash);
        url = `${BACKEND_URL}${res.url}`;
      }
      await playAudioUrl(url);
    } catch {} finally {
      setTtsLoading(false);
    }
  }, [ttsLoading, playAudioUrl]);

  const streamSend = useCallback(async (msg: string, img: string | null, convId: string, isRetry = false) => {
    setIsStreaming(true);
    setShowTyping(true);

    let fullContent = "";
    let assistantId = "";
    let firstToken = true;

    const handleFailure = (reason: string) => {
      setShowTyping(false);
      if (!fullContent) {
        if (!isRetry) {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", content: "*(signal dropped — retrying…)*", ts: new Date().toISOString() },
          ]);
          setIsStreaming(false);
          setShowTyping(false);
          setTimeout(() => {
            streamSend(msg, img, convId, true);
          }, 2500);
        } else {
          pendingRetryRef.current = { msg, img, convId };
          setPollFast(true);
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", content: "*(connection dropped — watching for her…)*", ts: new Date().toISOString() },
          ]);
        }
      }
    };

    try {
      await api.streamChat(
        msg,
        convId,
        img,
        (token) => {
          fullContent += token;
          if (firstToken) {
            firstToken = false;
            setShowTyping(false);
            assistantId = genId();
            setMessages((prev) => [
              ...prev,
              { id: assistantId, role: "assistant", content: fullContent, ts: new Date().toISOString() },
            ]);
          } else {
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === assistantId);
              if (idx >= 0) updated[idx] = { ...updated[idx], content: fullContent };
              return updated;
            });
          }
        },
        (finalText, memorySuggestions) => {
          const segments = finalText
            .split(/\[BREAK\]/i)
            .map((s) => s.trim())
            .filter(Boolean);

          if (segments.length > 1) {
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === assistantId);
              if (idx >= 0) updated[idx] = { ...updated[idx], content: segments[0] };
              const extras: Message[] = segments.slice(1).map((seg) => ({
                id: genId(),
                role: "assistant",
                content: seg,
                ts: new Date().toISOString(),
              }));
              return [...updated, ...extras];
            });
          } else if (finalText.trim()) {
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex((m) => m.id === assistantId);
              if (idx >= 0) updated[idx] = { ...updated[idx], content: finalText.trim() };
              return updated;
            });
          }

          setMoodFromText(finalText);
          lastElaraTextRef.current = finalText;
          playTTS(finalText);
          refreshConversations();
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        },
        handleFailure,
      );
    } catch {
      handleFailure("Connection dropped");
      return;
    } finally {
      setIsStreaming(false);
      setShowTyping(false);
    }
  }, [setMessages, setMoodFromText, playTTS, refreshConversations]);

  useEffect(() => {
    streamSendRef.current = streamSend;
  }, [streamSend]);

  useEffect(() => {
    playTTSRef.current = playTTS;
  }, [playTTS]);

  const handleSend = useCallback(async () => {
    const msg = inputText.trim();
    const img = pendingImage;
    if (!msg && !img) return;
    if (isStreaming) return;

    let activeConvId = conversationId;
    if (!activeConvId) {
      try {
        const created = await api.createConversation("New chat");
        activeConvId = created.conversation.id;
        await setConversationId(activeConvId);
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: genId(), role: "assistant", content: "*(can't reach Elara right now — check connection)*", ts: new Date().toISOString() },
        ]);
        return;
      }
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (isLongAway) setIsLongAway(false);

    const now = new Date().toISOString();
    setMessages((prev) => [
      ...prev,
      { id: genId(), role: "user", content: msg || "(image)", ts: now },
    ]);
    setInputText("");
    setPendingImage(null);
    inputRef.current?.focus();

    await streamSend(msg, img, activeConvId, false);
  }, [
    inputText,
    pendingImage,
    isStreaming,
    conversationId,
    setConversationId,
    isLongAway,
    setIsLongAway,
    setMessages,
    streamSend,
  ]);

  const startPulse = useCallback(() => {
    pulseAnim.setValue(1);
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.5,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    pulseLoop.current = loop;
    loop.start();
  }, [pulseAnim]);

  const stopPulse = useCallback(() => {
    pulseLoop.current?.stop();
    pulseLoop.current = null;
    pulseAnim.setValue(1);
  }, [pulseAnim]);

  const startRecording = useCallback(async () => {
    if (isRecording || isTranscribing) return;

    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== "granted") {
        setMessages((prev) => [
          ...prev,
          {
            id: genId(),
            role: "assistant",
            content: "*(microphone access is needed to use voice input — please allow it in your device settings)*",
            ts: new Date().toISOString(),
          },
        ]);
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
      startPulse();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch {
      setIsRecording(false);
    }
  }, [isRecording, isTranscribing, startPulse, setMessages]);

  const stopRecordingAndTranscribe = useCallback(async () => {
    if (!isRecording || !recordingRef.current) return;

    const recording = recordingRef.current;
    recordingRef.current = null;
    setIsRecording(false);
    stopPulse();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    try {
      await recording.stopAndUnloadAsync();
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

      const uri = recording.getURI();
      if (!uri) return;

      setIsTranscribing(true);

      const base64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      const audioFmt = Platform.OS === "ios" ? "m4a" : "webm";
      const result = await api.transcribe(base64, audioFmt);

      setIsTranscribing(false);

      if (result.text) {
        setInputText(result.text);
        setTimeout(() => {
          inputRef.current?.focus();
        }, 100);
      }
    } catch {
      setIsTranscribing(false);
      setMessages((prev) => [
        ...prev,
        {
          id: genId(),
          role: "assistant",
          content: "*(couldn't transcribe that — try again)*",
          ts: new Date().toISOString(),
        },
      ]);
    }
  }, [isRecording, stopPulse, setMessages, setInputText]);

  const pickImage = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: "images",
      quality: 0.7,
      base64: true,
    });
    if (!result.canceled && result.assets[0]?.base64) {
      setPendingImage(result.assets[0].base64);
    }
  }, []);

  const handleSelectConversation = useCallback(
    async (id: string) => {
      await setConversationId(id);
      await loadConversation(id);
    },
    [setConversationId, loadConversation]
  );

  const handleNewConversation = useCallback(async () => {
    try {
      const res = await api.createConversation("New chat");
      const id = res.conversation.id;
      await setConversationId(id);
      setMessages([]);
      await refreshConversations();
      setDrawerOpen(false);
    } catch {}
  }, [setConversationId, setMessages, refreshConversations, setDrawerOpen]);

  const awayBg = awayTintAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(14,4,30,0.0)", "rgba(20,40,80,0.4)"],
  });

  const reversedMessages = [...messages].reverse();
  const topPadding = insets.top + (Platform.OS === "web" ? 67 : 0);

  return (
    <View style={styles.root}>
      {/* Mood-reactive background tint */}
      <Animated.View
        style={[StyleSheet.absoluteFill, { backgroundColor: moodColor, opacity: moodOpacity }]}
        pointerEvents="none"
      />
      {/* Away-state overlay */}
      <Animated.View
        style={[StyleSheet.absoluteFill, { backgroundColor: awayBg }]}
        pointerEvents="none"
      />

      <View style={[styles.header, { paddingTop: topPadding + 12 }]}>
        <Pressable
          onPress={() => setDrawerOpen(true)}
          style={({ pressed }) => [styles.headerBtn, pressed && { opacity: 0.6 }]}
          testID="open-drawer-btn"
        >
          <Text style={styles.iconText}>☰</Text>
        </Pressable>

        <Text style={styles.headerTitle}>e l a r a</Text>

        <HealthDot ok={healthOk} />
      </View>

      {isLongAway && (
        <View style={styles.awayBanner}>
          <Text style={styles.awayText}>been a while...</Text>
        </View>
      )}

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={0}
      >
        <View style={{ flex: 1 }}>
          <FlatList
            data={reversedMessages}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => <MessageBubble message={item} />}
            inverted={messages.length > 0}
            scrollEnabled={messages.length > 0}
            ListHeaderComponent={showTyping ? <TypingIndicator /> : null}
            keyboardDismissMode="interactive"
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.listContent}
            style={styles.list}
          />
          {messages.length === 0 && (
            <View style={styles.emptyOverlay} pointerEvents="none">
              {convReady ? (
                <>
                  <View style={[styles.emptyIcon, !healthOk && { backgroundColor: "rgba(180,60,60,0.25)" }]} />
                  <Text style={styles.emptyText}>
                    {healthOk ? "she's thinking of you" : "no signal right now…"}
                  </Text>
                </>
              ) : (
                <ActivityIndicator color="rgba(139,63,168,0.6)" />
              )}
            </View>
          )}
        </View>


        <View style={[styles.composer, { paddingBottom: insets.bottom + (Platform.OS === "web" ? 34 : 4) }]}>
          {pendingImage && (
            <View style={styles.imagePreview}>
              <Text style={styles.imagePreviewText}>image attached</Text>
              <Pressable onPress={() => setPendingImage(null)} hitSlop={8}>
                <Text style={[styles.iconText, { fontSize: 14, color: "rgba(144,128,168,0.7)" }]}>✕</Text>
              </Pressable>
            </View>
          )}
          <View style={styles.composerRow}>
            <Pressable
              onPress={pickImage}
              style={({ pressed }) => [styles.iconBtn, pressed && { opacity: 0.6 }]}
              testID="image-picker-btn"
            >
              <Text style={[styles.iconText, { fontSize: 18, color: "rgba(200,180,220,0.5)" }]}>⊞</Text>
            </Pressable>

            <TextInput
              ref={inputRef}
              style={styles.textInput}
              value={isTranscribing ? "" : inputText}
              onChangeText={setInputText}
              placeholder={isTranscribing ? "transcribing..." : isRecording ? "listening..." : "say something..."}
              placeholderTextColor={isRecording ? "rgba(180,100,220,0.7)" : isTranscribing ? "rgba(200,180,220,0.5)" : "rgba(144,128,168,0.35)"}
              multiline
              blurOnSubmit={false}
              editable={!isRecording && !isTranscribing}
              testID="chat-input"
            />

            <View style={styles.micContainer}>
              {isRecording && (
                <Animated.View
                  style={[
                    styles.pulseRing,
                    { transform: [{ scale: pulseAnim }], opacity: pulseAnim.interpolate({ inputRange: [1, 1.5], outputRange: [0.5, 0] }) },
                  ]}
                  pointerEvents="none"
                />
              )}
              <Pressable
                onPressIn={startRecording}
                onPressOut={stopRecordingAndTranscribe}
                disabled={isTranscribing || isStreaming}
                style={({ pressed }) => [
                  styles.micBtn,
                  isRecording && styles.micBtnActive,
                  (isTranscribing || isStreaming) && { opacity: 0.35 },
                  pressed && !isRecording && { opacity: 0.7 },
                ]}
                testID="mic-btn"
              >
                {isTranscribing ? (
                  <ActivityIndicator size="small" color="rgba(200,180,220,0.8)" />
                ) : (
                  <Text style={[styles.iconText, { fontSize: 17, color: isRecording ? "#E8D8FF" : "rgba(200,180,220,0.5)" }]}>
                    {isRecording ? "●" : "⏺"}
                  </Text>
                )}
              </Pressable>
            </View>

            {isPlaying ? (
              <Pressable
                onPress={stopAudio}
                style={({ pressed }) => [styles.iconBtn, pressed && { opacity: 0.6 }]}
                testID="stop-btn"
              >
                <Text style={[styles.iconText, { fontSize: 18, color: "rgba(200,140,140,0.7)" }]}>♪✕</Text>
              </Pressable>
            ) : (
              <Pressable
                onPress={handleSpeakLast}
                disabled={ttsLoading || !lastElaraTextRef.current}
                style={({ pressed }) => [
                  styles.iconBtn,
                  (ttsLoading || !lastElaraTextRef.current) && { opacity: 0.3 },
                  pressed && { opacity: 0.6 },
                ]}
                testID="speak-btn"
              >
                {ttsLoading ? (
                  <ActivityIndicator size="small" color="rgba(200,180,220,0.6)" />
                ) : (
                  <Text style={[styles.iconText, { fontSize: 18, color: "rgba(200,180,220,0.5)" }]}>♪</Text>
                )}
              </Pressable>
            )}

            <Pressable
              onPress={handleSend}
              disabled={isStreaming || (!inputText.trim() && !pendingImage)}
              style={({ pressed }) => [
                styles.sendBtn,
                (isStreaming || (!inputText.trim() && !pendingImage)) && { opacity: 0.4 },
                pressed && { opacity: 0.7 },
              ]}
              testID="send-btn"
            >
              {isStreaming ? (
                <ActivityIndicator size="small" color="#E8D8FF" />
              ) : (
                <Text style={[styles.iconText, { fontSize: 16, color: "#E8D8FF" }]}>↑</Text>
              )}
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>

      {drawerOpen && (
        <DrawerPanel
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#0E0418",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(139,63,168,0.1)",
    backgroundColor: "#0E0418",
    zIndex: 5,
  },
  headerBtn: {
    width: 36,
    height: 36,
    justifyContent: "center",
    alignItems: "center",
  },
  headerTitle: {
    color: "rgba(200,180,220,0.7)",
    fontSize: 14,
    letterSpacing: 6,
    fontFamily: "Inter_400Regular",
  },
  awayBanner: {
    alignItems: "center",
    paddingVertical: 6,
    backgroundColor: "rgba(20,40,80,0.3)",
  },
  awayText: {
    color: "rgba(160,180,220,0.6)",
    fontSize: 11,
    letterSpacing: 2,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingVertical: 12,
    paddingBottom: 20,
  },
  emptyOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  emptyIcon: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(139,63,168,0.3)",
  },
  emptyText: {
    color: "rgba(144,128,168,0.4)",
    fontSize: 12,
    letterSpacing: 1,
    fontStyle: "italic",
    fontFamily: "Inter_400Regular",
  },
  composer: {
    backgroundColor: "#0E0418",
    borderTopWidth: 1,
    borderTopColor: "rgba(139,63,168,0.12)",
    paddingHorizontal: 12,
    paddingTop: 8,
    gap: 8,
  },
  imagePreview: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 4,
  },
  imagePreviewText: {
    color: "rgba(200,180,220,0.6)",
    fontSize: 12,
    fontFamily: "Inter_400Regular",
  },
  composerRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },
  iconBtn: {
    width: 36,
    height: 36,
    justifyContent: "center",
    alignItems: "center",
    flexShrink: 0,
  },
  textInput: {
    flex: 1,
    backgroundColor: "rgba(26,11,46,0.9)",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    color: "#E8D8FF",
    fontSize: 15,
    fontFamily: "Inter_400Regular",
    maxHeight: 120,
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.2)",
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(139,63,168,0.7)",
    justifyContent: "center",
    alignItems: "center",
    flexShrink: 0,
  },
  iconText: {
    fontSize: 20,
    color: "rgba(200,180,220,0.8)",
    lineHeight: 22,
  },
  micContainer: {
    width: 36,
    height: 36,
    justifyContent: "center",
    alignItems: "center",
    flexShrink: 0,
    position: "relative",
  },
  micBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: "center",
    alignItems: "center",
  },
  micBtnActive: {
    backgroundColor: "rgba(139,63,168,0.4)",
  },
  pulseRing: {
    position: "absolute",
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: "rgba(139,63,168,0.8)",
    backgroundColor: "transparent",
  },
});
