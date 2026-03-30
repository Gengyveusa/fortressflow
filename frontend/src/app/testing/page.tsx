"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  TestTube2,
  HeartPulse,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
  Stethoscope,
  Wrench,
  Bot,
  Brain,
  Mail,
  Phone,
  Search,
  Share2,
  Megaphone,
  DollarSign,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  RefreshCw,
  Zap,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────

interface AgentHealth {
  agent_name: string;
  status: "healthy" | "unconfigured" | "failing";
  action_count: number;
  configured: boolean;
  last_check: string;
  error_summary?: string;
}

interface FailingAction {
  agent: string;
  action: string;
  failure_count: number;
  error_category: "auth" | "timeout" | "validation" | "rate_limit" | "config" | "unknown";
  latest_error: string;
  last_failure: string;
}

interface DiagnosticRun {
  id: string;
  run_type: "health_check" | "full_diagnostic" | "integration_test";
  status: "running" | "passed" | "failed" | "partial";
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  started_at: string;
  completed_at: string | null;
  triggered_by: string;
}

interface FixSuggestion {
  id: string;
  agent: string;
  action: string;
  severity: "critical" | "warning" | "info";
  diagnosis: string;
  suggested_fix: string;
  auto_fixable: boolean;
  status: "pending" | "approved" | "rejected" | "applied";
  created_at: string;
}

interface IntegrationTestResult {
  workflow_name: string;
  status: "passed" | "failed" | "skipped";
  steps: {
    name: string;
    status: "passed" | "failed" | "skipped";
    duration_ms: number;
    error?: string;
  }[];
  duration_ms: number;
  tested_at: string;
}

// ── Mock Data ──────────────────────────────────────────────

const MOCK_AGENTS: AgentHealth[] = [
  { agent_name: "groq", status: "healthy", action_count: 8, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "openai", status: "healthy", action_count: 12, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "hubspot", status: "healthy", action_count: 15, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "zoominfo", status: "unconfigured", action_count: 6, configured: false, last_check: "2026-03-29T14:22:00Z", error_summary: "API key not set" },
  { agent_name: "twilio", status: "healthy", action_count: 5, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "apollo", status: "failing", action_count: 9, configured: true, last_check: "2026-03-29T14:22:00Z", error_summary: "Rate limit exceeded" },
  { agent_name: "taplio", status: "unconfigured", action_count: 4, configured: false, last_check: "2026-03-29T14:22:00Z", error_summary: "API key not set" },
  { agent_name: "marketing", status: "healthy", action_count: 11, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "sales", status: "healthy", action_count: 14, configured: true, last_check: "2026-03-29T14:22:00Z" },
  { agent_name: "testing", status: "healthy", action_count: 7, configured: true, last_check: "2026-03-29T14:22:00Z" },
];

const MOCK_FAILURES: FailingAction[] = [
  { agent: "apollo", action: "enrich_contact", failure_count: 47, error_category: "rate_limit", latest_error: "429 Too Many Requests: Rate limit exceeded. Retry after 60s.", last_failure: "2026-03-29T14:18:32Z" },
  { agent: "apollo", action: "search_people", failure_count: 23, error_category: "rate_limit", latest_error: "429 Too Many Requests: Daily quota exhausted.", last_failure: "2026-03-29T14:15:10Z" },
  { agent: "zoominfo", action: "get_company_info", failure_count: 15, error_category: "config", latest_error: "ZoomInfo API key is not configured. Set ZOOMINFO_API_KEY in environment.", last_failure: "2026-03-29T13:50:00Z" },
  { agent: "hubspot", action: "create_deal", failure_count: 8, error_category: "validation", latest_error: "Required field 'pipeline' is missing in deal creation payload.", last_failure: "2026-03-29T12:45:00Z" },
  { agent: "openai", action: "generate_email", failure_count: 3, error_category: "timeout", latest_error: "Request timed out after 30000ms. Model gpt-4o may be experiencing high latency.", last_failure: "2026-03-29T11:30:00Z" },
];

