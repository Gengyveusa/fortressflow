"use client";

import { createContext, useContext, useState, useCallback } from "react";

type PanelMode = "closed" | "floating" | "expanded";

interface ChatPanelContextValue {
  mode: PanelMode;
  setMode: (mode: PanelMode) => void;
  open: (expanded?: boolean) => void;
  close: () => void;
  toggle: () => void;
  toggleExpand: () => void;
  hasInsights: boolean;
  setHasInsights: (val: boolean) => void;
  // Allow other components to inject a message
  pendingMessage: string | null;
  sendFromExternal: (msg: string) => void;
  clearPending: () => void;
}

const ChatPanelContext = createContext<ChatPanelContextValue>({
  mode: "closed",
  setMode: () => {},
  open: () => {},
  close: () => {},
  toggle: () => {},
  toggleExpand: () => {},
  hasInsights: false,
  setHasInsights: () => {},
  pendingMessage: null,
  sendFromExternal: () => {},
  clearPending: () => {},
});

export function useChatPanel() {
  return useContext(ChatPanelContext);
}

export function ChatPanelProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<PanelMode>("closed");
  const [hasInsights, setHasInsights] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  const open = useCallback((expanded?: boolean) => {
    setMode(expanded ? "expanded" : "floating");
  }, []);

  const close = useCallback(() => {
    setMode("closed");
  }, []);

  const toggle = useCallback(() => {
    setMode((prev) => (prev === "closed" ? "floating" : "closed"));
  }, []);

  const toggleExpand = useCallback(() => {
    setMode((prev) => {
      if (prev === "expanded") return "floating";
      return "expanded";
    });
  }, []);

  const sendFromExternal = useCallback((msg: string) => {
    setPendingMessage(msg);
    setMode("expanded");
  }, []);

  const clearPending = useCallback(() => {
    setPendingMessage(null);
  }, []);

  return (
    <ChatPanelContext.Provider
      value={{
        mode,
        setMode,
        open,
        close,
        toggle,
        toggleExpand,
        hasInsights,
        setHasInsights,
        pendingMessage,
        sendFromExternal,
        clearPending,
      }}
    >
      {children}
    </ChatPanelContext.Provider>
  );
}
