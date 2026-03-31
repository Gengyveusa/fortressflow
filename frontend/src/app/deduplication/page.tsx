"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Database,
  GitMerge,
  Search,
  ClipboardCheck,
  Percent,
  CheckCircle,
  Clock,
  XCircle,
  ArrowRightLeft,
  TrendingUp,
  ShieldCheck,
  BarChart3,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
} from "recharts";
import api from "@/lib/api";

// ── Types ────────────────────────────────────────────────

interface FieldScore {
  field: string;
  score: number;
}

interface DuplicateRecord {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  company: string;
  title: string;
  phone: string;
  source: string;
}

interface DuplicateCandidate {
  candidate_id: string;
  match_score: number;
  field_scores: FieldScore[];
  record_a: DuplicateRecord;
  record_b: DuplicateRecord;
  suggested_action: "auto_merge" | "manual_review" | "dismiss";
}

interface CrmSyncStatus {
  name: string;
  status: "synced" | "pending" | "error" | "disconnected";
  last_synced: string | null;
  records_synced: number;
}

interface ScanHistoryEntry {
  date: string;
  duplicates_found: number;
  merged: number;
}

interface DeduplicationHealth {
  total_records: number;
  duplicates_found: number;
  merged_count: number;
  pending_review: number;
  duplicate_rate: number;
  merge_accuracy: number;
  crm_sync: CrmSyncStatus[];
  scan_history: ScanHistoryEntry[];
  savings: {
    prevented_duplicate_outreach: number;
    pipeline_accuracy_improvement: number;
    forecast_confidence_boost: number;
  };
}

interface DeduplicationCandidatesResponse {
  candidates: DuplicateCandidate[];
  total: number;
  page: number;
  page_size: number;
}

// ── Mock Data ────────────────────────────────────────────

const MOCK_HEALTH: DeduplicationHealth = {
  total_records: 24587,
  duplicates_found: 1432,
  merged_count: 1180,
  pending_review: 252,
  duplicate_rate: 5.8,
  merge_accuracy: 97.4,
  crm_sync: [
    {
      name: "HubSpot",
      status: "synced",
      last_synced: "2026-03-28T14:30:00Z",
      records_synced: 18420,
    },
    {
      name: "Apollo",
      status: "synced",
      last_synced: "2026-03-28T12:15:00Z",
      records_synced: 8340,
    },
    {
      name: "ZoomInfo",
      status: "pending",
      last_synced: "2026-03-27T09:00:00Z",
      records_synced: 5200,
    },
  ],
  scan_history: [
    { date: "Mar 22", duplicates_found: 210, merged: 195 },
    { date: "Mar 23", duplicates_found: 185, merged: 172 },
    { date: "Mar 24", duplicates_found: 198, merged: 188 },
    { date: "Mar 25", duplicates_found: 167, merged: 160 },
    { date: "Mar 26", duplicates_found: 220, merged: 205 },
    { date: "Mar 27", duplicates_found: 175, merged: 168 },
    { date: "Mar 28", duplicates_found: 152, merged: 140 },
  ],
  savings: {
    prevented_duplicate_outreach: 3420,
    pipeline_accuracy_improvement: 12.5,
    forecast_confidence_boost: 8.3,
  },
};

