import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, type Message } from "@/lib/api";
import { useApp, genId, MOOD_COLORS } from "@/contexts/AppContext";
import { MessageBubble } from "@/components/MessageBubble";
import { TypingIndicator } from "@/components/TypingIndicator";
import { DrawerPanel } from "@/components/DrawerPanel";
import { HealthDot } from "@/components/HealthDot";

type RecordState = "idle" | "recording" | "processing";

export default function ChatPage() {
  const {
    conversationId,
    setConversationId,
    messages,
    setMessages,
    moodColor,
    moodVisible,
    setMoodFromText,
    isLongAway,
    setIsLongAway,
    drawerOpen,
    setDrawerOpen,
    voiceEnabled,
    loadConversation,
    initialized,
  } = useApp();

  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [recordState, setRecordState] = useState<RecordState>("idle");
  const [imageData, setImageData] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming, scrollToBottom]);

  const ensureConversation = useCallback(async (): Promise<string> => {
    if (conversationId) return conversationId;
    const res = await api.createConversation("new conversation");
    const id = res.conversation.id;
    setConversationId(id);
    return id;
  }, [conversationId, setConversationId]);

  const playTTS = useCallback(
    async (text: string) => {
      if (!voiceEnabled) return;
      try {
        const res = await api.requestTTS(text);
        if (!res.url) return;
        const audioUrl = res.url.startsWith("http") ? res.url : `/api${res.url}`;
        const response = await fetch(audioUrl);
        const arrayBuffer = await response.arrayBuffer();
        if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
          audioCtxRef.current = new AudioContext();
        }
        const ctx = audioCtxRef.current;
        if (ctx.state === "suspended") await ctx.resume();
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        source.start();
      } catch {}
    },
    [voiceEnabled],
  );

  useEffect(() => {
    if (!initialized) return;
    const init = async () => {
      let id = conversationId;
      if (!id) {
        try {
          const res = await api.createConversation("new conversation");
          id = res.conversation.id;
          setConversationId(id);
        } catch {
          return;
        }
      } else {
        loadConversation(id);
      }

      try {
        const res = await api.getConversation(id);
        const msgs = (res.conversation.messages as Message[] | undefined) || [];
        if (msgs.length === 0) {
          const aw = await api.initiate(id);
          if (aw.hours_away >= 4) setIsLongAway(true);
          const initMsg: Message = {
            id: genId(),
            role: "assistant",
            content: aw.text,
            ts: new Date().toISOString(),
          };
          setMessages([initMsg]);
          setMoodFromText(aw.text);
          if (voiceEnabled) playTTS(aw.text);
        }
      } catch {}
    };
    init();
  }, [initialized]);

  const sendMessage = useCallback(
    async (text: string, img: string | null = null) => {
      if (!text.trim() || streaming) return;

      const convId = await ensureConversation();
      const userMsg: Message = {
        id: genId(),
        role: "user",
        content: text.trim(),
        ts: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setImageData(null);
      setImagePreview(null);
      setStreaming(true);

      const streamId = genId();
      let accumulated = "";

      setMessages((prev) => [
        ...prev,
        { id: streamId, role: "assistant", content: "", ts: new Date().toISOString() },
      ]);

      await api.streamChat(
        text.trim(),
        convId,
        img,
        (token) => {
          accumulated += token;
          setMessages((prev) =>
            prev.map((m) => (m.id === streamId ? { ...m, content: accumulated } : m)),
          );
        },
        (fullText) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === streamId ? { ...m, content: fullText || accumulated } : m,
            ),
          );
          setStreaming(false);
          setMoodFromText(fullText || accumulated);
          if (voiceEnabled) playTTS(fullText || accumulated);
        },
        (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === streamId ? { ...m, content: err || "something went wrong" } : m,
            ),
          );
          setStreaming(false);
        },
      );
    },
    [streaming, ensureConversation, setMessages, setMoodFromText, playTTS, voiceEnabled],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) sendMessage(input, imageData);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) sendMessage(input, imageData);
    }
  };

  const handleImagePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      setImageData(base64);
      setImagePreview(result);
    };
    reader.readAsDataURL(file);
  };

  const startRecording = async () => {
    if (recordState !== "idle") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/ogg";
      const mr = new MediaRecorder(stream, { mimeType });
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecordState("processing");
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        const base64 = await blobToBase64(blob);
        const ext = mimeType.includes("ogg") ? "ogg" : "webm";
        try {
          const res = await api.transcribe(base64, ext);
          if (res.ok && res.text) {
            setInput(res.text);
            inputRef.current?.focus();
          }
        } catch {}
        setRecordState("idle");
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecordState("recording");
    } catch {}
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  const handleVoiceBtn = () => {
    if (recordState === "idle") startRecording();
    else if (recordState === "recording") stopRecording();
  };

  const handleNewConversation = useCallback(async () => {
    setMessages([]);
    try {
      const res = await api.createConversation("new conversation");
      const id = res.conversation.id;
      setConversationId(id);
      const aw = await api.initiate(id);
      const initMsg: Message = {
        id: genId(),
        role: "assistant",
        content: aw.text,
        ts: new Date().toISOString(),
      };
      setMessages([initMsg]);
      setMoodFromText(aw.text);
      if (voiceEnabled) playTTS(aw.text);
    } catch {}
  }, [setConversationId, setMessages, setMoodFromText, playTTS, voiceEnabled]);

  const handleSelectConversation = useCallback(
    async (id: string) => {
      setConversationId(id);
      await loadConversation(id);
    },
    [setConversationId, loadConversation],
  );

  return (
    <div
      className="flex flex-col h-full transition-colors duration-[3000ms] relative"
      style={{ backgroundColor: moodVisible ? moodColor : MOOD_COLORS.neutral }}
    >
      <div className="absolute inset-0 bg-[#0E0418] -z-10" />

      <header className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0 relative z-10 pt-safe">
        <div className="flex items-center gap-2">
          <HealthDot />
        </div>
        <span className="text-[14px] tracking-[6px] text-[rgba(200,180,220,0.45)] select-none">
          e l a r a
        </span>
        <button
          onClick={() => setDrawerOpen(true)}
          className="flex flex-col gap-1 p-2 active:opacity-50"
          aria-label="menu"
        >
          <div className="w-4 h-px bg-[rgba(144,128,168,0.6)]" />
          <div className="w-4 h-px bg-[rgba(144,128,168,0.6)]" />
          <div className="w-4 h-px bg-[rgba(144,128,168,0.6)]" />
        </button>
      </header>

      {isLongAway && messages.length <= 1 && (
        <div className="px-4 pb-2 shrink-0">
          <p className="text-[11px] italic text-[rgba(200,180,220,0.3)] text-center animate-mood">
            she's been thinking of you
          </p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col min-h-full justify-end py-2">
          {messages.length === 0 && !streaming && (
            <div className="flex items-center justify-center py-16">
              <div className="w-2 h-2 rounded-full bg-[rgba(139,63,168,0.3)]" />
            </div>
          )}
          {messages.map((msg) =>
            msg.content === "" && streaming ? (
              <TypingIndicator key={msg.id} />
            ) : (
              <MessageBubble key={msg.id} message={msg} />
            ),
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {imagePreview && (
        <div className="px-4 pb-2 shrink-0 flex items-center gap-2">
          <img
            src={imagePreview}
            alt=""
            className="w-12 h-12 rounded-lg object-cover border border-[rgba(139,63,168,0.3)]"
          />
          <button
            onClick={() => {
              setImageData(null);
              setImagePreview(null);
            }}
            className="text-[rgba(144,128,168,0.6)] text-sm active:opacity-50"
          >
            ✕
          </button>
        </div>
      )}

      <div className="px-3 pb-4 pt-2 shrink-0 relative z-10 pb-safe">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-10 h-10 rounded-full border border-[rgba(139,63,168,0.2)] flex items-center justify-center
              text-[rgba(144,128,168,0.6)] text-sm shrink-0 active:opacity-50 mb-0.5"
            aria-label="attach image"
          >
            ⊕
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleImagePick}
          />

          <div
            className="flex-1 bg-[rgba(26,11,46,0.9)] rounded-2xl border border-[rgba(139,63,168,0.2)]
            focus-within:border-[rgba(139,63,168,0.5)] transition-colors"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
              }}
              onKeyDown={handleKeyDown}
              disabled={streaming}
              placeholder="say something..."
              rows={1}
              className="w-full bg-transparent text-[#D8C8F0] text-[15px] px-4 py-2.5
                placeholder:text-[rgba(144,128,168,0.35)] outline-none resize-none leading-[22px]
                disabled:opacity-50"
              style={{ maxHeight: "140px" }}
            />
          </div>

          {input.trim() || imageData ? (
            <button
              type="submit"
              disabled={streaming}
              className="w-10 h-10 rounded-full bg-[rgba(139,63,168,0.3)] border border-[rgba(139,63,168,0.35)]
                flex items-center justify-center text-[rgba(200,180,220,0.8)] shrink-0 mb-0.5
                disabled:opacity-30 active:opacity-60"
            >
              ↑
            </button>
          ) : (
            <button
              type="button"
              onClick={handleVoiceBtn}
              disabled={recordState === "processing"}
              className={[
                "w-10 h-10 rounded-full border flex items-center justify-center shrink-0 mb-0.5 transition-colors duration-200",
                recordState === "recording"
                  ? "bg-[rgba(220,60,100,0.4)] border-[rgba(220,60,100,0.5)] animate-glow"
                  : recordState === "processing"
                    ? "bg-[rgba(139,63,168,0.15)] border-[rgba(139,63,168,0.2)]"
                    : "bg-[rgba(139,63,168,0.15)] border-[rgba(139,63,168,0.25)] active:opacity-60",
              ].join(" ")}
              aria-label="voice input"
            >
              {recordState === "processing" ? (
                <div className="w-3 h-3 rounded-full border-2 border-[rgba(139,63,168,0.5)] border-t-transparent animate-spin" />
              ) : (
                <span className="text-[rgba(144,128,168,0.7)] text-sm">
                  {recordState === "recording" ? "■" : "♪"}
                </span>
              )}
            </button>
          )}
        </form>
      </div>

      <DrawerPanel
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
    </div>
  );
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