const MOCK_RUNS: DiagnosticRun[] = [
  { id: "run-001", run_type: "health_check", status: "passed", total_checks: 10, passed_checks: 8, failed_checks: 2, started_at: "2026-03-29T14:22:00Z", completed_at: "2026-03-29T14:22:04Z", triggered_by: "scheduler" },
  { id: "run-002", run_type: "full_diagnostic", status: "failed", total_checks: 48, passed_checks: 41, failed_checks: 7, started_at: "2026-03-29T12:00:00Z", completed_at: "2026-03-29T12:01:23Z", triggered_by: "manual" },
  { id: "run-003", run_type: "integration_test", status: "partial", total_checks: 12, passed_checks: 9, failed_checks: 3, started_at: "2026-03-29T08:00:00Z", completed_at: "2026-03-29T08:02:10Z", triggered_by: "scheduler" },
  { id: "run-004", run_type: "health_check", status: "passed", total_checks: 10, passed_checks: 10, failed_checks: 0, started_at: "2026-03-28T14:22:00Z", completed_at: "2026-03-28T14:22:03Z", triggered_by: "scheduler" },
  { id: "run-005", run_type: "full_diagnostic", status: "passed", total_checks: 48, passed_checks: 48, failed_checks: 0, started_at: "2026-03-28T08:00:00Z", completed_at: "2026-03-28T08:01:15Z", triggered_by: "scheduler" },
];

const MOCK_SUGGESTIONS: FixSuggestion[] = [
  {
    id: "fix-001",
    agent: "apollo",
    action: "enrich_contact",
    severity: "critical",
    diagnosis: "Apollo API rate limit is being hit consistently. Current usage pattern sends 50+ requests per minute, but the API limit is 30/min.",
    suggested_fix: "Implement request throttling with a 2-second delay between Apollo API calls. Add exponential backoff on 429 responses.",
    auto_fixable: false,
    status: "pending",
    created_at: "2026-03-29T14:22:05Z",
  },
  {
    id: "fix-002",
    agent: "zoominfo",
    action: "get_company_info",
    severity: "warning",
    diagnosis: "ZoomInfo integration is not configured. The ZOOMINFO_API_KEY environment variable is missing.",
    suggested_fix: "Add ZoomInfo API key via Settings > API Keys page. The agent will automatically reconnect once configured.",
    auto_fixable: false,
    status: "pending",
    created_at: "2026-03-29T14:22:05Z",
  },
  {
    id: "fix-003",
    agent: "hubspot",
    action: "create_deal",
    severity: "warning",
    diagnosis: "Deal creation calls are missing the required 'pipeline' field. This appears to be a schema change in the HubSpot API.",
    suggested_fix: "Update the deal creation payload to include the default pipeline ID. Auto-fix can add 'pipeline': 'default' to all create_deal calls.",
    auto_fixable: true,
    status: "pending",
    created_at: "2026-03-29T12:45:10Z",
  },
  {
    id: "fix-004",
    agent: "openai",
    action: "generate_email",
    severity: "info",
    diagnosis: "Occasional timeouts on GPT-4o requests during peak hours (11am-2pm EST). Latency increases from ~5s to 30s+.",
    suggested_fix: "Add fallback to GPT-4o-mini for time-sensitive operations. Implement a 15s timeout with automatic model downgrade.",
    auto_fixable: true,
    status: "pending",
    created_at: "2026-03-29T11:35:00Z",
  },
];

