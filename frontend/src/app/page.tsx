"use client";

import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import {
  Brain,
  Sparkles,
  Zap,
  Shield,
  Search,
  Mail,
  Phone,
  Globe,
  Database,
  Bot,
  Radio,
  Activity,
  TrendingUp,
  Users,
  Eye,
  MessageSquare,
  Calendar,
  Trophy,
  Target,
  FileText,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  Flame,
  Send,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";

// ── Types ────────────────────────────────────────────────────

interface AgentHeatmapEntry {
  agent_name: string;
  display_name: string;
  icon: string;
  success_rate: number;
  total_executions: number;
  avg_latency_ms: number;
  status: "healthy" | "degraded" | "inactive";
  errors_24h: number;
}

interface LiveFeedEntry {
  id: string;
  agent: string;
  action: string;
  status: "success" | "error" | "rate_limited";
  latency_ms: number;
  timestamp: string;
  params_preview?: string;
}

interface ProvenanceSource {
  name: string;
  count: number;
  color: string;
}

interface ProvenanceStats {
  sources: ProvenanceSource[];
  enriched_pct: number;
  phone_verified_pct: number;
  email_verified_pct: number;
  crm_synced_pct: number;
  total_leads: number;
}

interface ProvenanceTimelineEvent {
  timestamp: string;
  event: string;
  source: string;
  details: string;
}

interface FunnelStage {
  stage: string;
  count: number;
  conversion_pct: number;
}

interface ActiveSequence {
  id: string;
  name: string;
  enrolled: number;
  completed: number;
  replied: number;
  total_steps: number;
}

interface PositiveSignal {
  id: string;
  type: "open" | "reply" | "meeting";
  lead_name: string;
  lead_company: string;
  timestamp: string;
  details: string;
}

interface JourneyData {
  funnel: FunnelStage[];
  active_sequences: ActiveSequence[];
  positive_signals: PositiveSignal[];
}

// ── Mock Data ────────────────────────────────────────────────

const MOCK_AGENTS: AgentHeatmapEntry[] = [
  { agent_name: "groq", display_name: "Groq LLM", icon: "zap", success_rate: 97.2, total_executions: 14832, avg_latency_ms: 89, status: "healthy", errors_24h: 3 },
  { agent_name: "openai", display_name: "OpenAI GPT", icon: "brain", success_rate: 94.8, total_executions: 12405, avg_latency_ms: 420, status: "healthy", errors_24h: 12 },
  { agent_name: "apollo", display_name: "Apollo Enricher", icon: "search", success_rate: 91.3, total_executions: 8921, avg_latency_ms: 310, status: "healthy", errors_24h: 7 },
  { agent_name: "zoominfo", display_name: "ZoomInfo Lookup", icon: "globe", success_rate: 88.6, total_executions: 6540, avg_latency_ms: 540, status: "degraded", errors_24h: 22 },
  { agent_name: "hubspot", display_name: "HubSpot CRM", icon: "database", success_rate: 96.1, total_executions: 11200, avg_latency_ms: 180, status: "healthy", errors_24h: 5 },
  { agent_name: "email_sender", display_name: "Email Sender", icon: "mail", success_rate: 99.1, total_executions: 24500, avg_latency_ms: 45, status: "healthy", errors_24h: 1 },
  { agent_name: "phone_verifier", display_name: "Phone Verifier", icon: "phone", success_rate: 82.4, total_executions: 3200, avg_latency_ms: 1200, status: "degraded", errors_24h: 34 },
  { agent_name: "compliance", display_name: "Compliance Gate", icon: "shield", success_rate: 100.0, total_executions: 18700, avg_latency_ms: 12, status: "healthy", errors_24h: 0 },
  { agent_name: "sequence_engine", display_name: "Sequence Engine", icon: "bot", success_rate: 95.7, total_executions: 9840, avg_latency_ms: 65, status: "healthy", errors_24h: 8 },
  { agent_name: "analytics", display_name: "Analytics Agg.", icon: "activity", success_rate: 68.2, total_executions: 4100, avg_latency_ms: 2100, status: "inactive", errors_24h: 48 },
];

const MOCK_FEED: LiveFeedEntry[] = [
  { id: "f1", agent: "groq", action: "generate_email", status: "success", latency_ms: 87, timestamp: new Date(Date.now() - 3000).toISOString(), params_preview: '{"lead_id": "L-4821", "template": "cold_intro_v2"}' },
  { id: "f2", agent: "hubspot", action: "sync_contact", status: "success", latency_ms: 145, timestamp: new Date(Date.now() - 8000).toISOString(), params_preview: '{"lead_id": "L-4820", "fields": ["email", "phone"]}' },
  { id: "f3", agent: "zoominfo", action: "enrich_lead", status: "error", latency_ms: 5200, timestamp: new Date(Date.now() - 15000).toISOString(), params_preview: '{"email": "jane@acmecorp.com"}' },
  { id: "f4", agent: "email_sender", action: "send_touch", status: "success", latency_ms: 42, timestamp: new Date(Date.now() - 22000).toISOString(), params_preview: '{"sequence_id": "SEQ-12", "step": 3}' },
  { id: "f5", agent: "openai", action: "analyze_reply", status: "success", latency_ms: 380, timestamp: new Date(Date.now() - 30000).toISOString(), params_preview: '{"reply_id": "R-991", "sentiment": true}' },
  { id: "f6", agent: "apollo", action: "search_contacts", status: "rate_limited", latency_ms: 0, timestamp: new Date(Date.now() - 45000).toISOString(), params_preview: '{"domain": "bigcorp.io", "title": "VP Sales"}' },
  { id: "f7", agent: "compliance", action: "check_consent", status: "success", latency_ms: 8, timestamp: new Date(Date.now() - 52000).toISOString(), params_preview: '{"lead_id": "L-4818", "channel": "email"}' },
  { id: "f8", agent: "sequence_engine", action: "advance_step", status: "success", latency_ms: 55, timestamp: new Date(Date.now() - 60000).toISOString(), params_preview: '{"enrollment_id": "EN-445", "to_step": 4}' },
  { id: "f9", agent: "phone_verifier", action: "verify_number", status: "error", latency_ms: 3100, timestamp: new Date(Date.now() - 75000).toISOString(), params_preview: '{"phone": "+1-555-0199"}' },
  { id: "f10", agent: "groq", action: "summarize_thread", status: "success", latency_ms: 112, timestamp: new Date(Date.now() - 90000).toISOString(), params_preview: '{"thread_id": "T-882"}' },
  { id: "f11", agent: "analytics", action: "aggregate_daily", status: "error", latency_ms: 8500, timestamp: new Date(Date.now() - 120000).toISOString(), params_preview: '{"date": "2026-03-29"}' },
  { id: "f12", agent: "hubspot", action: "create_deal", status: "success", latency_ms: 220, timestamp: new Date(Date.now() - 150000).toISOString(), params_preview: '{"lead_id": "L-4815", "amount": 25000}' },
];

const MOCK_PROVENANCE: ProvenanceStats = {
  sources: [
    { name: "CSV Import", count: 4200, color: "#6366f1" },
    { name: "Apollo", count: 3100, color: "#8b5cf6" },
    { name: "ZoomInfo", count: 2800, color: "#a78bfa" },
    { name: "HubSpot", count: 1900, color: "#c4b5fd" },
    { name: "Manual", count: 600, color: "#ddd6fe" },
  ],
  enriched_pct: 78.4,
  phone_verified_pct: 62.1,
  email_verified_pct: 91.7,
  crm_synced_pct: 85.3,
  total_leads: 12600,
};

const MOCK_JOURNEY: JourneyData = {
  funnel: [
    { stage: "Discovered", count: 12600, conversion_pct: 100 },
    { stage: "Enriched", count: 9880, conversion_pct: 78.4 },
    { stage: "Contacted", count: 7210, conversion_pct: 73.0 },
    { stage: "Engaged", count: 3840, conversion_pct: 53.3 },
    { stage: "Replied", count: 1920, conversion_pct: 50.0 },
    { stage: "Meeting", count: 640, conversion_pct: 33.3 },
    { stage: "Won", count: 185, conversion_pct: 28.9 },
  ],
  active_sequences: [
    { id: "seq1", name: "Cold Outreach - SaaS CTOs", enrolled: 420, completed: 180, replied: 62, total_steps: 6 },
    { id: "seq2", name: "Re-engagement Q1 2026", enrolled: 310, completed: 95, replied: 41, total_steps: 4 },
    { id: "seq3", name: "Enterprise Warm Intro", enrolled: 185, completed: 40, replied: 28, total_steps: 5 },
    { id: "seq4", name: "Inbound MQL Follow-up", enrolled: 540, completed: 320, replied: 115, total_steps: 3 },
  ],
  positive_signals: [
    { id: "ps1", type: "reply", lead_name: "Sarah Chen", lead_company: "Datastream Inc", timestamp: new Date(Date.now() - 180000).toISOString(), details: "Positive reply - interested in demo" },
    { id: "ps2", type: "meeting", lead_name: "Marcus Johnson", lead_company: "TechVault", timestamp: new Date(Date.now() - 600000).toISOString(), details: "Meeting booked for April 2" },
    { id: "ps3", type: "open", lead_name: "Emily Rodriguez", lead_company: "CloudNine Solutions", timestamp: new Date(Date.now() - 900000).toISOString(), details: "Opened email 4 times in 2 hours" },
    { id: "ps4", type: "reply", lead_name: "David Kim", lead_company: "FinScale", timestamp: new Date(Date.now() - 1800000).toISOString(), details: "Asked for pricing information" },
    { id: "ps5", type: "meeting", lead_name: "Lisa Patel", lead_company: "GrowthForge", timestamp: new Date(Date.now() - 3600000).toISOString(), details: "Meeting booked for April 3" },
    { id: "ps6", type: "open", lead_name: "James Wilson", lead_company: "NexGen AI", timestamp: new Date(Date.now() - 5400000).toISOString(), details: "Clicked pricing link twice" },
    { id: "ps7", type: "reply", lead_name: "Ana Moreno", lead_company: "BrightPath", timestamp: new Date(Date.now() - 7200000).toISOString(), details: "Forwarded to VP Engineering" },
  ],
};

const MOCK_TIMELINE: ProvenanceTimelineEvent[] = [
  { timestamp: "2026-03-29T10:00:00Z", event: "Lead Created", source: "CSV Import", details: "Imported from Q1 prospect list" },
  { timestamp: "2026-03-29T10:05:00Z", event: "Email Verified", source: "ZeroBounce", details: "Status: valid, deliverable" },
  { timestamp: "2026-03-29T10:12:00Z", event: "Enriched", source: "Apollo", details: "Added title, company size, LinkedIn URL" },
  { timestamp: "2026-03-29T11:00:00Z", event: "Phone Verified", source: "Twilio Lookup", details: "Mobile, carrier: Verizon" },
  { timestamp: "2026-03-29T11:30:00Z", event: "CRM Synced", source: "HubSpot", details: "Contact created, deal attached" },
  { timestamp: "2026-03-29T14:00:00Z", event: "Sequence Enrolled", source: "Sequence Engine", details: "Cold Outreach - SaaS CTOs (Step 1)" },
];

// ── Icon Map ─────────────────────────────────────────────────

const AGENT_ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  zap: Zap,
  brain: Brain,
  sparkles: Sparkles,
  search: Search,
  globe: Globe,
  database: Database,
  mail: Mail,
  phone: Phone,
  shield: Shield,
  bot: Bot,
  activity: Activity,
  radio: Radio,
};

