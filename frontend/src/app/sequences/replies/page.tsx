"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Inbox,
  Mail,
  MessageSquare,
  Linkedin,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Bot,
  ChevronDown,
  ChevronRight,
  Filter,
  RefreshCw,
  ArrowRight,
  Send,
  AlertTriangle,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { sequencesApi, type ReplyLog } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "…";
}

// ── Channel Icon ─────────────────────────────────────────────────────────────

function ChannelIcon({ channel, className }: { channel: string; className?: string }) {
  switch (channel.toLowerCase()) {
    case "email":
      return <Mail className={className} />;
    case "sms":
      return <MessageSquare className={className} />;
    case "linkedin":
      return <Linkedin className={className} />;
    default:
      return <Send className={className} />;
  }
}

// ── Sentiment Styles ─────────────────────────────────────────────────────────

const SENTIMENT_BADGE: Record<string, string> = {
  positive: "bg-green-100 text-green-700",
  negative: "bg-red-100 text-red-700",
  neutral: "bg-gray-100 text-gray-600",
};

const SENTIMENT_DOT: Record<string, string> = {
  positive: "bg-green-500",
  negative: "bg-red-500",
  neutral: "bg-gray-400",
};

function SentimentIcon({ sentiment }: { sentiment: string | null }) {
  switch (sentiment?.toLowerCase()) {
    case "positive":
      return <ThumbsUp className="h-3.5 w-3.5 text-green-600" />;
    case "negative":
      return <ThumbsDown className="h-3.5 w-3.5 text-red-500" />;
    default:
      return <Minus className="h-3.5 w-3.5 text-gray-400" />;
  }
}

// ── AI Action Badge ──────────────────────────────────────────────────────────

const ACTION_COLORS: Record<string, string> = {
  reply: "bg-blue-100 text-blue-700",
  escalate: "bg-amber-100 text-amber-700",
  unsubscribe: "bg-red-100 text-red-600",
  nurture: "bg-purple-100 text-purple-700",
  close: "bg-emerald-100 text-emerald-700",
  follow_up: "bg-sky-100 text-sky-700",
};

function AIActionBadge({ action }: { action: string | null }) {
  if (!action) return null;
  const normalized = action.toLowerCase().replace(/\s+/g, "_");
  const colorClass = ACTION_COLORS[normalized] ?? "bg-gray-100 text-gray-600";
  return (
    <Badge className={`text-xs ${colorClass} flex items-center gap-1`}>
      <Bot className="h-3 w-3" />
      {action}
    </Badge>
  );
}

// ── Reply Card ────────────────────────────────────────────────────────────────