const MOCK_INTEGRATION_TESTS: IntegrationTestResult[] = [
  {
    workflow_name: "Lead Enrichment Pipeline",
    status: "failed",
    steps: [
      { name: "Create test lead", status: "passed", duration_ms: 120 },
      { name: "Enrich via Apollo", status: "failed", duration_ms: 5200, error: "Rate limit exceeded (429)" },
      { name: "Enrich via ZoomInfo", status: "skipped", duration_ms: 0 },
      { name: "Update HubSpot contact", status: "skipped", duration_ms: 0 },
    ],
    duration_ms: 5320,
    tested_at: "2026-03-29T08:00:30Z",
  },
  {
    workflow_name: "Email Sequence Execution",
    status: "passed",
    steps: [
      { name: "Generate email content", status: "passed", duration_ms: 3400 },
      { name: "Compliance check", status: "passed", duration_ms: 85 },
      { name: "Send via Twilio SendGrid", status: "passed", duration_ms: 450 },
      { name: "Log delivery event", status: "passed", duration_ms: 30 },
    ],
    duration_ms: 3965,
    tested_at: "2026-03-29T08:01:00Z",
  },
  {
    workflow_name: "Deal Stage Progression",
    status: "passed",
    steps: [
      { name: "Fetch deal from HubSpot", status: "passed", duration_ms: 280 },
      { name: "Evaluate stage criteria", status: "passed", duration_ms: 15 },
      { name: "Update deal stage", status: "passed", duration_ms: 310 },
      { name: "Notify sales agent", status: "passed", duration_ms: 95 },
    ],
    duration_ms: 700,
    tested_at: "2026-03-29T08:01:30Z",
  },
  {
    workflow_name: "SMS Consent & Outreach",
    status: "passed",
    steps: [
      { name: "Verify SMS consent", status: "passed", duration_ms: 45 },
      { name: "Generate SMS content", status: "passed", duration_ms: 1200 },
      { name: "Send via Twilio", status: "passed", duration_ms: 380 },
      { name: "Record touch event", status: "passed", duration_ms: 25 },
    ],
    duration_ms: 1650,
    tested_at: "2026-03-29T08:02:00Z",
  },
];

// ── Agent Icon Map ─────────────────────────────────────────

const AGENT_ICONS: Record<string, React.ElementType> = {
  groq: Zap,
  openai: Brain,
  hubspot: Share2,
  zoominfo: Search,
  twilio: Phone,
  apollo: Search,
  taplio: Share2,
  marketing: Megaphone,
  sales: DollarSign,
  testing: TestTube2,
};

// ── Helpers ────────────────────────────────────────────────

function statusBadge(status: "healthy" | "unconfigured" | "failing") {
  const map = {
    healthy: { label: "Healthy", classes: "bg-emerald-900/40 text-emerald-400 border-emerald-700" },
    unconfigured: { label: "Unconfigured", classes: "bg-yellow-900/40 text-yellow-400 border-yellow-700" },
    failing: { label: "Failing", classes: "bg-red-900/40 text-red-400 border-red-700" },
  };
  const s = map[status];
  return (
    <Badge variant="outline" className={s.classes}>
      {s.label}
    </Badge>
  );
}

function errorCategoryBadge(cat: FailingAction["error_category"]) {
  const map: Record<string, { label: string; classes: string }> = {
    auth: { label: "Auth", classes: "bg-red-900/40 text-red-400 border-red-700" },
    timeout: { label: "Timeout", classes: "bg-orange-900/40 text-orange-400 border-orange-700" },
    validation: { label: "Validation", classes: "bg-blue-900/40 text-blue-400 border-blue-700" },
    rate_limit: { label: "Rate Limit", classes: "bg-yellow-900/40 text-yellow-400 border-yellow-700" },
    config: { label: "Config", classes: "bg-purple-900/40 text-purple-400 border-purple-700" },
    unknown: { label: "Unknown", classes: "bg-gray-700/40 text-gray-400 border-gray-600" },
  };
  const s = map[cat] ?? map.unknown;
  return (
    <Badge variant="outline" className={s.classes}>
      {s.label}
    </Badge>
  );
}