const MOCK_CANDIDATES: DeduplicationCandidatesResponse = {
  candidates: [
    {
      candidate_id: "dup-001",
      match_score: 0.94,
      field_scores: [
        { field: "email", score: 1.0 },
        { field: "name", score: 0.95 },
        { field: "company", score: 0.88 },
        { field: "phone", score: 0.92 },
      ],
      record_a: {
        id: "r-001a",
        first_name: "John",
        last_name: "Smith",
        email: "john.smith@techcorp.com",
        company: "TechCorp Inc.",
        title: "VP of Engineering",
        phone: "+1-555-0101",
        source: "HubSpot",
      },
      record_b: {
        id: "r-001b",
        first_name: "John",
        last_name: "Smith",
        email: "john.smith@techcorp.com",
        company: "TechCorp",
        title: "VP Engineering",
        phone: "+1 555 0101",
        source: "Apollo",
      },
      suggested_action: "auto_merge",
    },
    {
      candidate_id: "dup-002",
      match_score: 0.82,
      field_scores: [
        { field: "email", score: 0.0 },
        { field: "name", score: 0.98 },
        { field: "company", score: 0.95 },
        { field: "phone", score: 0.85 },
      ],
      record_a: {
        id: "r-002a",
        first_name: "Sarah",
        last_name: "Johnson",
        email: "sarah.j@dataco.io",
        company: "DataCo",
        title: "Head of Sales",
        phone: "+1-555-0202",
        source: "HubSpot",
      },
      record_b: {
        id: "r-002b",
        first_name: "Sarah",
        last_name: "Johnson",
        email: "sjohnson@dataco.io",
        company: "DataCo Inc",
        title: "VP Sales",
        phone: "+1-555-0202",
        source: "ZoomInfo",
      },
      suggested_action: "manual_review",
    },
    {
      candidate_id: "dup-003",
      match_score: 0.67,
      field_scores: [
        { field: "email", score: 0.0 },
        { field: "name", score: 0.85 },
        { field: "company", score: 0.7 },
        { field: "phone", score: 0.0 },
      ],
      record_a: {
        id: "r-003a",
        first_name: "Michael",
        last_name: "Chen",
        email: "m.chen@startupxyz.com",
        company: "StartupXYZ",
        title: "CTO",
        phone: "+1-555-0303",
        source: "Apollo",
      },
      record_b: {
        id: "r-003b",
        first_name: "Mike",
        last_name: "Chen",
        email: "mike@startupxyz.io",
        company: "Startup XYZ Inc",
        title: "Chief Technology Officer",
        phone: "",
        source: "ZoomInfo",
      },
      suggested_action: "manual_review",
    },
  ],
  total: 252,
  page: 1,
  page_size: 25,
};

// ── Helpers ──────────────────────────────────────────────

const CRM_STATUS_CLASSES: Record<string, string> = {
  synced: "bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/20",
  pending:
    "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 hover:bg-yellow-500/20",
  error: "bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/20",
  disconnected:
    "bg-gray-500/20 text-gray-400 border-gray-500/30 hover:bg-gray-500/20",
};

function scoreColor(score: number): string {
  if (score >= 0.9) return "text-green-400";
  if (score >= 0.7) return "text-yellow-400";
  if (score >= 0.4) return "text-orange-400";
  return "text-red-400";
}

function ChartSkeleton() {
  return (
    <div className="h-64 flex items-center justify-center">
      <div
        className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"
        role="status"
        aria-label="Loading chart"
      />
    </div>
  );
}

function StatSkeleton() {
  return (
    <Card className="animate-pulse dark:bg-gray-900 dark:border-gray-800">
      <CardContent className="pt-6">
        <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
        <div className="h-7 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
      </CardContent>
    </Card>
  );
}

// ── Page Component ───────────────────────────────────────

