"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ShieldAlert,
  Users,
  DollarSign,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  Play,
  CheckCircle,
  Clock,
  Target,
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
  PieChart,
  Pie,
  Cell,
  Tooltip as RTooltip,
  Legend,
} from "recharts";
import api from "@/lib/api";

// ── Types ────────────────────────────────────────────────

interface ChurnPrediction {
  account_id: string;
  company_name: string;
  churn_probability: number;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  contributing_factors: string[];
  recommended_actions: string[];
  revenue_at_risk: number;
  last_engagement_date: string | null;
}

interface RetentionWorkflow {
  workflow_id: string;
  account_id: string;
  company_name: string;
  status: "active" | "completed" | "paused";
  steps_total: number;
  steps_completed: number;
  success_probability: number;
}

interface ChurnPredictionsResponse {
  total_customers: number;
  at_risk_count: number;
  high_risk_count: number;
  total_revenue_at_risk: number;
  risk_distribution: {
    CRITICAL: number;
    HIGH: number;
    MEDIUM: number;
    LOW: number;
  };
  predictions: ChurnPrediction[];
  retention_workflows: RetentionWorkflow[];
}

// ── Constants ────────────────────────────────────────────

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#22c55e",
};

const RISK_BADGE_CLASSES: Record<string, string> = {
  CRITICAL:
    "bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/20",
  HIGH:
    "bg-orange-500/20 text-orange-400 border-orange-500/30 hover:bg-orange-500/20",
  MEDIUM:
    "bg-yellow-500/20 text-yellow-400 border-yellow-500/30 hover:bg-yellow-500/20",
  LOW:
    "bg-green-500/20 text-green-400 border-green-500/30 hover:bg-green-500/20",
};

// ── Mock fallback (used when API is not yet wired) ──────

const MOCK_DATA: ChurnPredictionsResponse = {
  total_customers: 1248,
  at_risk_count: 87,
  high_risk_count: 23,
  total_revenue_at_risk: 2340000,
  risk_distribution: { CRITICAL: 8, HIGH: 15, MEDIUM: 34, LOW: 30 },
  predictions: [
    {
      account_id: "acc-001",
      company_name: "TechVision Corp",
      churn_probability: 0.89,
      risk_level: "CRITICAL",
      contributing_factors: [
        "No login in 45 days",
        "Support tickets up 300%",
        "Contract renewal in 30 days",
        "Champion left company",
      ],
      recommended_actions: [
        "Schedule executive check-in",
        "Offer dedicated CSM",
        "Propose custom renewal terms",
      ],
      revenue_at_risk: 480000,
      last_engagement_date: "2026-02-11",
    },
    {
      account_id: "acc-002",
      company_name: "DataStream Analytics",
      churn_probability: 0.76,
      risk_level: "HIGH",
      contributing_factors: [
        "Usage dropped 60%",
        "Missed last QBR",
        "Billing dispute pending",
      ],
      recommended_actions: [
        "Trigger re-engagement sequence",
        "Resolve billing issue",
        "Share ROI report",
      ],
      revenue_at_risk: 320000,
      last_engagement_date: "2026-02-28",
    },
    {
      account_id: "acc-003",
      company_name: "CloudFirst Solutions",
      churn_probability: 0.62,
      risk_level: "HIGH",
      contributing_factors: [
        "Evaluated competitor product",
        "Feature requests unresolved",
      ],
      recommended_actions: [
        "Product roadmap walkthrough",
        "Escalate feature requests to PM",
      ],
      revenue_at_risk: 210000,
      last_engagement_date: "2026-03-05",
    },
    {
      account_id: "acc-004",
      company_name: "NetSecure Inc",
      churn_probability: 0.45,
      risk_level: "MEDIUM",
      contributing_factors: [
        "Slow onboarding progress",
        "Low feature adoption",
      ],
      recommended_actions: [
        "Assign onboarding specialist",
        "Schedule training session",
      ],
      revenue_at_risk: 150000,
      last_engagement_date: "2026-03-15",
    },
    {
      account_id: "acc-005",
      company_name: "GrowthMetrics AI",
      churn_probability: 0.22,
      risk_level: "LOW",
      contributing_factors: ["Slight usage dip last month"],
      recommended_actions: ["Monitor engagement", "Send feature highlights"],
      revenue_at_risk: 95000,
      last_engagement_date: "2026-03-20",
    },
  ],
  retention_workflows: [
    {
      workflow_id: "wf-001",
      account_id: "acc-001",
      company_name: "TechVision Corp",
      status: "active",
      steps_total: 5,
      steps_completed: 2,
      success_probability: 0.35,
    },
    {
      workflow_id: "wf-002",
      account_id: "acc-002",
      company_name: "DataStream Analytics",
      status: "active",
      steps_total: 4,
      steps_completed: 1,
      success_probability: 0.48,
    },
    {
      workflow_id: "wf-003",
      account_id: "acc-006",
      company_name: "SaaS Metrics Pro",
      status: "completed",
      steps_total: 3,
      steps_completed: 3,
      success_probability: 0.92,
    },
  ],
};

