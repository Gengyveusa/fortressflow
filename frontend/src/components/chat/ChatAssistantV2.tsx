"use client";

import {
  useState,
  useRef,
  useEffect,
  useCallback,
  KeyboardEvent,
} from "react";
import {
  MessageCircle,
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Loader2,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChatMessage } from "./ChatMessage";
import { SlashMenu, QuickActions } from "./CommandBar";
import { useChatPanel } from "./ChatPanelContext";
import { SLASH_COMMANDS, PLACEHOLDER_EXAMPLES } from "./types";
import type { ChatMessageData, StructuredContent } from "./types";

// ── Helpers ─────────────────────────────────────────────────────────────────

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const LS_PROACTIVE_KEY = "fortressflow-chat-proactive-dismissed";
const PROACTIVE_MESSAGE =
  "Need help getting started? I can guide you through setup, warmup, sequences, and more. Try asking me anything or type /help!";

// ── Parse structured JSON from SSE ──────────────────────────────────────────

function tryParseStructured(text: string): StructuredContent | undefined {
  // Check if text contains a JSON block starting with ```json
  const jsonMatch = text.match(/```json\s*(\{[\s\S]*?\})\s*```/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[1]);
      if (parsed.type && parsed.data) {
        return parsed as StructuredContent;
      }
    } catch {
      // Not valid JSON
    }
  }
  // Also check if the whole text is JSON
  const trimmed = text.trim();
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed.type && parsed.data) {
        return parsed as StructuredContent;
      }
    } catch {
      // Not valid JSON
    }
  }
  return undefined;
}

function stripJsonBlock(text: string): string {
  return text.replace(/```json\s*\{[\s\S]*?\}\s*```/g, "").trim();
}

// ── Main Component ──────────────────────────────────────────────────────────