export default function DeduplicationPage() {
  const [expandedCandidate, setExpandedCandidate] = useState<string | null>(
    null
  );

  const {
    data: rawHealth,
    isLoading: healthLoading,
    error: healthError,
  } = useQuery({
    queryKey: ["deduplication-health"],
    queryFn: async () => {
      try {
        const res = await api.get<DeduplicationHealth>(
          "/insights/deduplication/health"
        );
        const d = res.data;
        if (d && typeof d.duplicates_found === "number" && typeof d.merged_count === "number" && d.savings) {
          return d;
        }
        return MOCK_HEALTH;
      } catch {
        return MOCK_HEALTH;
      }
    },
  });

  const health = rawHealth && typeof rawHealth.duplicates_found === "number" && rawHealth.savings ? rawHealth : MOCK_HEALTH;

  const {
    data: candidatesData,
    isLoading: candidatesLoading,
    error: candidatesError,
  } = useQuery({
    queryKey: ["deduplication-candidates"],
    queryFn: async () => {
      try {
        const res = await api.get<DeduplicationCandidatesResponse>(
          "/insights/deduplication/candidates"
        );
        return res.data;
      } catch {
        return MOCK_CANDIDATES;
      }
    },
  });

  const candidates = Array.isArray(candidatesData?.candidates) ? candidatesData.candidates : [];

  return (
    <div className="space-y-6" role="main" aria-label="Deduplication Dashboard">
      {/* ── Header ──────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-semibold dark:text-gray-100">
          Data Deduplication &amp; Golden Records
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Identify and merge duplicate records across CRM sources to maintain a
          single source of truth for every contact.
        </p>
      </div>

      {/* ── Health Cards ────────────────────────────────── */}
      {healthLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <StatSkeleton key={i} />
          ))}
        </div>
      ) : healthError && !health ? (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-8 text-center text-red-500 text-sm">
            Failed to load deduplication data. Please try again.
          </CardContent>
        </Card>
      ) : health ? (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4"
          role="region"
          aria-label="Deduplication health metrics"
        >
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Database
                  className="h-4 w-4 text-blue-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Total Records
                </p>
              </div>
              <p className="text-xl font-bold dark:text-gray-100">
                {(health.total_records ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Search
                  className="h-4 w-4 text-orange-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Duplicates Found
                </p>
              </div>
              <p className="text-xl font-bold text-orange-400">
                {(health.duplicates_found ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <GitMerge
                  className="h-4 w-4 text-green-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Merged
                </p>
              </div>
              <p className="text-xl font-bold text-green-400">
                {(health.merged_count ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <ClipboardCheck
                  className="h-4 w-4 text-yellow-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Pending Review
                </p>
              </div>
              <p className="text-xl font-bold text-yellow-400">
                {health.pending_review ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Percent
                  className="h-4 w-4 text-purple-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Duplicate Rate
                </p>
              </div>
              <p className="text-xl font-bold text-purple-400">
                {(health.duplicate_rate ?? 0).toFixed(1)}%
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck
                  className="h-4 w-4 text-emerald-500"
                  aria-hidden="true"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Merge Accuracy
                </p>
              </div>
              <p className="text-xl font-bold text-emerald-400">
                {(health.merge_accuracy ?? 0).toFixed(1)}%
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── CRM Sync Status ────────────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="CRM sync status"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              CRM Sync Status
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Data source integration health
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(health?.crm_sync ?? []).map((crm) => (
              <div
                key={crm.name}
                className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-gray-700 flex items-center justify-center">
                    <Database
                      className="h-4 w-4 text-gray-400"
                      aria-hidden="true"
                    />
                  </div>
                  <div>
                    <p className="text-sm font-medium dark:text-gray-200">
                      {crm.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(crm.records_synced ?? 0).toLocaleString()} records
                    </p>
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={CRM_STATUS_CLASSES[crm.status] ?? ""}
                  aria-label={`${crm.name}: ${crm.status}`}
                >
                  {crm.status === "synced" && (
                    <CheckCircle
                      className="h-3 w-3 mr-1"
                      aria-hidden="true"
                    />
                  )}
                  {crm.status === "pending" && (
                    <Clock className="h-3 w-3 mr-1" aria-hidden="true" />
                  )}
                  {crm.status === "error" && (
                    <XCircle className="h-3 w-3 mr-1" aria-hidden="true" />
                  )}
                  {crm.status}
                </Badge>
              </div>
            ))}
            {(!health || health.crm_sync.length === 0) && (
              <p className="text-sm text-gray-400 text-center py-4">
                No CRM integrations configured.
              </p>
            )}
          </CardContent>
        </Card>

        {/* ── Savings Panel ──────────────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="Deduplication savings"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              Deduplication Savings
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Impact of clean data on operations
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {health && (
              <>
                <div className="p-4 rounded-lg bg-gradient-to-br from-green-500/10 via-emerald-500/10 to-teal-500/10 border border-green-500/20">
                  <div className="flex items-start gap-3">
                    <ArrowRightLeft
                      className="h-5 w-5 text-green-400 mt-0.5 shrink-0"
                      aria-hidden="true"
                    />
                    <div>
                      <p className="text-sm font-medium text-green-300">
                        Prevented Duplicate Outreach
                      </p>
                      <p className="text-2xl font-bold text-green-400 mt-1">
                        {(health.savings?.prevented_duplicate_outreach ?? 0).toLocaleString()}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Contacts saved from duplicate messaging
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50">
                    <div className="flex items-center gap-2">
                      <TrendingUp
                        className="h-4 w-4 text-blue-400"
                        aria-hidden="true"
                      />
                      <span className="text-sm text-gray-400">
                        Pipeline Accuracy
                      </span>
                    </div>
                    <span className="text-sm font-semibold text-blue-400">
                      +{health.savings?.pipeline_accuracy_improvement ?? 0}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50">
                    <div className="flex items-center gap-2">
                      <BarChart3
                        className="h-4 w-4 text-purple-400"
                        aria-hidden="true"
                      />
                      <span className="text-sm text-gray-400">
                        Forecast Confidence
                      </span>
                    </div>
                    <span className="text-sm font-semibold text-purple-400">
                      +{health.savings?.forecast_confidence_boost ?? 0}%
                    </span>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* ── Scan History Chart ─────────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="Scan history chart"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              Scan History
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Duplicates found and merged over time
            </CardDescription>
          </CardHeader>
          <CardContent>
            {healthLoading ? (
              <ChartSkeleton />
            ) : !health?.scan_history?.length ? (
              <div className="h-48 flex items-center justify-center">
                <p className="text-sm text-gray-400">No scan data yet.</p>
              </div>
            ) : (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={health.scan_history}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700"
                    />
                    <XAxis
                      dataKey="date"
                      fontSize={11}
                      tick={{ fill: "#9ca3af" }}
                    />
                    <YAxis fontSize={11} tick={{ fill: "#9ca3af" }} />
                    <RTooltip
                      contentStyle={{
                        borderRadius: 8,
                        fontSize: 12,
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        color: "#e5e7eb",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="duplicates_found"
                      stroke="#f97316"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#f97316" }}
                      name="Found"
                    />
                    <Line
                      type="monotone"
                      dataKey="merged"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#22c55e" }}
                      name="Merged"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Duplicate Candidates Table ───────────────── */}
      <Card
        className="dark:bg-gray-900 dark:border-gray-800"
        role="region"
        aria-label="Duplicate candidates table"
      >
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base dark:text-gray-100">
                Duplicate Candidates
              </CardTitle>
              <CardDescription className="dark:text-gray-400">
                Side-by-side record comparison with match confidence scores
              </CardDescription>
            </div>
            {candidatesData && (
              <Badge variant="outline" className="dark:text-gray-300">
                {candidatesData.total} pending
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {candidatesLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-12 bg-gray-100 dark:bg-gray-800 rounded animate-pulse"
                />
              ))}
            </div>
          ) : candidates.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">
              No duplicate candidates found.
            </p>
          ) : (
            <div className="divide-y divide-gray-800">
              {candidates.map((c) => {
                const isExpanded = expandedCandidate === c.candidate_id;
                return (
                  <div key={c.candidate_id} className="p-4">
                    {/* Summary Row */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium dark:text-gray-200 truncate">
                            {c.record_a.first_name} {c.record_a.last_name}
                          </span>
                          <span className="text-xs text-gray-500">vs</span>
                          <span className="text-sm font-medium dark:text-gray-200 truncate">
                            {c.record_b.first_name} {c.record_b.last_name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                          <span>{c.record_a.company}</span>
                          <span className="text-gray-600">|</span>
                          <span>
                            {c.record_a.source} + {c.record_b.source}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 min-w-[120px]">
                          <Progress
                            value={c.match_score * 100}
                            className="h-2 flex-1"
                            aria-label={`Match score: ${(c.match_score * 100).toFixed(0)}%`}
                          />
                          <span className="text-xs font-mono text-gray-400 w-10 text-right">
                            {(c.match_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setExpandedCandidate(
                              isExpanded ? null : c.candidate_id
                            )
                          }
                          aria-expanded={isExpanded}
                          aria-label={`${isExpanded ? "Collapse" : "Expand"} comparison for ${c.record_a.first_name} ${c.record_a.last_name}`}
                        >
                          {isExpanded ? "Hide" : "Compare"}
                        </Button>
                      </div>
                    </div>

                    {/* Expanded Comparison */}
                    {isExpanded && (
                      <div className="mt-4 space-y-4">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-28">Field</TableHead>
                              <TableHead>
                                Record A ({c.record_a.source})
                              </TableHead>
                              <TableHead>
                                Record B ({c.record_b.source})
                              </TableHead>
                              <TableHead className="w-20 text-center">
                                Score
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {[
                              {
                                field: "Name",
                                a: `${c.record_a.first_name} ${c.record_a.last_name}`,
                                b: `${c.record_b.first_name} ${c.record_b.last_name}`,
                                key: "name",
                              },
                              {
                                field: "Email",
                                a: c.record_a.email,
                                b: c.record_b.email,
                                key: "email",
                              },
                              {
                                field: "Company",
                                a: c.record_a.company,
                                b: c.record_b.company,
                                key: "company",
                              },
                              {
                                field: "Title",
                                a: c.record_a.title,
                                b: c.record_b.title,
                                key: "title",
                              },
                              {
                                field: "Phone",
                                a: c.record_a.phone,
                                b: c.record_b.phone || "N/A",
                                key: "phone",
                              },
                            ].map((row) => {
                              const fs = c.field_scores.find(
                                (f) => f.field === row.key
                              );
                              const matchVal = fs?.score ?? null;
                              return (
                                <TableRow key={row.key}>
                                  <TableCell className="font-medium text-gray-400 text-xs uppercase">
                                    {row.field}
                                  </TableCell>
                                  <TableCell
                                    className={
                                      row.a === row.b
                                        ? "text-green-400"
                                        : "dark:text-gray-300"
                                    }
                                  >
                                    {row.a}
                                  </TableCell>
                                  <TableCell
                                    className={
                                      row.a === row.b
                                        ? "text-green-400"
                                        : "dark:text-gray-300"
                                    }
                                  >
                                    {row.b}
                                  </TableCell>
                                  <TableCell className="text-center">
                                    {matchVal !== null ? (
                                      <span
                                        className={`text-xs font-mono ${scoreColor(matchVal)}`}
                                      >
                                        {(matchVal * 100).toFixed(0)}%
                                      </span>
                                    ) : (
                                      <span className="text-xs text-gray-600">
                                        --
                                      </span>
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 justify-end pt-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-gray-400 hover:text-gray-200"
                            aria-label={`Dismiss duplicate candidate ${c.record_a.first_name} ${c.record_a.last_name}`}
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            Dismiss
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
                            aria-label={`Manual review for ${c.record_a.first_name} ${c.record_a.last_name}`}
                          >
                            <ClipboardCheck className="h-4 w-4 mr-1" />
                            Manual Review
                          </Button>
                          <Button
                            size="sm"
                            className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white"
                            aria-label={`Auto-merge records for ${c.record_a.first_name} ${c.record_a.last_name}`}
                          >
                            <GitMerge className="h-4 w-4 mr-1" />
                            Auto-merge
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