// ── Helpers ──────────────────────────────────────────────

function formatCurrency(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
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

export default function ChurnDetectionPage() {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["churn-predictions"],
    queryFn: async () => {
      try {
        const res = await api.get<ChurnPredictionsResponse>(
          "/insights/churn/predictions"
        );
        return res.data;
      } catch {
        return MOCK_DATA;
      }
    },
  });

  const predictions = data?.predictions ?? [];
  const workflows = data?.retention_workflows ?? [];

  const pieData = data
    ? [
        { name: "Critical", value: data.risk_distribution.CRITICAL },
        { name: "High", value: data.risk_distribution.HIGH },
        { name: "Medium", value: data.risk_distribution.MEDIUM },
        { name: "Low", value: data.risk_distribution.LOW },
      ]
    : [];

  const pieColors = ["#ef4444", "#f97316", "#eab308", "#22c55e"];

  const activeWorkflows = workflows.filter((w) => w.status === "active");
  const completedWorkflows = workflows.filter((w) => w.status === "completed");
  const avgSuccess =
    workflows.length > 0
      ? workflows.reduce((sum, w) => sum + w.success_probability, 0) /
        workflows.length
      : 0;

  return (
    <div className="space-y-6" role="main" aria-label="Churn Detection Dashboard">
      {/* ── Header ──────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-semibold dark:text-gray-100">
          Churn Detection &amp; Retention
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Identify at-risk accounts and trigger retention workflows before it is
          too late. Reducing churn by 5% can increase profits by 25-95%.
        </p>
      </div>

      {/* ── Summary Cards ───────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatSkeleton key={i} />
          ))}
        </div>
      ) : error && !data ? (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-8 text-center text-red-500 text-sm">
            Failed to load churn data. Please try again.
          </CardContent>
        </Card>
      ) : data ? (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
          role="region"
          aria-label="Churn summary metrics"
        >
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <Users className="h-4 w-4 text-blue-500" aria-hidden="true" />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Total Customers
                </p>
              </div>
              <p className="text-2xl font-bold dark:text-gray-100">
                {data.total_customers.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle
                  className="h-4 w-4 text-orange-500"
                  aria-hidden="true"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  At-Risk Accounts
                </p>
              </div>
              <p className="text-2xl font-bold text-orange-500">
                {data.at_risk_count}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                {((data.at_risk_count / data.total_customers) * 100).toFixed(1)}
                % of total
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <ShieldAlert
                  className="h-4 w-4 text-red-500"
                  aria-hidden="true"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  High Risk
                </p>
              </div>
              <p className="text-2xl font-bold text-red-500">
                {data.high_risk_count}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Immediate attention needed
              </p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign
                  className="h-4 w-4 text-yellow-500"
                  aria-hidden="true"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Revenue at Risk
                </p>
              </div>
              <p className="text-2xl font-bold dark:text-gray-100">
                {formatCurrency(data.total_revenue_at_risk)}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Across at-risk accounts
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Risk Distribution Chart ─────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="Risk distribution chart"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              Risk Distribution
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Account risk level breakdown
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <ChartSkeleton />
            ) : pieData.length === 0 ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-sm text-gray-400">No risk data available.</p>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="45%"
                      outerRadius={80}
                      innerRadius={40}
                      paddingAngle={2}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      labelLine={{ stroke: "#9ca3af", strokeWidth: 1 }}
                    >
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={pieColors[i]} />
                      ))}
                    </Pie>
                    <RTooltip
                      formatter={(value: number, name: string) => [
                        `${value} accounts`,
                        name,
                      ]}
                      contentStyle={{
                        borderRadius: 8,
                        fontSize: 12,
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        color: "#e5e7eb",
                      }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      iconType="circle"
                      formatter={(value: string) => (
                        <span className="text-sm text-gray-600 dark:text-gray-300">
                          {value}
                        </span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Retention Workflow Panel ────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="Retention workflows"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              Retention Workflows
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Active retention campaigns
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <p className="text-lg font-bold text-blue-400">
                  {activeWorkflows.length}
                </p>
                <p className="text-xs text-gray-400">Active</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                <p className="text-lg font-bold text-green-400">
                  {completedWorkflows.length}
                </p>
                <p className="text-xs text-gray-400">Completed</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                <p className="text-lg font-bold text-purple-400">
                  {(avgSuccess * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-gray-400">Avg Success</p>
              </div>
            </div>

            <div className="space-y-3" role="list" aria-label="Workflow list">
              {workflows.map((wf) => (
                <div
                  key={wf.workflow_id}
                  className="p-3 rounded-lg border border-gray-700 bg-gray-800/50 space-y-2"
                  role="listitem"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium dark:text-gray-200">
                      {wf.company_name}
                    </span>
                    <Badge
                      variant="outline"
                      className={
                        wf.status === "active"
                          ? "bg-blue-500/20 text-blue-400 border-blue-500/30"
                          : wf.status === "completed"
                            ? "bg-green-500/20 text-green-400 border-green-500/30"
                            : "bg-gray-500/20 text-gray-400 border-gray-500/30"
                      }
                    >
                      {wf.status === "active" && (
                        <Play
                          className="h-3 w-3 mr-1"
                          aria-hidden="true"
                        />
                      )}
                      {wf.status === "completed" && (
                        <CheckCircle
                          className="h-3 w-3 mr-1"
                          aria-hidden="true"
                        />
                      )}
                      {wf.status === "paused" && (
                        <Clock
                          className="h-3 w-3 mr-1"
                          aria-hidden="true"
                        />
                      )}
                      {wf.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>
                      {wf.steps_completed}/{wf.steps_total} steps
                    </span>
                    <span className="text-gray-600">|</span>
                    <span>
                      {(wf.success_probability * 100).toFixed(0)}% success
                      likelihood
                    </span>
                  </div>
                  <Progress
                    value={(wf.steps_completed / wf.steps_total) * 100}
                    className="h-1.5"
                    aria-label={`Workflow progress: ${wf.steps_completed} of ${wf.steps_total} steps`}
                  />
                </div>
              ))}
              {workflows.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-4">
                  No retention workflows active.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* ── Impact Calculator ───────────────────────── */}
        <Card
          className="dark:bg-gray-900 dark:border-gray-800"
          role="region"
          aria-label="Churn impact calculator"
        >
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">
              Impact Calculator
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              Why churn reduction matters
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-pink-500/10 border border-blue-500/20">
              <div className="flex items-start gap-3">
                <Target
                  className="h-5 w-5 text-blue-400 mt-0.5 shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-sm font-medium text-blue-300">
                    Reducing churn by 5% can increase profits by 25-95%
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Based on Harvard Business Review research on customer
                    retention economics
                  </p>
                </div>
              </div>
            </div>

            {data && (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50">
                  <span className="text-sm text-gray-400">
                    Current revenue at risk
                  </span>
                  <span className="text-sm font-semibold text-red-400">
                    {formatCurrency(data.total_revenue_at_risk)}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50">
                  <span className="text-sm text-gray-400">
                    If 5% churn prevented
                  </span>
                  <span className="text-sm font-semibold text-green-400">
                    {formatCurrency(data.total_revenue_at_risk * 0.05)} saved
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-lg border border-gray-700 bg-gray-800/50">
                  <span className="text-sm text-gray-400">
                    Potential profit impact
                  </span>
                  <span className="text-sm font-semibold bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">
                    {formatCurrency(data.total_revenue_at_risk * 0.05 * 0.25)} -{" "}
                    {formatCurrency(data.total_revenue_at_risk * 0.05 * 0.95)}
                  </span>
                </div>
              </div>
            )}

            <div className="p-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5">
              <div className="flex items-start gap-2">
                <TrendingDown
                  className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0"
                  aria-hidden="true"
                />
                <p className="text-xs text-yellow-400/80">
                  Acquiring new customers costs 5-25x more than retaining
                  existing ones. Focus on retention for maximum ROI.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── At-Risk Accounts Table ───────────────────── */}
      <Card
        className="dark:bg-gray-900 dark:border-gray-800"
        role="region"
        aria-label="At-risk accounts table"
      >
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">
            At-Risk Accounts
          </CardTitle>
          <CardDescription className="dark:text-gray-400">
            Accounts ranked by churn probability with recommended interventions
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 bg-gray-100 dark:bg-gray-800 rounded animate-pulse"
                />
              ))}
            </div>
          ) : predictions.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">
              No at-risk accounts detected.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company</TableHead>
                  <TableHead>Churn Probability</TableHead>
                  <TableHead>Risk Level</TableHead>
                  <TableHead>Revenue at Risk</TableHead>
                  <TableHead className="text-center">Details</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {predictions.map((p) => {
                  const isExpanded = expandedRow === p.account_id;
                  return (
                    <>
                      <TableRow key={p.account_id}>
                        <TableCell className="font-medium dark:text-gray-200">
                          {p.company_name}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2 min-w-[140px]">
                            <Progress
                              value={p.churn_probability * 100}
                              className="h-2 flex-1"
                              aria-label={`Churn probability: ${(p.churn_probability * 100).toFixed(0)}%`}
                            />
                            <span className="text-xs font-mono text-gray-400 w-10 text-right">
                              {(p.churn_probability * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              RISK_BADGE_CLASSES[p.risk_level] ?? ""
                            }
                          >
                            {p.risk_level}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium text-red-400">
                          {formatCurrency(p.revenue_at_risk)}
                        </TableCell>
                        <TableCell className="text-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setExpandedRow(isExpanded ? null : p.account_id)
                            }
                            aria-expanded={isExpanded}
                            aria-label={`${isExpanded ? "Collapse" : "Expand"} details for ${p.company_name}`}
                          >
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white"
                            aria-label={`Trigger retention workflow for ${p.company_name}`}
                          >
                            Trigger Retention
                          </Button>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${p.account_id}-expanded`}>
                          <TableCell colSpan={6} className="bg-gray-800/30">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-2">
                              <div>
                                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                                  Contributing Factors
                                </p>
                                <ul
                                  className="space-y-1"
                                  role="list"
                                  aria-label={`Contributing factors for ${p.company_name}`}
                                >
                                  {p.contributing_factors.map((f, i) => (
                                    <li
                                      key={i}
                                      className="flex items-start gap-2 text-sm text-gray-300"
                                    >
                                      <AlertTriangle className="h-3 w-3 text-yellow-500 mt-1 shrink-0" />
                                      {f}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                              <div>
                                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                                  Recommended Actions
                                </p>
                                <ul
                                  className="space-y-1"
                                  role="list"
                                  aria-label={`Recommended actions for ${p.company_name}`}
                                >
                                  {p.recommended_actions.map((a, i) => (
                                    <li
                                      key={i}
                                      className="flex items-start gap-2 text-sm text-gray-300"
                                    >
                                      <CheckCircle className="h-3 w-3 text-green-500 mt-1 shrink-0" />
                                      {a}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                              {p.last_engagement_date && (
                                <div className="md:col-span-2">
                                  <p className="text-xs text-gray-500">
                                    Last engagement:{" "}
                                    {new Date(
                                      p.last_engagement_date
                                    ).toLocaleDateString("en-US", {
                                      year: "numeric",
                                      month: "short",
                                      day: "numeric",
                                    })}
                                  </p>
                                </div>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