function ReplyCard({ reply }: { reply: ReplyLog }) {
  const [expanded, setExpanded] = useState(false);
  const sentiment = reply.sentiment?.toLowerCase() ?? "neutral";
  const dotColor = SENTIMENT_DOT[sentiment] ?? "bg-gray-400";

  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardContent className="py-4 px-5">
        {/* Main row */}
        <div className="flex items-start gap-3">
          {/* Channel icon + sentiment dot */}
          <div className="relative shrink-0 mt-0.5">
            <div className="h-9 w-9 rounded-full bg-gray-100 flex items-center justify-center">
              <ChannelIcon channel={reply.channel} className="h-4 w-4 text-gray-600" />
            </div>
            <span
              className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${dotColor}`}
            />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div>
                <p className="font-semibold text-sm text-gray-900">
                  {reply.lead_name ?? "Unknown Lead"}
                </p>
                <p className="text-xs text-gray-400">{reply.lead_email ?? "—"}</p>
              </div>
              <div className="flex items-center gap-2 flex-wrap shrink-0">
                <span className="text-xs text-gray-400">{relativeTime(reply.received_at)}</span>
                {reply.sentiment && (
                  <Badge className={`text-xs ${SENTIMENT_BADGE[sentiment] ?? "bg-gray-100 text-gray-600"} flex items-center gap-1`}>
                    <SentimentIcon sentiment={reply.sentiment} />
                    {reply.sentiment}
                  </Badge>
                )}
              </div>
            </div>

            {reply.subject && (
              <p className="text-sm font-medium text-gray-800 mt-1">{reply.subject}</p>
            )}

            {reply.body_snippet && (
              <p className="text-sm text-gray-600 mt-0.5 leading-snug">
                {truncate(reply.body_snippet, 150)}
              </p>
            )}

            {/* Footer row */}
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {reply.ai_suggested_action && (
                <AIActionBadge action={reply.ai_suggested_action} />
              )}
              {reply.sequence_id && (
                <Link
                  href={`/sequences/${reply.sequence_id}/monitor`}
                  className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ArrowRight className="h-3 w-3" /> View Sequence
                </Link>
              )}
              {reply.processed_at && (
                <span className="text-xs text-gray-400">
                  Processed {relativeTime(reply.processed_at)}
                </span>
              )}
            </div>
          </div>

          {/* Expand toggle */}
          <button
            className="shrink-0 p-1 rounded hover:bg-gray-100 transition-colors mt-0.5"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? "Collapse" : "Expand"}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400" />
            )}
          </button>
        </div>

        {/* Expanded: AI analysis + enrollment info */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
            {/* AI Analysis */}
            {reply.ai_analysis && Object.keys(reply.ai_analysis).length > 0 ? (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                  <Bot className="h-3.5 w-3.5" /> AI Analysis
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries(reply.ai_analysis).map(([key, value]) => (
                    <div key={key} className="bg-gray-50 rounded p-2">
                      <p className="text-xs text-gray-400 capitalize">{key.replace(/_/g, " ")}</p>
                      <p className="text-sm font-medium text-gray-700 truncate">
                        {typeof value === "number"
                          ? value.toFixed(2)
                          : String(value ?? "—")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No AI analysis available.</p>
            )}

            {/* Confidence */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Sentiment confidence:</span>
              <span className="text-xs font-medium text-gray-700">
                {(reply.sentiment_confidence * 100).toFixed(0)}%
              </span>
            </div>

            {/* Enrollment / Lead links */}
            <div className="flex items-center gap-3 flex-wrap text-xs text-gray-500">
              {reply.enrollment_id && (
                <span>Enrollment ID: <span className="font-mono text-gray-700">{reply.enrollment_id}</span></span>
              )}
              {reply.lead_id && (
                <Link
                  href={`/leads`}
                  className="text-blue-600 hover:underline flex items-center gap-1"
                >
                  <ArrowRight className="h-3 w-3" /> View Lead
                </Link>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ReplyCardSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardContent className="py-4 px-5">
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-full bg-gray-200 shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 bg-gray-200 rounded" />
            <div className="h-3 w-48 bg-gray-100 rounded" />
            <div className="h-3 w-full bg-gray-100 rounded" />
            <div className="h-3 w-3/4 bg-gray-100 rounded" />
            <div className="flex gap-2">
              <div className="h-5 w-20 bg-gray-100 rounded" />
              <div className="h-5 w-24 bg-gray-100 rounded" />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

export default function ReplyInboxPage() {
  const [replies, setReplies] = useState<ReplyLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [sentiment, setSentiment] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReplies = useCallback(
    async (p: number, s: string) => {
      setLoading(true);
      setError(null);
      try {
        const sentimentParam = s === "all" ? undefined : s;
        const res = await sequencesApi.replyInbox(p, PAGE_SIZE, sentimentParam);
        setReplies(res.data.items);
        setTotal(res.data.total);
      } catch (err) {
        setError("Failed to load replies. The API may be unavailable.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchReplies(page, sentiment);
  }, [page, sentiment, fetchReplies]);

  const handleSentimentChange = (val: string) => {
    setSentiment(val);
    setPage(1);
  };

  const handleRefresh = () => {
    fetchReplies(page, sentiment);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Counts by sentiment from current page (approximate)
  const posCount = replies.filter((r) => r.sentiment?.toLowerCase() === "positive").length;
  const negCount = replies.filter((r) => r.sentiment?.toLowerCase() === "negative").length;
  const neuCount = replies.filter((r) => !r.sentiment || r.sentiment.toLowerCase() === "neutral").length;

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Inbox className="h-5 w-5 text-gray-600" />
          <h1 className="text-xl font-semibold">Reply Inbox</h1>
          {total > 0 && (
            <Badge className="bg-gray-100 text-gray-600 text-xs">{total} total</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <Filter className="h-4 w-4 text-gray-400" />
            <Select value={sentiment} onValueChange={handleSentimentChange}>
              <SelectTrigger className="w-36 h-8 text-sm">
                <SelectValue placeholder="Sentiment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Replies</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
                <SelectItem value="neutral">Neutral</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Sentiment stats row ──────────────────────────────────────────── */}
      {!loading && replies.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500">This page:</span>
          <Badge className="bg-green-100 text-green-700 text-xs flex items-center gap-1">
            <ThumbsUp className="h-3 w-3" /> {posCount} positive
          </Badge>
          <Badge className="bg-red-100 text-red-700 text-xs flex items-center gap-1">
            <ThumbsDown className="h-3 w-3" /> {negCount} negative
          </Badge>
          <Badge className="bg-gray-100 text-gray-600 text-xs flex items-center gap-1">
            <Minus className="h-3 w-3" /> {neuCount} neutral
          </Badge>
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <ReplyCardSkeleton key={i} />)}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle className="h-10 w-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-500 font-medium">{error}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={handleRefresh}>
              <RefreshCw className="h-4 w-4 mr-1" /> Retry
            </Button>
          </CardContent>
        </Card>
      ) : replies.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Inbox className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">
              {sentiment === "all" ? "No replies yet" : `No ${sentiment} replies found`}
            </p>
            <p className="text-sm text-gray-400 mt-1">
              {sentiment === "all"
                ? "Replies from your sequences will appear here once received."
                : "Try adjusting the sentiment filter."}
            </p>
            {sentiment !== "all" && (
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => handleSentimentChange("all")}
              >
                View all replies
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {replies.map((reply) => (
            <ReplyCard key={reply.id} reply={reply} />
          ))}
        </div>
      )}

      {/* ── Pagination ──────────────────────────────────────────────────── */}
      {!loading && !error && totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-gray-500">
            Page {page} of {totalPages} &middot; {total} total repl{total !== 1 ? "ies" : "y"}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <span className="text-sm text-gray-600 px-1">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
