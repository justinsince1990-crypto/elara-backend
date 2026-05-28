import React, { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";

interface HealthDotProps {
  ok: boolean;
}

export function HealthDot({ ok }: HealthDotProps) {
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (ok) {
      const anim = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 0.4, duration: 1200, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1, duration: 1200, useNativeDriver: true }),
        ])
      );
      anim.start();
      return () => anim.stop();
    }
    pulse.setValue(1);
    return undefined;
  }, [ok, pulse]);

  return (
    <View style={styles.wrapper}>
      <Animated.View
        style={[
          styles.dot,
          {
            backgroundColor: ok ? "#3AE06A" : "#E03A3A",
            opacity: pulse,
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: 20,
    height: 20,
    justifyContent: "center",
    alignItems: "center",
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
});
