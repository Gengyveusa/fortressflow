"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  Mail,
  MessageSquare,
  Linkedin,
  Clock,
  CheckCircle2,
  XCircle,
  Pause,
  ArrowUpRight,
  AlertTriangle,
  Inbox,
  RefreshCw,
  Users,
  Send,
  TrendingUp,
  Eye,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import {
  sequencesApi,
  type SequenceMonitor,
  type ChannelHealth,
  type EnrollmentMonitor,
} from "@/lib/api";

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

const ENROLLMENT_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  sent: "bg-blue-100 text-blue-700",
  opened: "bg-yellow-100 text-yellow-700",
  replied: "bg-purple-100 text-purple-700",
  paused: "bg-orange-100 text-orange-700",
  escalated: "bg-amber-100 text-amber-700",
  completed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
};

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "bg-green-100 text-green-700",
  negative: "bg-red-100 text-red-700",
  neutral: "bg-gray-100 text-gray-600",
};

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

// ── Skeletons ─────────────────────────────────────────────────────────────────

function StatCardSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardContent className="pt-6 space-y-2">
        <div className="h-4 w-24 bg-gray-200 rounded" />
        <div className="h-8 w-16 bg-gray-200 rounded" />
        <div className="h-3 w-20 bg-gray-100 rounded" />
      </CardContent>
    </Card>
  );
}

function ChannelCardSkeleton() {
  return (
    <Card className="animate-pulse">
      <CardContent className="pt-5 space-y-3">
        <div className="h-5 w-20 bg-gray-200 rounded" />
        <div className="h-2 w-full bg-gray-100 rounded" />
        <div className="flex gap-4">
          <div className="h-3 w-16 bg-gray-100 rounded" />
          <div className="h-3 w-16 bg-gray-100 rounded" />
        </div>
      </CardContent>
    </Card>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-12 w-full bg-gray-100 rounded" />
      ))}
    </div>
  );
}

// ── Touch History Timeline ─────────────────────────────────────────────────────

