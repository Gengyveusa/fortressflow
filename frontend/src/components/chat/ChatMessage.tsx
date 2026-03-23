"use client";

import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { ActionPreview } from "./ActionPreview";
import { ProgressTracker } from "./ProgressTracker";
import { MetricsCard } from "./MetricsCard";
import { QuestionCard } from "./QuestionCard";
import type {
  ChatMessageData,
  ActionPreviewData,
  ProgressData,
  MetricsData,
  QuestionData,
} from "./types";

// ── Markdown-bold helper ────────────────────────────────────────────────────

function parseMarkdownBold(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function renderTextContent(content: string) {
  const html = parseMarkdownBold(content);
  return (
    <span
      dangerouslySetInnerHTML={{ __html: html.replace(/\n/g, "<br/>") }}
    />
  );
}

// ── Streaming dots ──────────────────────────────────────────────────────────

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

// ── Main ChatMessage ────────────────────────────────────────────────────────

interface ChatMessageProps {
  message: ChatMessageData;
  onSendMessage: (text: string) => void;
}

export function ChatMessage({ message, onSendMessage }: ChatMessageProps) {
  const isUser = message.role === "user";
  const structured = message.structured;

  // Route structured content to the right renderer
  const renderStructured = () => {
    if (!structured?.data) return null;

    switch (structured.type) {
      case "action_preview":
        return (
          <ActionPreview
            data={structured.data as ActionPreviewData}
            onConfirm={() => onSendMessage("Confirm: launch campaign")}
            onModify={() => onSendMessage("Modify campaign settings")}
            onCancel={() => onSendMessage("Cancel campaign")}
          />
        );

      case "progress":
        return <ProgressTracker data={structured.data as ProgressData} />;

      case "metrics":
        return <MetricsCard data={structured.data as MetricsData} />;

      case "question":
        return (
          <QuestionCard
            data={structured.data as QuestionData}
            onAnswer={(answer) => onSendMessage(answer)}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div
      className={cn(
        "flex gap-2",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
          isUser
            ? "bg-blue-600 dark:bg-blue-500"
            : "bg-gray-200 dark:bg-gray-700"
        )}
      >
        {isUser ? (
          <User size={14} className="text-white" />
        ) : (
          <Bot size={14} className="text-gray-600 dark:text-gray-300" />
        )}
      </div>

      {/* Content */}
      <div className={cn("max-w-[85%] space-y-2", isUser && "flex flex-col items-end")}>
        {/* Text bubble */}
        {(message.content || message.isStreaming) && (
          <div
            className={cn(
              "rounded-2xl px-3 py-2 text-sm leading-relaxed",
              isUser
                ? "bg-blue-600 dark:bg-blue-500 text-white rounded-tr-sm"
                : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-tl-sm shadow-sm"
            )}
          >
            {message.content ? (
              renderTextContent(message.content)
            ) : message.isStreaming ? (
              <StreamingDots />
            ) : null}
            {message.isStreaming && message.content && <StreamingDots />}

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-gray-200 dark:border-gray-600 space-y-0.5">
                {message.sources.map((src, i) => (
                  <p key={i} className="text-xs text-gray-400 dark:text-gray-500">
                    {src}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Structured content (assistant only) */}
        {!isUser && structured && renderStructured()}

        {/* Timestamp */}
        <p
          className={cn(
            "text-xs px-1",
            isUser ? "text-gray-400" : "text-gray-400 dark:text-gray-500"
          )}
        >
          {format(message.timestamp, "h:mm a")}
        </p>
      </div>
    </div>
  );
}