// ── Utility ──────────────────────────────────────────────────

function timeAgo(timestamp: string): string {
  const seconds = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

function statusColor(status: "healthy" | "degraded" | "inactive"): string {
  switch (status) {
    case "healthy":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "degraded":
      return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case "inactive":
      return "bg-red-500/20 text-red-400 border-red-500/30";
  }
}

function rateBarColor(rate: number): string {
  if (rate >= 90) return "bg-emerald-500";
  if (rate >= 70) return "bg-amber-500";
  return "bg-red-500";
}

function feedDotColor(status: "success" | "error" | "rate_limited"): string {
  switch (status) {
    case "success":
      return "bg-emerald-400";
    case "error":
      return "bg-red-400";
    case "rate_limited":
      return "bg-amber-400";
  }
}

function signalIcon(type: "open" | "reply" | "meeting") {
  switch (type) {
    case "open":
      return Eye;
    case "reply":
      return MessageSquare;
    case "meeting":
      return Calendar;
  }
}

// ── Custom Chart Tooltip ─────────────────────────────────────

interface PieTooltipProps {
  active?: boolean;
  payload?: { name: string; value: number; payload: { color: string } }[];
}

function PieTooltipContent({ active, payload }: PieTooltipProps) {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl px-3 py-2 text-xs">
      <div className="flex items-center gap-2">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ background: entry.payload.color }}
        />
        <span className="text-gray-300 font-medium">{entry.name}</span>
      </div>
      <p className="text-white font-semibold mt-1">
        {entry.value.toLocaleString()} leads
      </p>
    </div>
  );
}