function severityBadge(severity: "critical" | "warning" | "info") {
  const map = {
    critical: { label: "Critical", classes: "bg-red-900/40 text-red-400 border-red-700" },
    warning: { label: "Warning", classes: "bg-yellow-900/40 text-yellow-400 border-yellow-700" },
    info: { label: "Info", classes: "bg-blue-900/40 text-blue-400 border-blue-700" },
  };
  const s = map[severity];
  return (
    <Badge variant="outline" className={s.classes}>
      {s.label}
    </Badge>
  );
}

function runStatusBadge(status: DiagnosticRun["status"]) {
  const map = {
    running: { label: "Running", classes: "bg-blue-900/40 text-blue-400 border-blue-700", icon: RefreshCw },
    passed: { label: "Passed", classes: "bg-emerald-900/40 text-emerald-400 border-emerald-700", icon: CheckCircle2 },
    failed: { label: "Failed", classes: "bg-red-900/40 text-red-400 border-red-700", icon: XCircle },
    partial: { label: "Partial", classes: "bg-yellow-900/40 text-yellow-400 border-yellow-700", icon: AlertTriangle },
  };
  const s = map[status];
  const Icon = s.icon;
  return (
    <Badge variant="outline" className={`${s.classes} flex items-center gap-1 w-fit`}>
      <Icon className="w-3 h-3" aria-hidden="true" />
      {s.label}
    </Badge>
  );
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function runTypeLabel(type: DiagnosticRun["run_type"]) {
  const map = {
    health_check: "Health Check",
    full_diagnostic: "Full Diagnostic",
    integration_test: "Integration Test",
  };
  return map[type];
}

function truncate(text: string, max: number) {
  return text.length > max ? text.slice(0, max) + "..." : text;
}

// ── Agent Health Card ──────────────────────────────────────

function AgentCard({ agent }: { agent: AgentHealth }) {
  const Icon = AGENT_ICONS[agent.agent_name] ?? Bot;
  const statusDot = {
    healthy: "bg-emerald-500",
    unconfigured: "bg-yellow-500",
    failing: "bg-red-500",
  }[agent.status];

  return (
    <Card
      className="dark:bg-gray-900 dark:border-gray-800 hover:border-gray-600 transition-colors"
      role="listitem"
      aria-label={`${agent.agent_name} agent status: ${agent.status}`}
    >
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-gray-800 border border-gray-700">
              <Icon className="w-4 h-4 text-gray-300" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-100 capitalize">{agent.agent_name}</p>
              <p className="text-xs text-gray-500">{agent.action_count} actions</p>
            </div>
          </div>
          <div className={`w-2.5 h-2.5 rounded-full ${statusDot}`} aria-hidden="true" />
        </div>
        <div className="flex items-center justify-between">
          {statusBadge(agent.status)}
          {agent.configured ? (
            <span className="text-xs text-emerald-500 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
              Configured
            </span>
          ) : (
            <span className="text-xs text-yellow-500 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" aria-hidden="true" />
              Not configured
            </span>
          )}
        </div>
        {agent.error_summary && (
          <p className="text-xs text-gray-500 truncate" title={agent.error_summary}>
            {agent.error_summary}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Integration Test Expandable Row ────────────────────────

function IntegrationTestRow({ test }: { test: IntegrationTestResult }) {
  const [expanded, setExpanded] = useState(false);
  const statusColor = {
    passed: "text-emerald-400",
    failed: "text-red-400",
    skipped: "text-gray-500",
  };

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-800/50 transition-colors text-left"
        aria-expanded={expanded}
        aria-label={`${test.workflow_name}: ${test.status}`}
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" aria-hidden="true" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" aria-hidden="true" />
          )}
          <span className="text-sm font-medium text-gray-100">{test.workflow_name}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-500">{test.duration_ms}ms</span>
          <span className={`text-xs font-medium ${statusColor[test.status]}`}>
            {test.status.toUpperCase()}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-gray-800 bg-gray-900/50 p-4 space-y-2">
          {test.steps.map((step, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                {step.status === "passed" && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />}
                {step.status === "failed" && <XCircle className="w-3.5 h-3.5 text-red-500" aria-hidden="true" />}
                {step.status === "skipped" && <Clock className="w-3.5 h-3.5 text-gray-600" aria-hidden="true" />}
                <span className="text-gray-300">{step.name}</span>
              </div>
              <div className="flex items-center gap-3">
                {step.error && (
                  <span className="text-red-400 max-w-[300px] truncate" title={step.error}>{step.error}</span>
                )}
                <span className="text-gray-600 tabular-nums w-16 text-right">
                  {step.duration_ms > 0 ? `${step.duration_ms}ms` : "--"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page Component ────────────────────────────────────

export default function TestingPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("health");

  // Fetch with mock fallbacks -- endpoints require auth, so we use mock data for now
  const { data: agents } = useQuery<AgentHealth[]>({
    queryKey: ["testing", "health"],
    queryFn: async () => {
      try {
        const res = await api.get("/testing/health");
        return res.data;
      } catch {
        return MOCK_AGENTS;
      }
    },
    initialData: MOCK_AGENTS,
  });

  const { data: failures } = useQuery<FailingAction[]>({
    queryKey: ["testing", "failures"],
    queryFn: async () => {
      try {
        const res = await api.get("/testing/failures");
        return res.data;
      } catch {
        return MOCK_FAILURES;
      }
    },
    initialData: MOCK_FAILURES,
  });

  const { data: runs } = useQuery<DiagnosticRun[]>({
    queryKey: ["testing", "runs"],
    queryFn: async () => {
      try {
        const res = await api.get("/testing/runs");
        return res.data;
      } catch {
        return MOCK_RUNS;
      }
    },
    initialData: MOCK_RUNS,
  });

  const { data: suggestions } = useQuery<FixSuggestion[]>({
    queryKey: ["testing", "suggestions"],
    queryFn: async () => {
      try {
        const res = await api.get("/testing/suggestions");
        return res.data;
      } catch {
        return MOCK_SUGGESTIONS;
      }
    },
    initialData: MOCK_SUGGESTIONS,
  });

  // Derived stats
  const healthyCount = agents.filter((a) => a.status === "healthy").length;
  const failingCount = agents.filter((a) => a.status === "failing").length;
  const unconfiguredCount = agents.filter((a) => a.status === "unconfigured").length;
  const totalFailures = failures.reduce((sum, f) => sum + f.failure_count, 0);
  const pendingSuggestions = suggestions.filter((s) => s.status === "pending").length;

  return (
    <div className="space-y-6" role="main" aria-label="Agent Testing and Diagnostics dashboard">
      {/* ── Header ──────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold dark:text-gray-100 flex items-center gap-2">
            <TestTube2 className="w-6 h-6 text-violet-400" aria-hidden="true" />
            Agent Testing &amp; Diagnostics
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Monitor agent health, diagnose failures, and approve automated fixes.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            variant="outline"
            className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            aria-label="Run health check on all agents"
          >
            <HeartPulse className="w-4 h-4 mr-1.5" aria-hidden="true" />
            Run Health Check
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            aria-label="Run full diagnostic on all agents"
          >
            <Stethoscope className="w-4 h-4 mr-1.5" aria-hidden="true" />
            Run Full Diagnostic
          </Button>
          <Button
            size="sm"
            className="bg-violet-600 hover:bg-violet-700 text-white"
            aria-label="Run integration tests"
          >
            <Play className="w-4 h-4 mr-1.5" aria-hidden="true" />
            Run Integration Test
          </Button>
        </div>
      </div>

      {/* ── Summary Stats ───────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4" role="list" aria-label="Testing summary statistics">
        <Card className="dark:bg-gray-900 dark:border-gray-800" role="listitem" aria-label="Healthy agents">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-emerald-900/30">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Healthy</p>
              <p className="text-lg font-semibold text-gray-100">{healthyCount}/{agents.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800" role="listitem" aria-label="Failing agents">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-red-900/30">
              <XCircle className="w-5 h-5 text-red-400" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Failing</p>
              <p className="text-lg font-semibold text-gray-100">{failingCount}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800" role="listitem" aria-label="Total recent failures">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-orange-900/30">
              <AlertTriangle className="w-5 h-5 text-orange-400" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Failures</p>
              <p className="text-lg font-semibold text-gray-100">{totalFailures}</p>
            </div>
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800" role="listitem" aria-label="Pending fix suggestions">
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-violet-900/30">
              <Lightbulb className="w-5 h-5 text-violet-400" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide">Pending Fixes</p>
              <p className="text-lg font-semibold text-gray-100">{pendingSuggestions}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Tabs ────────────────────────────────────────── */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="dark:bg-gray-800 dark:border-gray-700">
          <TabsTrigger value="health" className="text-xs sm:text-sm">Agent Health</TabsTrigger>
          <TabsTrigger value="failures" className="text-xs sm:text-sm">Recent Failures</TabsTrigger>
          <TabsTrigger value="runs" className="text-xs sm:text-sm">Diagnostic Runs</TabsTrigger>
          <TabsTrigger value="suggestions" className="text-xs sm:text-sm">Fix Suggestions</TabsTrigger>
          <TabsTrigger value="integration" className="text-xs sm:text-sm">Integration Tests</TabsTrigger>
        </TabsList>

        {/* ── Agent Health Matrix ──────────────────────── */}
        <TabsContent value="health" className="mt-4">
          <div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4"
            role="list"
            aria-label="Agent health matrix"
          >
            {agents.map((agent) => (
              <AgentCard key={agent.agent_name} agent={agent} />
            ))}
          </div>
        </TabsContent>

        {/* ── Recent Failures ──────────────────────────── */}
        <TabsContent value="failures" className="mt-4">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-400" aria-hidden="true" />
                Top Failing Actions
              </CardTitle>
              <CardDescription className="dark:text-gray-500">
                Most frequent failures across all agents in the last 24 hours.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table aria-label="Recent failure details">
                <TableHeader>
                  <TableRow className="dark:border-gray-800">
                    <TableHead className="dark:text-gray-400">Action</TableHead>
                    <TableHead className="dark:text-gray-400 text-right">Failures</TableHead>
                    <TableHead className="dark:text-gray-400">Category</TableHead>
                    <TableHead className="dark:text-gray-400">Latest Error</TableHead>
                    <TableHead className="dark:text-gray-400 text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {failures.map((f, i) => (
                    <TableRow key={i} className="dark:border-gray-800">
                      <TableCell className="font-medium text-gray-200">
                        <span className="text-gray-500">{f.agent}.</span>{f.action}
                      </TableCell>
                      <TableCell className="text-right text-gray-300 tabular-nums">{f.failure_count}</TableCell>
                      <TableCell>{errorCategoryBadge(f.error_category)}</TableCell>
                      <TableCell className="max-w-[300px]">
                        <span className="text-xs text-gray-400 block truncate" title={f.latest_error}>
                          {truncate(f.latest_error, 80)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs dark:text-violet-400 dark:hover:text-violet-300 dark:hover:bg-gray-800"
                          aria-label={`Diagnose ${f.agent}.${f.action}`}
                        >
                          <Stethoscope className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                          Diagnose
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Diagnostic Runs ──────────────────────────── */}
        <TabsContent value="runs" className="mt-4">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-blue-400" aria-hidden="true" />
                Recent Diagnostic Runs
              </CardTitle>
              <CardDescription className="dark:text-gray-500">
                History of health checks, diagnostics, and integration test runs.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table aria-label="Diagnostic run history">
                <TableHeader>
                  <TableRow className="dark:border-gray-800">
                    <TableHead className="dark:text-gray-400">Run ID</TableHead>
                    <TableHead className="dark:text-gray-400">Type</TableHead>
                    <TableHead className="dark:text-gray-400">Status</TableHead>
                    <TableHead className="dark:text-gray-400 text-right">Passed</TableHead>
                    <TableHead className="dark:text-gray-400 text-right">Failed</TableHead>
                    <TableHead className="dark:text-gray-400">Started</TableHead>
                    <TableHead className="dark:text-gray-400">Triggered By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id} className="dark:border-gray-800">
                      <TableCell className="font-mono text-xs text-gray-400">{run.id}</TableCell>
                      <TableCell className="text-gray-300 text-sm">{runTypeLabel(run.run_type)}</TableCell>
                      <TableCell>{runStatusBadge(run.status)}</TableCell>
                      <TableCell className="text-right text-emerald-400 tabular-nums">{run.passed_checks}</TableCell>
                      <TableCell className="text-right text-red-400 tabular-nums">{run.failed_checks}</TableCell>
                      <TableCell className="text-gray-400 text-xs">{formatTime(run.started_at)}</TableCell>
                      <TableCell className="text-gray-500 text-xs capitalize">{run.triggered_by}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Fix Suggestions ──────────────────────────── */}
        <TabsContent value="suggestions" className="mt-4">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <Wrench className="w-4 h-4 text-violet-400" aria-hidden="true" />
                Fix Suggestions
              </CardTitle>
              <CardDescription className="dark:text-gray-500">
                AI-generated fixes awaiting approval. Review and approve or reject each suggestion.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {suggestions.filter((s) => s.status === "pending").map((suggestion) => (
                <div
                  key={suggestion.id}
                  className="border border-gray-800 rounded-lg p-4 space-y-3"
                  role="article"
                  aria-label={`Fix suggestion for ${suggestion.agent}.${suggestion.action}`}
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      {severityBadge(suggestion.severity)}
                      <span className="text-sm font-medium text-gray-200">
                        <span className="text-gray-500">{suggestion.agent}.</span>{suggestion.action}
                      </span>
                      {suggestion.auto_fixable && (
                        <Badge variant="outline" className="bg-violet-900/30 text-violet-400 border-violet-700 text-[10px]">
                          Auto-fixable
                        </Badge>
                      )}
                    </div>
                    <span className="text-xs text-gray-600">{formatTime(suggestion.created_at)}</span>
                  </div>

                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Diagnosis</p>
                      <p className="text-sm text-gray-300">{suggestion.diagnosis}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Suggested Fix</p>
                      <p className="text-sm text-gray-300">{suggestion.suggested_fix}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                      aria-label={`Approve fix for ${suggestion.agent}.${suggestion.action}`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 text-xs"
                      aria-label={`Reject fix for ${suggestion.agent}.${suggestion.action}`}
                    >
                      <XCircle className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
              {suggestions.filter((s) => s.status === "pending").length === 0 && (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No pending fix suggestions. All systems are running smoothly.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Integration Tests ────────────────────────── */}
        <TabsContent value="integration" className="mt-4">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                Integration Test Results
              </CardTitle>
              <CardDescription className="dark:text-gray-500">
                End-to-end workflow tests. Click to expand and see step-by-step results.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Summary bar */}
              <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />
                  {MOCK_INTEGRATION_TESTS.filter((t) => t.status === "passed").length} passed
                </span>
                <span className="flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5 text-red-500" aria-hidden="true" />
                  {MOCK_INTEGRATION_TESTS.filter((t) => t.status === "failed").length} failed
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-gray-600" aria-hidden="true" />
                  {MOCK_INTEGRATION_TESTS.filter((t) => t.status === "skipped").length} skipped
                </span>
              </div>

              {MOCK_INTEGRATION_TESTS.map((test, i) => (
                <IntegrationTestRow key={i} test={test} />
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