export function ChatAssistantV2() {
  const { mode, open, close, toggle, toggleExpand, pendingMessage, clearPending } = useChatPanel();

  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");
  const [showProactive, setShowProactive] = useState(false);
  const [proactiveShown, setProactiveShown] = useState(false);
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0);
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const isOpen = mode !== "closed";
  const isExpanded = mode === "expanded";

  // ── Rotating placeholder ──────────────────────────────────────────────

  useEffect(() => {
    const timer = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  // ── Init session ──────────────────────────────────────────────────────

  useEffect(() => {
    const initSession = async () => {
      try {
        const res = await fetch("/api/v1/chat/sessions");
        if (res.ok) {
          const data = await res.json();
          if (data.sessions?.length > 0) {
            const latest = data.sessions[0];
            setSessionId(latest.session_id);
            await loadSessionMessages(latest.session_id);
            return;
          }
        }
      } catch {
        // Backend unavailable
      }

      try {
        const res = await fetch("/api/v1/chat/sessions", { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          setSessionId(data.session_id);
          return;
        }
      } catch {
        // fallback
      }
      setSessionId(generateId());
    };

    initSession();

    const dismissed = localStorage.getItem(LS_PROACTIVE_KEY);
    if (!dismissed) {
      const timer = setTimeout(() => {
        setShowProactive(true);
        setProactiveShown(true);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, []);

  // ── Load messages ─────────────────────────────────────────────────────

  const loadSessionMessages = async (sid: string) => {
    try {
      const res = await fetch(`/api/v1/chat/sessions/${sid}`);
      if (res.ok) {
        const data = await res.json();
        if (data.messages?.length > 0) {
          const loaded: ChatMessageData[] = data.messages.map(
            (m: { id: string; role: string; content: string; timestamp: string; sources?: string[] }) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              structured: tryParseStructured(m.content),
              timestamp: new Date(m.timestamp),
              sources: m.sources || [],
            })
          );
          setMessages(loaded);
        }
      }
    } catch {
      // Silently handle
    }
  };

  // ── Handle pending messages from external (nav, insights) ─────────────

  useEffect(() => {
    if (pendingMessage && isOpen && !isStreaming) {
      setInputValue(pendingMessage);
      clearPending();
      // Auto-send after a short delay
      const timer = setTimeout(() => {
        sendMessageDirect(pendingMessage);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [pendingMessage, isOpen, isStreaming]);

  // ── Auto-scroll ───────────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Focus input ───────────────────────────────────────────────────────

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // ── Keyboard shortcut: Cmd+J to toggle ────────────────────────────────

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        close();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "j") {
        e.preventDefault();
        if (!isOpen) {
          open(true);
        } else {
          toggleExpand();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, close, open, toggleExpand]);

  // ── Dismiss proactive ─────────────────────────────────────────────────

  const handleOpen = useCallback(() => {
    open();
    setShowProactive(false);
    if (proactiveShown) {
      localStorage.setItem(LS_PROACTIVE_KEY, "1");
    }
  }, [open, proactiveShown]);

  // ── Input handling ────────────────────────────────────────────────────

  const filteredCommands = SLASH_COMMANDS.filter((c) =>
    c.command.toLowerCase().startsWith(slashFilter.toLowerCase())
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInputValue(val);

    if (val.startsWith("/")) {
      setShowSlashMenu(true);
      setSlashFilter(val);
      setSelectedSlashIndex(0);
    } else {
      setShowSlashMenu(false);
      setSlashFilter("");
    }

    const ta = e.target;
    ta.style.height = "auto";
    const maxHeight = 24 * 3 + 16;
    ta.style.height = Math.min(ta.scrollHeight, maxHeight) + "px";
  };

  const selectSlashCommand = (cmd: string) => {
    setInputValue(cmd + " ");
    setShowSlashMenu(false);
    inputRef.current?.focus();
  };

  // ── Send message ──────────────────────────────────────────────────────

  const sendMessageDirect = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setInputValue("");
      setShowSlashMenu(false);
      if (inputRef.current) inputRef.current.style.height = "auto";

      const userMsg: ChatMessageData = {
        id: generateId(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      const assistantId = generateId();
      const assistantMsg: ChatMessageData = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      try {
        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch("/api/v1/chat/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed, session_id: sessionId }),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            if (trimmedLine.startsWith("data: ")) {
              const data = trimmedLine.slice(6);

              if (data === "[DONE]") {
                const structured = tryParseStructured(accumulated);
                const displayContent = structured ? stripJsonBlock(accumulated) : accumulated;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: displayContent, structured, isStreaming: false }
                      : m
                  )
                );
                setIsStreaming(false);
                return;
              }

              if (data === "[ERROR]") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          content: accumulated || "Sorry, an error occurred. Please try again.",
                          isStreaming: false,
                        }
                      : m
                  )
                );
                setIsStreaming(false);
                return;
              }

              accumulated += data;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: accumulated, isStreaming: true }
                    : m
                )
              );
            }
          }
        }

        if (buffer.trim().startsWith("data: ")) {
          const data = buffer.trim().slice(6);
          if (data !== "[DONE]" && data !== "[ERROR]") {
            accumulated += data;
          }
        }

        const structured = tryParseStructured(accumulated);
        const displayContent = structured ? stripJsonBlock(accumulated) : accumulated;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: displayContent, structured, isStreaming: false }
              : m
          )
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: "Sorry, I couldn't connect to the assistant. Please check your connection and try again.",
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, sessionId]
  );

  const sendMessage = useCallback(() => {
    sendMessageDirect(inputValue);
  }, [inputValue, sendMessageDirect]);

  const handleSendFromChild = useCallback(
    (text: string) => {
      sendMessageDirect(text);
    },
    [sendMessageDirect]
  );

  // ── Quick action handler ──────────────────────────────────────────────

  const handleQuickAction = useCallback(
    (msg: string) => {
      if (msg.startsWith("/")) {
        setInputValue(msg + " ");
        inputRef.current?.focus();
      } else {
        sendMessageDirect(msg);
      }
    },
    [sendMessageDirect]
  );

  // ── Keyboard ──────────────────────────────────────────────────────────

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashMenu) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedSlashIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedSlashIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        if (filteredCommands[selectedSlashIndex]) {
          selectSlashCommand(filteredCommands[selectedSlashIndex].command);
        }
        return;
      }
      if (e.key === "Escape") {
        setShowSlashMenu(false);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <>
      {/* Floating button — hidden when expanded */}
      {!isExpanded && (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
          {showProactive && !isOpen && (
            <div
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl px-4 py-3 max-w-[260px] text-sm text-gray-700 dark:text-gray-200 cursor-pointer animate-in slide-in-from-bottom-2 fade-in mb-1"
              onClick={handleOpen}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && handleOpen()}
            >
              <button
                className="float-right ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowProactive(false);
                  localStorage.setItem(LS_PROACTIVE_KEY, "1");
                }}
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
              {PROACTIVE_MESSAGE}
            </div>
          )}

          <Button
            onClick={isOpen ? () => close() : handleOpen}
            className={cn(
              "w-14 h-14 rounded-full shadow-lg relative",
              "bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",
              "text-white transition-all duration-200"
            )}
            aria-label={isOpen ? "Close chat assistant" : "Open chat assistant"}
          >
            {isOpen ? (
              <X size={24} />
            ) : (
              <>
                <MessageCircle size={24} />
                {showProactive && (
                  <span className="absolute top-1 right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white dark:border-gray-900" />
                )}
              </>
            )}
          </Button>
        </div>
      )}

      {/* Chat Panel */}
      <div
        role="dialog"
        aria-label="FortressFlow Chat Assistant"
        aria-modal={isExpanded}
        className={cn(
          "fixed z-40 flex flex-col",
          "bg-white dark:bg-gray-900",
          "border border-gray-200 dark:border-gray-700",
          "shadow-2xl overflow-hidden",
          "transition-all duration-300 ease-in-out",

          // Expanded mode — right panel
          isExpanded && [
            "top-0 right-0 bottom-0",
            "w-full sm:w-[480px] lg:w-[520px]",
            "rounded-none border-l",
          ],

          // Floating mode
          !isExpanded && [
            "sm:bottom-24 sm:right-6 sm:w-96 sm:h-[520px] sm:rounded-2xl",
            "bottom-0 right-0 w-full h-full sm:h-auto",
          ],

          // Visibility
          isOpen
            ? "opacity-100 translate-x-0 pointer-events-auto"
            : "opacity-0 translate-x-4 pointer-events-none"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-blue-500 dark:bg-blue-600 flex items-center justify-center flex-shrink-0">
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm leading-tight">
                FortressFlow Assistant
              </p>
              <p className="text-blue-200 text-xs">
                {isStreaming ? "Typing..." : "Online"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggleExpand}
              className="text-blue-200 hover:text-white transition-colors rounded-lg p-1.5"
              aria-label={isExpanded ? "Minimize chat" : "Expand chat"}
              title={`${isExpanded ? "Minimize" : "Expand"} (Cmd+J)`}
            >
              {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
            <button
              onClick={() => close()}
              className="text-blue-200 hover:text-white transition-colors rounded-lg p-1.5"
              aria-label="Close chat"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 bg-gray-50 dark:bg-gray-950 min-h-0">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-8">
              <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <Bot size={24} className="text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-gray-700 dark:text-gray-300 font-medium text-sm">
                  How can I help you today?
                </p>
                <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">
                  Ask me about campaigns, leads, deliverability, or type{" "}
                  <code className="bg-gray-200 dark:bg-gray-800 px-1 rounded text-xs">/</code>{" "}
                  for commands
                </p>
              </div>

              {/* Quick action chips in empty state */}
              <div className="flex flex-wrap justify-center gap-1.5 mt-2">
                <QuickActions onAction={handleQuickAction} />
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onSendMessage={handleSendFromChild}
            />
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Slash command autocomplete */}
        {showSlashMenu && (
          <SlashMenu
            filter={slashFilter}
            selectedIndex={selectedSlashIndex}
            onSelect={selectSlashCommand}
            onHover={setSelectedSlashIndex}
          />
        )}

        {/* Quick actions (when messages exist) */}
        {messages.length > 0 && !isStreaming && (
          <QuickActions onAction={handleQuickAction} />
        )}

        {/* Input area */}
        <div className="px-3 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex-shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={PLACEHOLDER_EXAMPLES[placeholderIndex]}
              disabled={isStreaming}
              rows={1}
              className={cn(
                "flex-1 resize-none rounded-xl border border-gray-200 dark:border-gray-700",
                "bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                "px-3 py-2 text-sm leading-6",
                "placeholder-gray-400 dark:placeholder-gray-500",
                "focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-colors overflow-hidden"
              )}
              style={{ minHeight: "40px", maxHeight: "88px" }}
              aria-label="Chat message input"
            />
            <Button
              onClick={sendMessage}
              disabled={!inputValue.trim() || isStreaming}
              className={cn(
                "w-9 h-9 rounded-xl p-0 flex-shrink-0",
                "bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",
                "text-white disabled:opacity-50"
              )}
              aria-label="Send message"
            >
              {isStreaming ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </Button>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-600 mt-1 pl-1">
            Enter to send · Shift+Enter for newline · Cmd+J to {isExpanded ? "minimize" : "expand"}
          </p>
        </div>
      </div>
    </>
  );
}
