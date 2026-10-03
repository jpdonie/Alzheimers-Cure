"use client";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

export function VoiceProvider({ children }: { children: ReactNode }) {
  return <ConversationProvider>{children}</ConversationProvider>;
}

let activeRole: "interviewer" | "tutor" | null = null;   // the provider keeps one live conversation across pages

type Opts = { role: "interviewer" | "tutor"; onUserMessage?: (text: string) => void };

/** ElevenAgents adapter. The engine decides what to say; the agent only voices it. Captions/typed answers are the fallback. */
export function useVoiceAgent({ role, onUserMessage }: Opts) {
  const lastVoice = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const conv = useConversation({
    onMessage: (m) => { if (m.source === "user" && m.message) { lastVoice.current = Date.now(); onUserMessage?.(m.message); } },
    onVadScore: ({ vadScore }) => { if (vadScore > 0.45) lastVoice.current = Date.now(); },
    onError: (msg) => setError(String(msg)),
  });
  const live = conv.status === "connected";
  const connected = live && activeRole === role;
  useEffect(() => { if (live && activeRole !== role) conv.endSession(); }, [live, role]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = useCallback(async () => {
    setError(null);
    try {
      const r = await fetch(`/api/voice?role=${role}`);
      const j = await r.json();
      if (!j.signedUrl) throw new Error(j.error ?? "no signed url");
      await navigator.mediaDevices.getUserMedia({ audio: true });
      activeRole = role;
      conv.startSession({ signedUrl: j.signedUrl });
    } catch (e) {
      setError(e instanceof Error ? e.message : "voice unavailable");
    }
  }, [conv, role]);

  /** ms since the person last spoke (0 while the agent itself is talking). */
  const silentFor = useCallback(() => (conv.isSpeaking ? 0 : Date.now() - lastVoice.current), [conv.isSpeaking]);
  const tell = useCallback((tag: "ASK" | "SAY" | "TEACHBACK", text: string) => { if (connected) conv.sendUserMessage(`[${tag}] ${text}`); }, [conv, connected]);
  const context = useCallback((text: string) => { if (connected) conv.sendContextualUpdate(`[CONTEXT] ${text}`); }, [conv, connected]);

  return { start, stop: conv.endSession, connected, speaking: conv.isSpeaking, silentFor, tell, context, error, status: conv.status };
}
