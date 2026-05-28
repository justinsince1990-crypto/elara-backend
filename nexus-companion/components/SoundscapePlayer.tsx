import React, { useEffect, useRef, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Audio } from "expo-av";
import { storage } from "@/lib/storage";
import { useApp } from "@/contexts/AppContext";

const SCENES = [
  { id: "off", label: "OFF" },
  { id: "rain", label: "RAIN" },
  { id: "fire", label: "FIREPLACE" },
  { id: "forest", label: "FOREST" },
  { id: "city", label: "CITY" },
  { id: "space", label: "SPACE" },
] as const;

type SceneId = (typeof SCENES)[number]["id"];

const SCENE_COLORS: Record<SceneId, string> = {
  off: "rgba(80,60,100,0.5)",
  rain: "rgba(40,80,140,0.7)",
  fire: "rgba(140,40,20,0.7)",
  forest: "rgba(40,100,50,0.7)",
  city: "rgba(80,80,100,0.7)",
  space: "rgba(20,20,80,0.7)",
};

interface SoundscapePlayerProps {
  onSceneChange?: (scene: string) => void;
}

export function SoundscapePlayer({ onSceneChange }: SoundscapePlayerProps) {
  const [activeScene, setActiveScene] = useState<SceneId>("off");
  const soundRef = useRef<Audio.Sound | null>(null);
  const { autoSoundscape, setSoundscapeManualOverride } = useApp();

  useEffect(() => {
    (async () => {
      const saved = (await storage.getSoundscape()) as SceneId;
      setActiveScene(saved);
    })();

    return () => {
      soundRef.current?.unloadAsync().catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (autoSoundscape !== null) {
      const scene = autoSoundscape as SceneId;
      playScene(scene, false);
    }
  }, [autoSoundscape]);

  const stopSound = async () => {
    if (soundRef.current) {
      try {
        await soundRef.current.stopAsync();
        await soundRef.current.unloadAsync();
      } catch {}
      soundRef.current = null;
    }
  };

  const playScene = async (scene: SceneId, isManual = true) => {
    if (isManual) {
      setSoundscapeManualOverride(true);
    }

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      shouldDuckAndroid: true,
    });
    await stopSound();
    setActiveScene(scene);
    await storage.setSoundscape(scene);
    onSceneChange?.(scene);

    if (scene === "off") return;

    const sceneUrls: Record<Exclude<SceneId, "off">, string> = {
      rain: "https://cdn.pixabay.com/audio/2022/05/27/audio_1808fbf07a.mp3",
      fire: "https://cdn.pixabay.com/audio/2022/10/30/audio_946c8e5b1a.mp3",
      forest: "https://cdn.pixabay.com/audio/2022/03/10/audio_a4dd24b5f5.mp3",
      city: "https://cdn.pixabay.com/audio/2022/09/09/audio_8e1c2ef8d8.mp3",
      space: "https://cdn.pixabay.com/audio/2024/02/14/audio_5e2f7b9b11.mp3",
    };

    try {
      const url = sceneUrls[scene as Exclude<SceneId, "off">];
      if (!url) return;
      const { sound } = await Audio.Sound.createAsync(
        { uri: url },
        { isLooping: true, volume: 0.25 }
      );
      soundRef.current = sound;
      await sound.playAsync();
    } catch {}
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>SOUNDSCAPE</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {SCENES.map((scene) => {
          const active = activeScene === scene.id;
          return (
            <Pressable
              key={scene.id}
              onPress={() => playScene(scene.id as SceneId, true)}
              style={({ pressed }) => [
                styles.sceneBtn,
                active && { backgroundColor: SCENE_COLORS[scene.id as SceneId], borderColor: "rgba(139,63,168,0.8)" },
                pressed && styles.pressed,
              ]}
              testID={`scene-${scene.id}`}
            >
              <Text style={[styles.sceneTxt, active && styles.sceneTxtActive]}>
                {scene.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 10,
    paddingVertical: 4,
  },
  label: {
    color: "rgba(144,128,168,0.7)",
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "Inter_600SemiBold",
  },
  row: {
    flexDirection: "row",
    gap: 8,
    paddingRight: 8,
  },
  sceneBtn: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(139,63,168,0.2)",
    backgroundColor: "rgba(26,11,46,0.8)",
  },
  sceneTxt: {
    color: "rgba(200,180,220,0.6)",
    fontSize: 11,
    letterSpacing: 1.5,
    fontFamily: "Inter_600SemiBold",
  },
  sceneTxtActive: {
    color: "#E8D8FF",
  },
  pressed: {
    opacity: 0.7,
  },
});