function TouchTimeline({ history }: { history: Record<string, unknown>[] }) {
  if (!history.length) {
    return <p className="text-sm text-gray-400 italic">No touch history recorded.</p>;
  }
  return (
    <ol className="relative border-l border-gray-200 space-y-4 ml-2 mt-2">
      {history.map((touch, idx) => {
        const channel = String(touch.channel ?? "email");
        const action = String(touch.action ?? touch.step_type ?? "touch");
        const status = String(touch.status ?? "sent");
        const ts = touch.sent_at ?? touch.timestamp ?? touch.created_at;
        return (
          <li key={idx} className="ml-5">
            <span className="absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full bg-white border border-gray-200 shadow-sm">
              <ChannelIcon channel={channel} className="h-3 w-3 text-gray-500" />
            </span>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium capitalize">{action}</span>
              <Badge className={`text-xs ${ENROLLMENT_STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
                {status}
              </Badge>
              {ts != null && (
                <span className="text-xs text-gray-400">{relativeTime(String(ts))}</span>
              )}
              <span className="text-xs text-gray-400 capitalize">via {channel}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// ── Reply Snippets ─────────────────────────────────────────────────────────────

function ReplySnippets({ snippets }: { snippets: Record<string, unknown>[] }) {
  if (!snippets.length) {
    return <p className="text-sm text-gray-400 italic">No replies recorded.</p>;
  }
  return (
    <div className="space-y-2 mt-2">
      {snippets.map((r, idx) => {
        const sentiment = String(r.sentiment ?? "neutral");
        const snippet = String(r.body_snippet ?? r.snippet ?? "");
        const ts = r.received_at ?? r.timestamp;
        return (
          <div key={idx} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center gap-2 mb-1">
              <Badge className={`text-xs ${SENTIMENT_COLORS[sentiment] ?? "bg-gray-100 text-gray-600"}`}>
                {sentiment}
              </Badge>
              {ts != null && <span className="text-xs text-gray-400">{relativeTime(String(ts))}</span>}
            </div>
            <p className="text-sm text-gray-700 line-clamp-2">{snippet || "No preview available."}</p>
          </div>
        );
      })}
    </div>
  );
}

// ── Enrollment Row (expandable) ───────────────────────────────────────────────

function EnrollmentRow({ enrollment }: { enrollment: EnrollmentMonitor }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <TableCell>
          <div>
            <p className="font-medium text-sm">{enrollment.lead_name}</p>
            <p className="text-xs text-gray-400">{enrollment.lead_email}</p>
          </div>
        </TableCell>
        <TableCell className="text-sm text-gray-600">{enrollment.lead_company}</TableCell>
        <TableCell>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium">{enrollment.current_step}</span>
            <span className="text-gray-400 text-xs">/ {enrollment.total_steps}</span>
          </div>
        </TableCell>
        <TableCell>
          <Badge
            className={`text-xs ${ENROLLMENT_STATUS_COLORS[enrollment.status] ?? "bg-gray-100 text-gray-600"}`}
          >
            {enrollment.status}
          </Badge>
        </TableCell>
        <TableCell className="text-xs text-gray-500">
          {relativeTime(enrollment.last_touch_at)}
        </TableCell>
        <TableCell>
          {enrollment.escalation_channel ? (
            <div className="flex items-center gap-1">
              <ChannelIcon
                channel={enrollment.escalation_channel}
                className="h-3.5 w-3.5 text-gray-500"
              />
              <span className="text-xs capitalize">{enrollment.escalation_channel}</span>
            </div>
          ) : (
            <span className="text-xs text-gray-400">—</span>
          )}
        </TableCell>
        <TableCell>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
          >
            <Eye className="h-3.5 w-3.5 mr-1" />
            {expanded ? "Hide" : "View"}
          </Button>
        </TableCell>
      </TableRow>

      {expanded && (
        <TableRow className="bg-gray-50 hover:bg-gray-50">
          <TableCell colSpan={7} className="py-4 px-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Touch history */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <Clock className="h-4 w-4 text-gray-400" /> Touch History
                </h4>
                <TouchTimeline history={enrollment.touch_history} />
              </div>

              {/* Reply snippets */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <Inbox className="h-4 w-4 text-gray-400" /> Replies
                </h4>
                <ReplySnippets snippets={enrollment.reply_snippets} />
              </div>
            </div>

            {/* FSM state */}
            <div className="mt-4 pt-4 border-t border-gray-200 flex items-center gap-3 flex-wrap">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                Current FSM State:
              </span>
              <Badge
                className={`${ENROLLMENT_STATUS_COLORS[enrollment.status] ?? "bg-gray-100 text-gray-600"}`}
              >
                {enrollment.status}
              </Badge>
              {enrollment.hole_filler_triggered && (
                <Badge className="bg-amber-100 text-amber-700">
                  <AlertTriangle className="h-3 w-3 mr-1" /> Hole Filler Active
                </Badge>
              )}
              {enrollment.last_state_change_at && (
                <span className="text-xs text-gray-400">
                  State changed {relativeTime(enrollment.last_state_change_at)}
                </span>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ── Channel Health Card ────────────────────────────────────────────────────────

function ChannelHealthCard({ health }: { health: ChannelHealth }) {
  const utilPct = Math.min(100, Math.round(health.utilization * 100));
  const colorClass =
    utilPct >= 90
      ? "border-red-200 bg-red-50"
      : utilPct >= 70
      ? "border-yellow-200 bg-yellow-50"
      : "border-green-200 bg-green-50";
  const progressColor =
    utilPct >= 90 ? "[&>div]:bg-red-500" : utilPct >= 70 ? "[&>div]:bg-yellow-500" : "[&>div]:bg-green-500";

  return (
    <Card className={`border ${colorClass}`}>
      <CardContent className="pt-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ChannelIcon channel={health.channel} className="h-4 w-4 text-gray-600" />
            <span className="font-medium text-sm capitalize">{health.channel}</span>
          </div>
          <span className="text-xs text-gray-500">
            {health.sent_today} / {health.limit} sent
          </span>
        </div>

        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Utilization</span>
            <span>{utilPct}%</span>
          </div>
          <Progress value={utilPct} className={`h-2 ${progressColor}`} />
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3 text-amber-500" />
            <span>Bounce: {(health.bounce_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-blue-500" />
            <span>Reply: {(health.reply_rate * 100).toFixed(1)}%</span>
          </div>
        </div>

        {health.last_failure && (
          <p className="text-xs text-red-500 flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Last failure: {relativeTime(health.last_failure)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Daily Activity Chart ───────────────────────────────────────────────────────

function DailyActivityTab({ dailySendCount }: { dailySendCount: Record<string, number> }) {
  const entries = Object.entries(dailySendCount).sort(([a], [b]) => a.localeCompare(b));
  if (!entries.length) {
    return (
      <div className="py-16 text-center">
        <Activity className="h-10 w-10 text-gray-300 mx-auto mb-3" />
        <p className="text-sm text-gray-400">No send activity recorded yet.</p>
      </div>
    );
  }
  const maxVal = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">Daily Send Volume</h3>
      <div className="space-y-2">
        {entries.map(([date, count]) => {
          const widthPct = Math.round((count / maxVal) * 100);
          return (
            <div key={date} className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-24 shrink-0">{date}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full flex items-center justify-end pr-2 transition-all"
                  style={{ width: `${Math.max(widthPct, 4)}%` }}
                >
                  <span className="text-xs text-white font-medium">{count}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SequenceMonitorPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [monitor, setMonitor] = useState<SequenceMonitor | null>(null);
  const [channelHealth, setChannelHealth] = useState<ChannelHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const [monitorRes, healthRes] = await Promise.all([
        sequencesApi.monitor(id),
        sequencesApi.channelHealth(id),
      ]);
      setMonitor(monitorRes.data);
      setChannelHealth(healthRes.data);
      setLastRefresh(new Date());
    } catch (err) {
      setError("Failed to load monitor data. The API may be unavailable.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRefresh = () => {
    setLoading(true);
    fetchData();
  };

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading && !monitor) {
    return (
      <div className="space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-20 bg-gray-200 rounded animate-pulse" />
            <div className="h-6 w-40 bg-gray-200 rounded animate-pulse" />
            <div className="h-5 w-16 bg-gray-100 rounded animate-pulse" />
          </div>
          <div className="h-8 w-24 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <ChannelCardSkeleton key={i} />)}
        </div>
        <TableSkeleton />
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (error && !monitor) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/sequences">
            ← Back to Sequences
          </Link>
        </Button>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle className="h-10 w-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-500 font-medium">{error}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={handleRefresh}>
              <RefreshCw className="h-4 w-4 mr-1" /> Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!monitor) return null;

  const total = monitor.total_enrolled || 1; // avoid division by zero
  const activePct = Math.round((monitor.active / total) * 100);
  const repliedPct = Math.round((monitor.replied / total) * 100);
  const completedPct = Math.round((monitor.completed / total) * 100);

  const statusColorClass =
    monitor.status === "active"
      ? "bg-green-100 text-green-700"
      : monitor.status === "paused"
      ? "bg-yellow-100 text-yellow-700"
      : "bg-gray-100 text-gray-700";

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/sequences">
              ← Sequences
            </Link>
          </Button>
          <h1 className="text-xl font-semibold">{monitor.sequence_name}</h1>
          <Badge className={statusColorClass}>{monitor.status}</Badge>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            Last refreshed {relativeTime(lastRefresh.toISOString())}
          </span>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Stats row ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-blue-50 border-blue-100">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-blue-700">Total Enrolled</p>
              <Users className="h-4 w-4 text-blue-400" />
            </div>
            <p className="text-3xl font-bold text-blue-800">{monitor.total_enrolled}</p>
            <p className="text-xs text-blue-500 mt-1">All time enrollments</p>
          </CardContent>
        </Card>

        <Card className="bg-green-50 border-green-100">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-green-700">Active</p>
              <Activity className="h-4 w-4 text-green-400" />
            </div>
            <p className="text-3xl font-bold text-green-800">{monitor.active}</p>
            <p className="text-xs text-green-500 mt-1">{activePct}% of total</p>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 border-purple-100">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-purple-700">Replied</p>
              <Inbox className="h-4 w-4 text-purple-400" />
            </div>
            <p className="text-3xl font-bold text-purple-800">{monitor.replied}</p>
            <p className="text-xs text-purple-500 mt-1">{repliedPct}% reply rate</p>
          </CardContent>
        </Card>

        <Card className="bg-emerald-50 border-emerald-100">
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-emerald-700">Completed</p>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <p className="text-3xl font-bold text-emerald-800">{monitor.completed}</p>
            <p className="text-xs text-emerald-500 mt-1">{completedPct}% completion rate</p>
          </CardContent>
        </Card>
      </div>

      {/* ── Channel Health ─────────────────────────────────────────────────── */}
      {channelHealth.length > 0 && (
        <div>
          <h2 className="text-base font-semibold mb-3 text-gray-800">Channel Health</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {channelHealth.map((ch) => (
              <ChannelHealthCard key={ch.channel} health={ch} />
            ))}
          </div>
        </div>
      )}

      {/* ── Tabs ──────────────────────────────────────────────────────────── */}
      <Tabs defaultValue="enrollments">
        <TabsList className="grid w-full grid-cols-2 max-w-sm">
          <TabsTrigger value="enrollments">
            <Users className="h-4 w-4 mr-1.5" /> Enrollments
          </TabsTrigger>
          <TabsTrigger value="activity">
            <TrendingUp className="h-4 w-4 mr-1.5" /> Daily Activity
          </TabsTrigger>
        </TabsList>

        {/* Enrollments tab */}
        <TabsContent value="enrollments" className="mt-4">
          {monitor.enrollments.length === 0 ? (
            <Card>
              <CardContent className="py-16 text-center">
                <Users className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 font-medium">No enrollments yet</p>
                <p className="text-sm text-gray-400 mt-1">
                  Enroll leads to this sequence to start tracking their progress.
                </p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-gray-600">
                  {monitor.enrollments.length} enrollment{monitor.enrollments.length !== 1 ? "s" : ""}
                  <span className="text-xs text-gray-400 ml-2 font-normal">Click a row to expand details</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="text-xs font-medium text-gray-500 pl-6">Lead</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Company</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Step</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Status</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Last Touch</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Channel</TableHead>
                      <TableHead className="text-xs font-medium text-gray-500">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {monitor.enrollments.map((enrollment) => (
                      <EnrollmentRow key={enrollment.id} enrollment={enrollment} />
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Daily Activity tab */}
        <TabsContent value="activity" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              <DailyActivityTab dailySendCount={monitor.daily_send_count} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── Failed count warning ───────────────────────────────────────────── */}
      {monitor.failed > 0 && (
        <div className="flex items-start gap-3 p-4 bg-red-50 rounded-lg border border-red-200">
          <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">
              {monitor.failed} enrollment{monitor.failed !== 1 ? "s" : ""} failed
            </p>
            <p className="text-xs text-red-600 mt-0.5">
              Review failed enrollments and check channel health for potential issues.
            </p>
          </div>
        </div>
      )}

      {/* ── Paused warning ─────────────────────────────────────────────────── */}
      {monitor.status === "paused" && (
        <div className="flex items-start gap-3 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
          <Pause className="h-5 w-5 text-yellow-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-800">Sequence is paused</p>
            <p className="text-xs text-yellow-600 mt-0.5">
              No new touches will be sent until the sequence is resumed.
            </p>
          </div>
          <Link href={`/sequences/${id}`} className="ml-auto">
            <Button variant="outline" size="sm" className="border-yellow-300 text-yellow-700 hover:bg-yellow-100">
              <ArrowUpRight className="h-3.5 w-3.5 mr-1" /> Manage
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}
