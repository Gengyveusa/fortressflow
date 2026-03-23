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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { getSession } from "next-auth/react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  sources?: string[];
  isStreaming?: boolean;
}

interface SlashCommand {
  command: string;
  description: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SLASH_COMMANDS: SlashCommand[] = [
  { command: "/status", description: "System status overview" },
  { command: "/help", description: "Available commands and help" },
  { command: "/warmup", description: "Warmup status and next steps" },
  { command: "/sequences", description: "Active sequence summary" },
  { command: "/compliance", description: "Compliance checklist" },
  { command: "/leads", description: "Lead import status" },
  { command: "/deliverability", description: "Deliverability health" },
];

const PROACTIVE_MESSAGE =
  "👋 Need help getting started? I can guide you through setup, warmup, sequences, and more. Try asking me anything or type /help!";

const LS_PROACTIVE_KEY = "fortressflow-chat-proactive-dismissed";

// ── Helpers ───────────────────────────────────────────────────────────────────

async function getAuthHeaders(): Promise<Record<string, string>> {
  const session = await getSession() as { accessToken?: string } | null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (session?.accessToken) {
    headers["Authorization"] = `Bearer ${session.accessToken}`;
  }
  return headers;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function parseMarkdownBold(text: string): string {
  // Convert **text** to <strong>text</strong>
  return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function renderContent(content: string) {
  const html = parseMarkdownBold(content);
  return (
    <span
      dangerouslySetInnerHTML={{ __html: html.replace(/\n/g, "<br/>") }}
    />
  );
}

// ── Streaming dots animation ──────────────────────────────────────────────────

function StreamingDots() {
  return (
    <span className="inline-flex items-center gap-0.5 ml-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.9s" }}
        />
      ))}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ChatAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");
  const [showProactive, setShowProactive] = useState(false);
  const [proactiveShown, setProactiveShown] = useState(false);
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Init session from backend ─────────────────────────────────────────

  useEffect(() => {
    const initSession = async () => {
      const headers = await getAuthHeaders();
      // Try to load sessions from backend
      try {
        const res = await fetch("/api/v1/chat/sessions", { headers });
        if (res.ok) {
          const data = await res.json();
          if (data.sessions && data.sessions.length > 0) {
            // Resume most recent session
            const latest = data.sessions[0];
            setSessionId(latest.session_id);
            // Load messages for this session
            await loadSessionMessages(latest.session_id);
            return;
          }
        }
      } catch {
        // Backend unavailable — create local session
      }

      // Create a new session
      try {
        const res = await fetch("/api/v1/chat/sessions", { method: "POST", headers });
        if (res.ok) {
          const data = await res.json();
          setSessionId(data.session_id);
          return;
        }
      } catch {
        // Fallback to local session ID
      }
      setSessionId(generateId());
    };

    initSession();

    // Proactive message timer
    const dismissed = localStorage.getItem(LS_PROACTIVE_KEY);
    if (!dismissed) {
      const timer = setTimeout(() => {
        setShowProactive(true);
        setProactiveShown(true);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, []);

  // ── Load messages from backend ────────────────────────────────────────

  const loadSessionMessages = async (sid: string) => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`/api/v1/chat/sessions/${sid}`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
          const loaded: ChatMessage[] = data.messages.map((m: { id: string; role: string; content: string; timestamp: string; sources?: string[] }) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content,
            timestamp: new Date(m.timestamp),
            sources: m.sources || [],
          }));
          setMessages(loaded);
        }
      }
    } catch {
      // Silently handle — show empty chat
    }
  };

  // ── Auto-scroll to bottom ────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Focus input when panel opens ─────────────────────────────────────────

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // ── Escape key listener ──────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen]);

  // ── Dismiss proactive on open ────────────────────────────────────────────

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    setShowProactive(false);
    if (proactiveShown) {
      localStorage.setItem(LS_PROACTIVE_KEY, "1");
    }
  }, [proactiveShown]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    abortRef.current?.abort();
  }, []);

  // ── Slash command menu ───────────────────────────────────────────────────

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

    // Auto-resize textarea
    const ta = e.target;
    ta.style.height = "auto";
    const lineHeight = 24;
    const maxHeight = lineHeight * 3 + 16; // 3 lines + padding
    ta.style.height = Math.min(ta.scrollHeight, maxHeight) + "px";
  };

  const selectSlashCommand = (cmd: string) => {
    setInputValue(cmd + " ");
    setShowSlashMenu(false);
    inputRef.current?.focus();
  };

  // ── Send message ─────────────────────────────────────────────────────────

  const sendMessage = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || isStreaming) return;

    setInputValue("");
    setShowSlashMenu(false);
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    // Add user message
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    // Add placeholder assistant message
    const assistantId = generateId();
    const assistantMsg: ChatMessage = {
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

      const headers = await getAuthHeaders();
      const response = await fetch("/api/v1/chat/", {
        method: "POST",
        headers,
        body: JSON.stringify({ message: text, session_id: sessionId }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

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
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("data: ")) {
            const data = trimmed.slice(6);

            if (data === "[DONE]") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: accumulated, isStreaming: false }
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
                        content:
                          accumulated ||
                          "Sorry, an error occurred. Please try again.",
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

      // Handle any remaining buffer
      if (buffer.trim().startsWith("data: ")) {
        const data = buffer.trim().slice(6);
        if (data !== "[DONE]" && data !== "[ERROR]") {
          accumulated += data;
        }
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: accumulated, isStreaming: false }
            : m
        )
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
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
  }, [inputValue, isStreaming, sessionId]);

  // ── Keyboard handlers ────────────────────────────────────────────────────

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashMenu) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedSlashIndex((i) =>
          Math.min(i + 1, filteredCommands.length - 1)
        );
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

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Floating button */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
        {/* Proactive tooltip */}
        {showProactive && !isOpen && (
          <div
            className="
              bg-white dark:bg-gray-800
              border border-gray-200 dark:border-gray-700
              rounded-2xl shadow-xl px-4 py-3 max-w-xs
              text-sm text-gray-700 dark:text-gray-200
              animate-in slide-in-from-bottom-2 fade-in
              cursor-pointer
            "
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
          onClick={isOpen ? handleClose : handleOpen}
          className={cn(
            "w-14 h-14 rounded-full shadow-lg relative",
            "bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",
            "text-white transition-all duration-200",
            "focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
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

      {/* Chat panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-label="FortressFlow Chat Assistant"
        aria-modal="true"
        className={cn(
          "fixed z-40",
          // Desktop positioning
          "sm:bottom-24 sm:right-6 sm:w-96 sm:h-[560px] sm:rounded-2xl",
          // Mobile: full screen
          "bottom-0 right-0 w-full h-full sm:h-auto",
          "flex flex-col",
          "bg-white dark:bg-gray-900",
          "border border-gray-200 dark:border-gray-700",
          "shadow-2xl",
          "overflow-hidden",
          // Animation
          "transition-all duration-300 ease-in-out",
          isOpen
            ? "opacity-100 translate-y-0 pointer-events-auto"
            : "opacity-0 translate-y-4 pointer-events-none"
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
          <button
            onClick={handleClose}
            className="text-blue-200 hover:text-white transition-colors rounded-lg p-1 focus:outline-none focus:ring-2 focus:ring-blue-300"
            aria-label="Close chat"
          >
            <X size={20} />
          </button>
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
                  Ask me about sequences, warmup, deliverability, or type{" "}
                  <code className="bg-gray-200 dark:bg-gray-800 px-1 rounded text-xs">
                    /help
                  </code>
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex gap-2",
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              {/* Avatar */}
              <div
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                  msg.role === "user"
                    ? "bg-blue-600 dark:bg-blue-500"
                    : "bg-gray-200 dark:bg-gray-700"
                )}
              >
                {msg.role === "user" ? (
                  <User size={14} className="text-white" />
                ) : (
                  <Bot
                    size={14}
                    className="text-gray-600 dark:text-gray-300"
                  />
                )}
              </div>

              {/* Bubble */}
              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-blue-600 dark:bg-blue-500 text-white rounded-tr-sm"
                    : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-tl-sm shadow-sm"
                )}
              >
                {msg.content ? (
                  renderContent(msg.content)
                ) : msg.isStreaming ? (
                  <StreamingDots />
                ) : null}
                {msg.isStreaming && msg.content && <StreamingDots />}

                {/* Sources */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-1.5 pt-1.5 border-t border-gray-200 dark:border-gray-600 space-y-0.5">
                    {msg.sources.map((src, i) => (
                      <p
                        key={i}
                        className="text-xs text-gray-400 dark:text-gray-500"
                      >
                        • {src}
                      </p>
                    ))}
                  </div>
                )}

                {/* Timestamp */}
                <p
                  className={cn(
                    "text-xs mt-1",
                    msg.role === "user"
                      ? "text-blue-200"
                      : "text-gray-400 dark:text-gray-500"
                  )}
                >
                  {format(msg.timestamp, "h:mm a")}
                </p>
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Slash command autocomplete */}
        {showSlashMenu && filteredCommands.length > 0 && (
          <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 max-h-48 overflow-y-auto flex-shrink-0">
            {filteredCommands.map((cmd, i) => (
              <button
                key={cmd.command}
                className={cn(
                  "w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors",
                  i === selectedSlashIndex &&
                    "bg-blue-50 dark:bg-blue-900/20"
                )}
                onClick={() => selectSlashCommand(cmd.command)}
                onMouseEnter={() => setSelectedSlashIndex(i)}
              >
                <code className="text-blue-600 dark:text-blue-400 text-xs font-mono font-semibold mt-0.5 flex-shrink-0">
                  {cmd.command}
                </code>
                <span className="text-gray-500 dark:text-gray-400 text-xs">
                  {cmd.description}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="px-3 py-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 flex-shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything or type / for commands…"
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
              aria-multiline="true"
            />
            <Button
              onClick={sendMessage}
              disabled={!inputValue.trim() || isStreaming}
              className={cn(
                "w-9 h-9 rounded-xl p-0 flex-shrink-0",
                "bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600",
                "text-white disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-colors"
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
            Enter to send · Shift+Enter for newline
          </p>
        </div>
      </div>
    </>
  );
}