// ── Skeletons ────────────────────────────────────────────────

function AgentCardSkeleton() {
  return (
    <Card className="dark:bg-gray-900/60 dark:border-gray-800 animate-pulse">
      <CardContent className="p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-lg bg-gray-700/50" />
          <div className="space-y-1.5 flex-1">
            <div className="h-3.5 w-24 bg-gray-700/50 rounded" />
            <div className="h-2.5 w-16 bg-gray-700/30 rounded" />
          </div>
        </div>
        <div className="h-2 w-full bg-gray-700/30 rounded mb-3" />
        <div className="flex justify-between">
          <div className="h-3 w-12 bg-gray-700/30 rounded" />
          <div className="h-3 w-12 bg-gray-700/30 rounded" />
        </div>
      </CardContent>
    </Card>
  );
}

function FeedSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 animate-pulse">
          <div className="w-2 h-2 rounded-full bg-gray-700/50" />
          <div className="h-4 flex-1 bg-gray-700/30 rounded" />
          <div className="h-4 w-14 bg-gray-700/30 rounded" />
        </div>
      ))}
    </div>
  );
}

// ── Agent Heatmap Card ───────────────────────────────────────

function AgentCard({ agent }: { agent: AgentHeatmapEntry }) {
  const IconComponent = AGENT_ICON_MAP[agent.icon] ?? Bot;

  return (
    <Card
      className="dark:bg-gray-900/70 dark:border-gray-800 hover:dark:border-gray-700
                 transition-all duration-200 hover:shadow-lg hover:shadow-indigo-500/5
                 group relative overflow-hidden"
      role="article"
      aria-label={`Agent ${agent.display_name}: ${agent.status}, ${agent.success_rate}% success rate`}
    >
      {/* Subtle top-edge glow based on status */}
      <div
        className={`absolute top-0 left-0 right-0 h-0.5 ${
          agent.status === "healthy"
            ? "bg-gradient-to-r from-emerald-500/60 via-emerald-400/40 to-emerald-500/60"
            : agent.status === "degraded"
            ? "bg-gradient-to-r from-amber-500/60 via-amber-400/40 to-amber-500/60"
            : "bg-gradient-to-r from-red-500/60 via-red-400/40 to-red-500/60"
        }`}
      />
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div
              className={`p-2 rounded-lg ${
                agent.status === "healthy"
                  ? "bg-indigo-500/10 text-indigo-400"
                  : agent.status === "degraded"
                  ? "bg-amber-500/10 text-amber-400"
                  : "bg-gray-500/10 text-gray-500"
              }`}
            >
              <IconComponent className="h-4.5 w-4.5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-100 leading-tight">
                {agent.display_name}
              </p>
              <p className="text-xs text-gray-500 font-mono">{agent.agent_name}</p>
            </div>
          </div>
          <Badge
            variant="outline"
            className={`text-[10px] px-1.5 py-0 border ${statusColor(agent.status)}`}
          >
            {agent.status}
          </Badge>
        </div>

        {/* Success Rate Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-400">Success Rate</span>
            <span
              className={`text-xs font-bold ${
                agent.success_rate >= 90
                  ? "text-emerald-400"
                  : agent.success_rate >= 70
                  ? "text-amber-400"
                  : "text-red-400"
              }`}
            >
              {agent.success_rate.toFixed(1)}%
            </span>
          </div>
          <div
            className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden"
            role="progressbar"
            aria-valuenow={agent.success_rate}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Success rate: ${agent.success_rate}%`}
          >
            <div
              className={`h-full rounded-full transition-all duration-500 ${rateBarColor(agent.success_rate)}`}
              style={{ width: `${agent.success_rate}%` }}
            />
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Execs</p>
            <p className="text-sm font-semibold text-gray-200">
              {formatNumber(agent.total_executions)}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Latency</p>
            <p className="text-sm font-semibold text-gray-200">
              {agent.avg_latency_ms}ms
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Errors</p>
            <p
              className={`text-sm font-semibold ${
                agent.errors_24h === 0
                  ? "text-emerald-400"
                  : agent.errors_24h < 10
                  ? "text-amber-400"
                  : "text-red-400"
              }`}
            >
              {agent.errors_24h}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Live Feed Item ───────────────────────────────────────────

function FeedItem({ entry }: { entry: LiveFeedEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="group flex items-start gap-3 py-2 px-2 rounded-lg
                 hover:bg-gray-800/50 transition-colors cursor-pointer"
      onClick={() => setExpanded(!expanded)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={`${entry.agent}.${entry.action} - ${entry.status} - ${entry.latency_ms}ms`}
    >
      <div className="mt-1.5 flex-shrink-0">
        <span
          className={`block w-2 h-2 rounded-full ${feedDotColor(entry.status)}`}
          aria-hidden="true"
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-mono text-gray-200">
            <span className="text-indigo-400">{entry.agent}</span>
            <span className="text-gray-600">.</span>
            <span className="text-gray-300">{entry.action}</span>
          </span>
          <span className="text-xs text-gray-500">
            {entry.latency_ms > 0 ? `${entry.latency_ms}ms` : "---"}
          </span>
          <span className="text-xs text-gray-600 ml-auto flex-shrink-0">
            {timeAgo(entry.timestamp)}
          </span>
        </div>
        {expanded && entry.params_preview && (
          <pre className="mt-1.5 text-[11px] text-gray-500 bg-gray-800/80 rounded px-2 py-1.5
                          overflow-x-auto font-mono leading-relaxed">
            {entry.params_preview}
          </pre>
        )}
      </div>
      <div className="mt-1 flex-shrink-0">
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-gray-600" aria-hidden="true" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}

// ── Provenance Timeline ──────────────────────────────────────

function ProvenanceTimeline({ events }: { events: ProvenanceTimelineEvent[] }) {
  return (
    <div className="relative pl-6" role="list" aria-label="Lead provenance timeline">
      {/* Vertical line */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-gradient-to-b from-indigo-500 via-purple-500 to-indigo-500/30" />
      {events.map((ev, i) => (
        <div
          key={i}
          className="relative flex items-start gap-4 pb-6 last:pb-0"
          role="listitem"
        >
          {/* Dot */}
          <div className="absolute left-[-15px] top-1.5 w-3 h-3 rounded-full border-2 border-indigo-500 bg-gray-900 z-10" />
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-gray-200">{ev.event}</span>
              <Badge
                variant="outline"
                className="text-[10px] border-gray-700 text-gray-400"
              >
                {ev.source}
              </Badge>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">{ev.details}</p>
            <p className="text-[10px] text-gray-600 mt-1 font-mono">
              {new Date(ev.timestamp).toLocaleString()}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Funnel Stage ─────────────────────────────────────────────

const FUNNEL_COLORS = [
  "from-blue-600 to-blue-500",
  "from-blue-500 to-cyan-500",
  "from-cyan-500 to-teal-500",
  "from-teal-500 to-emerald-500",
  "from-emerald-500 to-green-500",
  "from-green-500 to-lime-500",
  "from-lime-500 to-yellow-500",
];

function FunnelChart({ stages }: { stages: FunnelStage[] }) {
  const maxCount = stages[0]?.count || 1;

  return (
    <div className="space-y-2" role="img" aria-label="Lead journey funnel chart">
      {stages.map((stage, i) => {
        const widthPct = Math.max((stage.count / maxCount) * 100, 12);
        return (
          <div key={stage.stage} className="flex items-center gap-4">
            <div className="w-24 text-right">
              <span className="text-xs font-medium text-gray-400">{stage.stage}</span>
            </div>
            <div className="flex-1 relative">
              <div
                className={`h-10 rounded-lg bg-gradient-to-r ${FUNNEL_COLORS[i] ?? FUNNEL_COLORS[0]}
                             flex items-center justify-between px-3 transition-all duration-700
                             shadow-sm`}
                style={{ width: `${widthPct}%` }}
                role="meter"
                aria-valuenow={stage.count}
                aria-valuemin={0}
                aria-valuemax={maxCount}
                aria-label={`${stage.stage}: ${stage.count} leads`}
              >
                <span className="text-sm font-bold text-white drop-shadow">
                  {formatNumber(stage.count)}
                </span>
                {i > 0 && (
                  <span className="text-[10px] font-medium text-white/80">
                    {stage.conversion_pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {i < stages.length - 1 && (
              <div className="w-8 flex justify-center">
                <ArrowRight className="h-3.5 w-3.5 text-gray-600" aria-hidden="true" />
              </div>
            )}
            {i === stages.length - 1 && <div className="w-8" />}
          </div>
        );
      })}
    </div>
  );
}

// ── Enrichment Coverage Card ─────────────────────────────────

function CoverageStatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <Card className="dark:bg-gray-900/70 dark:border-gray-800">
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`p-2.5 rounded-lg ${color}`}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-100">{value.toFixed(1)}%</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Active Sequence Card ─────────────────────────────────────

function SequenceCard({ seq }: { seq: ActiveSequence }) {
  const progressPct = seq.total_steps > 0 ? (seq.completed / seq.enrolled) * 100 : 0;

  return (
    <Card className="dark:bg-gray-900/70 dark:border-gray-800">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-gray-200 truncate pr-2">
            {seq.name}
          </h4>
          <Badge variant="outline" className="border-indigo-500/30 text-indigo-400 text-[10px] flex-shrink-0">
            {seq.total_steps} steps
          </Badge>
        </div>
        <div className="flex items-center gap-4 mb-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" aria-hidden="true" />
            {seq.enrolled} enrolled
          </span>
          <span className="flex items-center gap-1">
            <MessageSquare className="h-3 w-3" aria-hidden="true" />
            {seq.replied} replies
          </span>
        </div>
        <div>
          <div className="flex justify-between text-[10px] text-gray-500 mb-1">
            <span>Progress</span>
            <span>{progressPct.toFixed(0)}% completed</span>
          </div>
          <Progress value={progressPct} className="h-1.5" />
        </div>
      </CardContent>
    </Card>
  );
}

// ── Signal Feed Item ─────────────────────────────────────────

function SignalItem({ signal }: { signal: PositiveSignal }) {
  const Icon = signalIcon(signal.type);
  const typeColors: Record<string, string> = {
    open: "text-blue-400 bg-blue-500/10",
    reply: "text-emerald-400 bg-emerald-500/10",
    meeting: "text-purple-400 bg-purple-500/10",
  };

  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-800/50 last:border-0">
      <div className={`p-1.5 rounded-md ${typeColors[signal.type]}`}>
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">{signal.lead_name}</span>
          <span className="text-xs text-gray-500">{signal.lead_company}</span>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">{signal.details}</p>
      </div>
      <span className="text-[10px] text-gray-600 flex-shrink-0 mt-0.5">
        {timeAgo(signal.timestamp)}
      </span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// ── Page Component ───────────────────────────────────────────
// ══════════════════════════════════════════════════════════════

export default function MissionControlPage() {
  const [activeTab, setActiveTab] = useState("live-operations");
  const [provenanceSearch, setProvenanceSearch] = useState("");
  const [searchSubmitted, setSearchSubmitted] = useState(false);

  // ── Data Fetching ────────────────────────────────────────

  const {
    data: agentHeatmap,
    isLoading: heatmapLoading,
  } = useQuery<AgentHeatmapEntry[]>({
    queryKey: ["mission-control", "agent-heatmap"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/agent-heatmap");
        return res.data;
      } catch {
        return MOCK_AGENTS;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const {
    data: liveFeed,
    isLoading: feedLoading,
  } = useQuery<LiveFeedEntry[]>({
    queryKey: ["mission-control", "live-feed"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/agent-live-feed");
        return res.data;
      } catch {
        return MOCK_FEED;
      }
    },
    refetchInterval: 5_000,
    staleTime: 3_000,
  });

  const {
    data: provenance,
    isLoading: provenanceLoading,
  } = useQuery<ProvenanceStats>({
    queryKey: ["mission-control", "provenance"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/provenance");
        return res.data;
      } catch {
        return MOCK_PROVENANCE;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const {
    data: journey,
    isLoading: journeyLoading,
  } = useQuery<JourneyData>({
    queryKey: ["mission-control", "journey-funnel"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/journey-funnel");
        return res.data;
      } catch {
        return MOCK_JOURNEY;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // ── Provenance search ──────────────────────────────────

  const {
    data: provenanceTimeline,
    isLoading: timelineLoading,
    isFetching: timelineFetching,
  } = useQuery<ProvenanceTimelineEvent[]>({
    queryKey: ["mission-control", "provenance-timeline", provenanceSearch],
    queryFn: async () => {
      try {
        const res = await api.get(`/monitor/provenance/timeline?email=${encodeURIComponent(provenanceSearch)}`);
        return res.data;
      } catch {
        return MOCK_TIMELINE;
      }
    },
    enabled: searchSubmitted && provenanceSearch.length > 0,
    staleTime: 60_000,
  });

  const handleProvenanceSearch = useCallback(() => {
    if (provenanceSearch.trim().length > 0) {
      setSearchSubmitted(true);
    }
  }, [provenanceSearch]);

  // ── Derived data ────────────────────────────────────────

  const agents = agentHeatmap ?? MOCK_AGENTS;
  const feed = liveFeed ?? MOCK_FEED;
  const prov = provenance ?? MOCK_PROVENANCE;
  const journeyData = journey ?? MOCK_JOURNEY;

  const healthyCount = useMemo(
    () => agents.filter((a) => a.status === "healthy").length,
    [agents]
  );
  const degradedCount = useMemo(
    () => agents.filter((a) => a.status === "degraded").length,
    [agents]
  );

  // ── Render ──────────────────────────────────────────────

  return (
    <div className="space-y-6" role="main" aria-label="Mission Control Dashboard">
      {/* ── Header ──────────────────────────────────────────── */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-400 bg-clip-text text-transparent">
              Mission Control
            </span>
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time operations center
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-refresh indicator */}
          <div
            className="flex items-center gap-2 text-xs text-gray-400"
            aria-live="polite"
            aria-label="Live data auto-refreshing"
          >
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
            <span>Auto-refreshing</span>
          </div>
          <Badge
            className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 px-2.5 py-0.5
                       font-semibold text-xs uppercase tracking-wider"
          >
            <Radio className="h-3 w-3 mr-1 animate-pulse" aria-hidden="true" />
            Live
          </Badge>
          {/* Agent health summary */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-500 border-l border-gray-800 pl-3 ml-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
            <span>{healthyCount} healthy</span>
            {degradedCount > 0 && (
              <>
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 ml-1.5" aria-hidden="true" />
                <span>{degradedCount} degraded</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ── Tabs ────────────────────────────────────────────── */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full"
      >
        <TabsList className="dark:bg-gray-900 dark:border dark:border-gray-800 w-full sm:w-auto">
          <TabsTrigger
            value="live-operations"
            className="data-[state=active]:dark:bg-indigo-500/20 data-[state=active]:dark:text-indigo-300
                       transition-all duration-200"
            aria-label="Live Operations tab"
          >
            <Activity className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Live Operations
          </TabsTrigger>
          <TabsTrigger
            value="data-provenance"
            className="data-[state=active]:dark:bg-purple-500/20 data-[state=active]:dark:text-purple-300
                       transition-all duration-200"
            aria-label="Data Provenance tab"
          >
            <Database className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Data Provenance
          </TabsTrigger>
          <TabsTrigger
            value="lead-journey"
            className="data-[state=active]:dark:bg-emerald-500/20 data-[state=active]:dark:text-emerald-300
                       transition-all duration-200"
            aria-label="Lead Journey tab"
          >
            <TrendingUp className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Lead Journey
          </TabsTrigger>
        </TabsList>

        {/* ════════════════════════════════════════════════════ */}
        {/* Tab 1: Live Operations                              */}
        {/* ════════════════════════════════════════════════════ */}
        <TabsContent value="live-operations" className="mt-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* ── Agent Heatmap Grid ── */}
            <div className="xl:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
                  <Flame className="h-5 w-5 text-orange-400" aria-hidden="true" />
                  Agent Heatmap
                </h2>
                <span className="text-xs text-gray-500">
                  {agents.length} agents monitored
                </span>
              </div>
              <div
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-2 gap-3"
                role="list"
                aria-label="Agent status cards"
              >
                {heatmapLoading
                  ? Array.from({ length: 10 }).map((_, i) => (
                      <AgentCardSkeleton key={i} />
                    ))
                  : agents.map((agent) => (
                      <div key={agent.agent_name} role="listitem">
                        <AgentCard agent={agent} />
                      </div>
                    ))}
              </div>
            </div>

            {/* ── Live Activity Feed ── */}
            <div className="xl:col-span-1">
              <Card className="dark:bg-gray-900/70 dark:border-gray-800 h-full">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base text-gray-100 flex items-center gap-2">
                      <Radio className="h-4 w-4 text-emerald-400 animate-pulse" aria-hidden="true" />
                      Live Activity Feed
                    </CardTitle>
                    <span className="text-[10px] text-gray-500 flex items-center gap-1">
                      <RefreshCw className="h-3 w-3" aria-hidden="true" />
                      5s interval
                    </span>
                  </div>
                  <CardDescription className="text-xs text-gray-500">
                    Real-time agent execution stream
                  </CardDescription>
                </CardHeader>
                <CardContent
                  className="max-h-[680px] overflow-y-auto pr-1
                             scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent"
                  role="log"
                  aria-label="Live agent activity feed"
                  aria-live="polite"
                >
                  {feedLoading ? (
                    <FeedSkeleton />
                  ) : feed.length === 0 ? (
                    <p className="text-sm text-gray-500 text-center py-8">
                      No recent activity
                    </p>
                  ) : (
                    <div className="space-y-0.5">
                      {feed.map((entry) => (
                        <FeedItem key={entry.id} entry={entry} />
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ════════════════════════════════════════════════════ */}
        {/* Tab 2: Data Provenance                              */}
        {/* ════════════════════════════════════════════════════ */}
        <TabsContent value="data-provenance" className="mt-6">
          <div className="space-y-6">
            {/* Top Row: Pie + Coverage Stats */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Source Breakdown Pie */}
              <Card className="dark:bg-gray-900/70 dark:border-gray-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base text-gray-100">
                    Source Breakdown
                  </CardTitle>
                  <CardDescription className="text-xs text-gray-500">
                    Lead origins across {formatNumber(prov.total_leads)} total leads
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {provenanceLoading ? (
                    <div className="h-64 bg-gray-800/30 rounded-lg animate-pulse" />
                  ) : (
                    <div className="flex flex-col items-center">
                      <ResponsiveContainer width="100%" height={260}>
                        <PieChart>
                          <Pie
                            data={prov.sources}
                            dataKey="count"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={65}
                            outerRadius={105}
                            paddingAngle={3}
                            strokeWidth={0}
                          >
                            {prov.sources.map((source, i) => (
                              <Cell key={i} fill={source.color} />
                            ))}
                          </Pie>
                          <Tooltip content={<PieTooltipContent />} />
                        </PieChart>
                      </ResponsiveContainer>
                      {/* Legend */}
                      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 mt-2">
                        {prov.sources.map((source) => (
                          <div key={source.name} className="flex items-center gap-1.5 text-xs">
                            <span
                              className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                              style={{ background: source.color }}
                            />
                            <span className="text-gray-400">{source.name}</span>
                            <span className="text-gray-600 font-mono">
                              {formatNumber(source.count)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Enrichment Coverage Stats */}
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-gray-200">
                  Enrichment Coverage
                </h2>
                <div className="grid grid-cols-2 gap-3">
                  <CoverageStatCard
                    label="Enriched"
                    value={prov.enriched_pct}
                    icon={Sparkles}
                    color="bg-indigo-500/10 text-indigo-400"
                  />
                  <CoverageStatCard
                    label="Phone Verified"
                    value={prov.phone_verified_pct}
                    icon={Phone}
                    color="bg-purple-500/10 text-purple-400"
                  />
                  <CoverageStatCard
                    label="Email Verified"
                    value={prov.email_verified_pct}
                    icon={Mail}
                    color="bg-emerald-500/10 text-emerald-400"
                  />
                  <CoverageStatCard
                    label="CRM Synced"
                    value={prov.crm_synced_pct}
                    icon={Database}
                    color="bg-amber-500/10 text-amber-400"
                  />
                </div>

                {/* Summary Table */}
                <Card className="dark:bg-gray-900/70 dark:border-gray-800">
                  <CardContent className="p-4">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-gray-800">
                          <TableHead className="text-gray-400 text-xs">Metric</TableHead>
                          <TableHead className="text-gray-400 text-xs text-right">Coverage</TableHead>
                          <TableHead className="text-gray-400 text-xs text-right">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {[
                          { metric: "Data Enrichment", value: prov.enriched_pct },
                          { metric: "Phone Verification", value: prov.phone_verified_pct },
                          { metric: "Email Verification", value: prov.email_verified_pct },
                          { metric: "CRM Sync", value: prov.crm_synced_pct },
                        ].map((row) => (
                          <TableRow key={row.metric} className="border-gray-800/50">
                            <TableCell className="text-sm text-gray-300 py-2">
                              {row.metric}
                            </TableCell>
                            <TableCell className="text-sm text-gray-200 font-semibold text-right py-2">
                              {row.value.toFixed(1)}%
                            </TableCell>
                            <TableCell className="text-right py-2">
                              <Badge
                                variant="outline"
                                className={`text-[10px] border ${
                                  row.value >= 85
                                    ? "border-emerald-500/30 text-emerald-400"
                                    : row.value >= 60
                                    ? "border-amber-500/30 text-amber-400"
                                    : "border-red-500/30 text-red-400"
                                }`}
                              >
                                {row.value >= 85 ? "Good" : row.value >= 60 ? "Fair" : "Low"}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* Provenance Search */}
            <Card className="dark:bg-gray-900/70 dark:border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-gray-100">
                  Provenance Search
                </CardTitle>
                <CardDescription className="text-xs text-gray-500">
                  Look up a lead by email to view their data provenance timeline
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search
                      className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500"
                      aria-hidden="true"
                    />
                    <Input
                      type="email"
                      placeholder="Enter lead email address..."
                      className="pl-10 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-200
                                 dark:placeholder:text-gray-500"
                      value={provenanceSearch}
                      onChange={(e) => {
                        setProvenanceSearch(e.target.value);
                        setSearchSubmitted(false);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleProvenanceSearch();
                      }}
                      aria-label="Search lead by email"
                    />
                  </div>
                  <Button
                    onClick={handleProvenanceSearch}
                    className="dark:bg-indigo-600 dark:hover:bg-indigo-700 dark:text-white"
                    aria-label="Search provenance"
                  >
                    <Search className="h-4 w-4 mr-1.5" aria-hidden="true" />
                    Search
                  </Button>
                </div>

                {/* Timeline Results */}
                {searchSubmitted && provenanceSearch.length > 0 && (
                  <div className="mt-4">
                    {timelineLoading || timelineFetching ? (
                      <div className="flex items-center gap-2 text-sm text-gray-400 py-6 justify-center">
                        <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Searching provenance data...
                      </div>
                    ) : provenanceTimeline && provenanceTimeline.length > 0 ? (
                      <div className="bg-gray-800/30 rounded-lg p-4">
                        <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                          <FileText className="h-4 w-4 text-indigo-400" aria-hidden="true" />
                          Provenance Timeline for{" "}
                          <span className="text-indigo-400 font-mono">{provenanceSearch}</span>
                        </h3>
                        <ProvenanceTimeline events={provenanceTimeline} />
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-6">
                        No provenance data found for this email.
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ════════════════════════════════════════════════════ */}
        {/* Tab 3: Lead Journey                                 */}
        {/* ════════════════════════════════════════════════════ */}
        <TabsContent value="lead-journey" className="mt-6">
          <div className="space-y-6">
            {/* Funnel Chart */}
            <Card className="dark:bg-gray-900/70 dark:border-gray-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-gray-100 flex items-center gap-2">
                  <Target className="h-5 w-5 text-blue-400" aria-hidden="true" />
                  Lead Journey Funnel
                </CardTitle>
                <CardDescription className="text-xs text-gray-500">
                  Discovery through Engagement pipeline — conversion at each stage
                </CardDescription>
              </CardHeader>
              <CardContent>
                {journeyLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 7 }).map((_, i) => (
                      <div key={i} className="flex items-center gap-4">
                        <div className="w-24 h-4 bg-gray-700/30 rounded animate-pulse" />
                        <div
                          className="h-10 bg-gray-700/30 rounded-lg animate-pulse"
                          style={{ width: `${100 - i * 12}%` }}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <FunnelChart stages={journeyData.funnel} />
                )}
              </CardContent>
            </Card>

            {/* Active Sequences + Positive Signals */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Sequences */}
              <div>
                <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                  <Send className="h-5 w-5 text-indigo-400" aria-hidden="true" />
                  Active Sequences
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {journeyLoading
                    ? Array.from({ length: 4 }).map((_, i) => (
                        <Card key={i} className="dark:bg-gray-900/60 dark:border-gray-800 animate-pulse">
                          <CardContent className="p-4">
                            <div className="h-4 w-32 bg-gray-700/50 rounded mb-3" />
                            <div className="h-3 w-20 bg-gray-700/30 rounded mb-3" />
                            <div className="h-1.5 w-full bg-gray-700/30 rounded" />
                          </CardContent>
                        </Card>
                      ))
                    : journeyData.active_sequences.map((seq) => (
                        <SequenceCard key={seq.id} seq={seq} />
                      ))}
                </div>
              </div>

              {/* Recent Positive Signals */}
              <Card className="dark:bg-gray-900/70 dark:border-gray-800">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base text-gray-100 flex items-center gap-2">
                    <Trophy className="h-5 w-5 text-amber-400" aria-hidden="true" />
                    Recent Positive Signals
                  </CardTitle>
                  <CardDescription className="text-xs text-gray-500">
                    Opens, replies, and meetings booked
                  </CardDescription>
                </CardHeader>
                <CardContent
                  className="max-h-[420px] overflow-y-auto
                             scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent"
                  role="feed"
                  aria-label="Positive engagement signals"
                >
                  {journeyLoading ? (
                    <div className="space-y-3">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="flex items-start gap-3 animate-pulse">
                          <div className="w-8 h-8 bg-gray-700/50 rounded-md" />
                          <div className="flex-1 space-y-1.5">
                            <div className="h-3.5 w-32 bg-gray-700/50 rounded" />
                            <div className="h-3 w-48 bg-gray-700/30 rounded" />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : journeyData.positive_signals.length === 0 ? (
                    <p className="text-sm text-gray-500 text-center py-8">
                      No positive signals yet
                    </p>
                  ) : (
                    journeyData.positive_signals.map((signal) => (
                      <SignalItem key={signal.id} signal={signal} />
                    ))
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Journey Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                {
                  label: "Total Discovered",
                  value: formatNumber(journeyData.funnel[0]?.count ?? 0),
                  icon: Users,
                  color: "bg-blue-500/10 text-blue-400",
                },
                {
                  label: "Currently Engaged",
                  value: formatNumber(journeyData.funnel[3]?.count ?? 0),
                  icon: Activity,
                  color: "bg-teal-500/10 text-teal-400",
                },
                {
                  label: "Meetings Booked",
                  value: formatNumber(journeyData.funnel[5]?.count ?? 0),
                  icon: Calendar,
                  color: "bg-purple-500/10 text-purple-400",
                },
                {
                  label: "Deals Won",
                  value: formatNumber(journeyData.funnel[6]?.count ?? 0),
                  icon: Trophy,
                  color: "bg-amber-500/10 text-amber-400",
                },
              ].map((stat) => (
                <Card key={stat.label} className="dark:bg-gray-900/70 dark:border-gray-800">
                  <CardContent className="p-4 flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${stat.color}`}>
                      <stat.icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-xl font-bold text-gray-100">{stat.value}</p>
                      <p className="text-[11px] text-gray-500">{stat.label}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
