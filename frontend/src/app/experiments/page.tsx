"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  Legend,
} from "recharts";
import {
  FlaskConical,
  Beaker,
  TrendingUp,
  Target,
  AlertTriangle,
  CheckCircle2,
  BarChart3,
  Activity,
  Zap,
  ShieldAlert,
  ThumbsUp,
  Play,
  Gauge,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────

interface Variant {
  id: string;
  name: string;
  description: string;
  pulls: number;
  avg_reward: number;
  confidence: number;
  is_best: boolean;
  is_high_risk: boolean;
  risk_reason?: string;
  cumulative_reward: number;
  conversion_rate: number;
}

interface RewardHistoryEntry {
  step: number;
  exploitation: number;
  exploration: number;
  cumulative: number;
}

interface SafetyAlert {
  variant_id: string;
  variant_name: string;
  alert_type: "high_risk" | "degrading" | "anomaly";
  message: string;
  severity: "warning" | "critical";
  requires_approval: boolean;
}

interface ExperimentSummary {
  total_experiments: number;
  active_experiments: number;
  total_pulls: number;
  best_variant: string;
  strategy: string;
  exploration_rate: number;
  exploitation_rate: number;
  variants: Variant[];
  reward_history: RewardHistoryEntry[];
  safety_alerts: SafetyAlert[];
  experiment_name: string;
  started_at: string;
}

// ── Mock Data ───────────────────────────────────────────────

const MOCK_DATA: ExperimentSummary = {
  total_experiments: 12,
  active_experiments: 3,
  total_pulls: 48250,
  best_variant: "Variant B - Personalized Subject",
  strategy: "Thompson Sampling",
  exploration_rate: 0.18,
  exploitation_rate: 0.82,
  experiment_name: "Q1 Email Campaign Optimization",
  started_at: "2026-02-01T00:00:00Z",
  variants: [
    {
      id: "v1",
      name: "Control - Standard Template",
      description: "Original email template with generic subject line",
      pulls: 15200,
      avg_reward: 0.042,
      confidence: 0.91,
      is_best: false,
      is_high_risk: false,
      cumulative_reward: 638.4,
      conversion_rate: 0.042,
    },
    {
      id: "v2",
      name: "Variant A - Urgency CTA",
      description: "Modified CTA with urgency language and countdown timer",
      pulls: 12800,
      avg_reward: 0.058,
      confidence: 0.87,
      is_best: false,
      is_high_risk: false,
      cumulative_reward: 742.4,
      conversion_rate: 0.058,
    },
    {
      id: "v3",
      name: "Variant B - Personalized Subject",
      description: "AI-personalized subject line with recipient name and company",
      pulls: 16100,
      avg_reward: 0.073,
      confidence: 0.95,
      is_best: true,
      is_high_risk: false,
      cumulative_reward: 1175.3,
      conversion_rate: 0.073,
    },
    {
      id: "v4",
      name: "Variant C - Short Form",
      description: "Condensed email body with single clear CTA",
      pulls: 4150,
      avg_reward: 0.031,
      confidence: 0.62,
      is_best: false,
      is_high_risk: true,
      risk_reason: "Below-threshold performance after 4000+ pulls. May be degrading user experience.",
      cumulative_reward: 128.65,
      conversion_rate: 0.031,
    },
  ],
  reward_history: Array.from({ length: 30 }, (_, i) => ({
    step: i + 1,
    exploitation: 0.03 + Math.random() * 0.04 + i * 0.001,
    exploration: 0.02 + Math.random() * 0.03,
    cumulative: 0.03 + i * 0.0015 + Math.random() * 0.005,
  })),
  safety_alerts: [
    {
      variant_id: "v4",
      variant_name: "Variant C - Short Form",
      alert_type: "degrading",
      message: "Conversion rate has declined 40% over the last 500 pulls. Recommend pausing this variant.",
      severity: "warning",
      requires_approval: true,
    },
  ],
};

// ── Chart Skeleton ──────────────────────────────────────────

function ChartSkeleton() {
  return (
    <div className="h-64 flex items-center justify-center">
      <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ── Summary Stat Card ───────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent: string;
}) {
  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800" role="listitem" aria-label={label}>
      <CardContent className="p-4 flex items-center gap-4">
        <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${accent}`}>
          <Icon className="w-5 h-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide">{label}</p>
          <p className="text-lg font-semibold text-gray-100">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Exploration / Exploitation Gauge ────────────────────────

function ExplorationGauge({
  explorationRate,
  exploitationRate,
}: {
  explorationRate: number;
  exploitationRate: number;
}) {
  const explorePercent = Math.round(explorationRate * 100);
  const exploitPercent = Math.round(exploitationRate * 100);

  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800" role="region" aria-label="Exploration vs exploitation balance">
      <CardHeader className="pb-2">
        <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
          <Gauge className="w-4 h-4 text-violet-400" aria-hidden="true" />
          Exploration vs Exploitation Balance
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Visual bar */}
        <div
          className="relative h-6 rounded-full overflow-hidden bg-gray-800 border border-gray-700"
          role="progressbar"
          aria-label="Exploitation vs exploration balance"
          aria-valuenow={exploitPercent}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-violet-600 to-violet-500 transition-all duration-500"
            style={{ width: `${exploitPercent}%` }}
          />
          <div
            className="absolute right-0 top-0 h-full bg-gradient-to-l from-amber-500 to-amber-600 transition-all duration-500"
            style={{ width: `${explorePercent}%` }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[11px] font-semibold text-white drop-shadow-md">
              {exploitPercent}% / {explorePercent}%
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-violet-500" />
            <span className="text-gray-400">Exploitation ({exploitPercent}%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span className="text-gray-400">Exploration ({explorePercent}%)</span>
          </div>
        </div>

        <p className="text-xs text-gray-500">
          The agent is currently favoring exploitation of the best-known variant while
          allocating {explorePercent}% of traffic to explore alternatives.
        </p>
      </CardContent>
    </Card>
  );
}

// ── Main Page ───────────────────────────────────────────────

export default function ExperimentsPage() {
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const { data, isLoading, error } = useQuery<ExperimentSummary>({
    queryKey: ["experiments-summary"],
    queryFn: async () => {
      try {
        const res = await api.get("/insights/experiments/summary");
        return res.data;
      } catch {
        return MOCK_DATA;
      }
    },
    staleTime: 1000 * 60 * 5,
  });

  const exp = data ?? MOCK_DATA;

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <div className="h-10 w-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-400">Loading experiment data...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-red-400">Failed to load experiment data. Please try again.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────── */}
      <section aria-label="Experiment header" className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-100 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-violet-400" />
            Campaign Experiments
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {exp.experiment_name}
          </p>
        </div>
        <Badge className="bg-violet-500/15 text-violet-300 border-violet-500/30 text-sm px-3 py-1 w-fit">
          <Beaker className="w-3.5 h-3.5 mr-1.5" aria-hidden="true" />
          {exp.strategy}
        </Badge>
      </section>

      {/* ── Summary Cards ────────────────────────────────── */}
      <section aria-label="Experiment summary statistics" role="region">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" role="list">
        <StatCard
          icon={FlaskConical}
          label="Total Experiments"
          value={exp.total_experiments}
          accent="bg-violet-500/10 text-violet-400"
        />
        <StatCard
          icon={Activity}
          label="Active"
          value={exp.active_experiments}
          accent="bg-emerald-500/10 text-emerald-400"
        />
        <StatCard
          icon={BarChart3}
          label="Total Pulls"
          value={(exp.total_pulls ?? 0).toLocaleString()}
          accent="bg-blue-500/10 text-blue-400"
        />
        <StatCard
          icon={Target}
          label="Best Variant"
          value={(exp.best_variant ?? "N/A").length > 28 ? (exp.best_variant ?? "N/A").slice(0, 26) + "..." : (exp.best_variant ?? "N/A")}
          accent="bg-amber-500/10 text-amber-400"
        />
      </div>
      </section>

      {/* ── Tabs ─────────────────────────────────────────── */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="dark:bg-gray-800/60">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="variants">Variants</TabsTrigger>
          <TabsTrigger value="safety">Safety</TabsTrigger>
        </TabsList>

        {/* ── Overview Tab ────────────────────────────────── */}
        <TabsContent value="overview" className="space-y-4">
          {/* Reward History Chart */}
          <Card className="dark:bg-gray-900 dark:border-gray-800" role="region" aria-label="Reward history">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                Reward History
              </CardTitle>
              <CardDescription>Exploitation vs exploration reward over time</CardDescription>
            </CardHeader>
            <CardContent>
              {!exp.reward_history?.length ? (
                <div className="h-64 flex items-center justify-center text-sm text-gray-500">
                  No reward history available yet.
                </div>
              ) : (
                <div className="h-80" role="img" aria-label="Reward history chart showing exploitation vs exploration reward over time">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={exp.reward_history} margin={{ top: 4, right: 8, left: -8, bottom: 4 }}>
                      <defs>
                        <linearGradient id="exploitGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="exploreGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                      <XAxis
                        dataKey="step"
                        fontSize={11}
                        tick={{ fill: "#9ca3af" }}
                        label={{ value: "Step", position: "insideBottom", offset: -2, fill: "#6b7280", fontSize: 11 }}
                      />
                      <YAxis
                        fontSize={11}
                        tick={{ fill: "#9ca3af" }}
                        tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                      />
                      <RTooltip
                        contentStyle={{
                          backgroundColor: "#1f2937",
                          border: "1px solid #374151",
                          borderRadius: 8,
                          fontSize: 12,
                          color: "#e5e7eb",
                        }}
                        formatter={(value: number, name: string) => [
                          `${(value * 100).toFixed(2)}%`,
                          name,
                        ]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                      <Area
                        type="monotone"
                        dataKey="exploitation"
                        name="Exploitation"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        fill="url(#exploitGrad)"
                      />
                      <Area
                        type="monotone"
                        dataKey="exploration"
                        name="Exploration"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        fill="url(#exploreGrad)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Gauge */}
          <ExplorationGauge
            explorationRate={exp.exploration_rate}
            exploitationRate={exp.exploitation_rate}
          />
        </TabsContent>

        {/* ── Variants Tab ────────────────────────────────── */}
        <TabsContent value="variants">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" role="list" aria-label="Experiment variants">
            {(exp.variants ?? []).map((variant) => (
              <Card
                key={variant.id}
                role="listitem"
                className={`dark:bg-gray-900 dark:border-gray-800 transition-colors ${
                  variant.is_best
                    ? "ring-1 ring-emerald-500/40 border-emerald-500/30"
                    : variant.is_high_risk
                    ? "ring-1 ring-red-500/30 border-red-500/20"
                    : ""
                } ${
                  selectedVariant === variant.id ? "ring-2 ring-violet-500/50" : ""
                }`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-sm dark:text-gray-100 flex items-center gap-2">
                        {variant.name}
                        {variant.is_best && (
                          <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-[10px]">
                            Best
                          </Badge>
                        )}
                        {variant.is_high_risk && (
                          <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-[10px]">
                            <AlertTriangle className="w-2.5 h-2.5 mr-0.5" aria-hidden="true" />
                            <span className="sr-only">Warning: </span>
                            Risk
                          </Badge>
                        )}
                      </CardTitle>
                      <CardDescription className="text-xs mt-1">
                        {variant.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Pulls */}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Pulls</span>
                    <span className="font-semibold text-gray-200">
                      {(variant.pulls ?? 0).toLocaleString()}
                    </span>
                  </div>

                  {/* Avg Reward with progress */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Avg Reward</span>
                      <span className="font-semibold text-gray-200">
                        {(variant.avg_reward * 100).toFixed(2)}%
                      </span>
                    </div>
                    <Progress
                      value={variant.avg_reward * 100}
                      max={10}
                      className="h-2"
                      aria-label={`Average reward for ${variant.name}`}
                      aria-valuenow={Math.round(variant.avg_reward * 10000) / 100}
                      aria-valuemin={0}
                      aria-valuemax={10}
                    />
                  </div>

                  {/* Confidence */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-400">Confidence</span>
                      <span
                        className={`font-semibold ${
                          variant.confidence >= 0.9
                            ? "text-emerald-400"
                            : variant.confidence >= 0.7
                            ? "text-amber-400"
                            : "text-red-400"
                        }`}
                      >
                        {(variant.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <Progress
                      value={variant.confidence * 100}
                      max={100}
                      className="h-2"
                      aria-label={`Confidence level for ${variant.name}`}
                      aria-valuenow={Math.round(variant.confidence * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    />
                  </div>

                  {/* Conversion rate */}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Conversion Rate</span>
                    <span className="font-semibold text-gray-200">
                      {(variant.conversion_rate * 100).toFixed(2)}%
                    </span>
                  </div>

                  {/* Risk reason */}
                  {variant.is_high_risk && variant.risk_reason && (
                    <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-300">
                      <div className="flex items-start gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span>{variant.risk_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* Select button */}
                  <Button
                    variant={selectedVariant === variant.id ? "default" : "outline"}
                    size="sm"
                    className="w-full"
                    aria-label={`Select ${variant.name}`}
                    aria-pressed={selectedVariant === variant.id}
                    onClick={() =>
                      setSelectedVariant(
                        selectedVariant === variant.id ? null : variant.id
                      )
                    }
                  >
                    {selectedVariant === variant.id ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                        Selected
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 mr-1" />
                        Select
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* ── Safety Tab ──────────────────────────────────── */}
        <TabsContent value="safety">
          <Card className="dark:bg-gray-900 dark:border-gray-800" role="region" aria-label="Safety alerts panel">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-400" />
                Safety Panel
              </CardTitle>
              <CardDescription>
                High-risk variant alerts and human-in-the-loop approval prompts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {(exp.safety_alerts ?? []).length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <CheckCircle2 className="w-10 h-10 text-emerald-500 mb-3" aria-hidden="true" />
                  <p className="text-sm font-medium text-gray-100">All Clear</p>
                  <span className="sr-only">No safety alerts active</span>
                  <p className="text-xs text-gray-400 mt-1">
                    No safety alerts at this time. All variants are performing within acceptable bounds.
                  </p>
                </div>
              ) : (
                (exp.safety_alerts ?? []).map((alert, i) => (
                  <div
                    key={i}
                    className={`rounded-xl border p-4 space-y-3 ${
                      alert.severity === "critical"
                        ? "bg-red-500/10 border-red-500/30"
                        : "bg-amber-500/10 border-amber-500/30"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <AlertTriangle
                        className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
                          alert.severity === "critical"
                            ? "text-red-400"
                            : "text-amber-400"
                        }`}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-sm text-gray-100">
                            {alert.variant_name}
                          </h4>
                          <Badge
                            className={
                              alert.severity === "critical"
                                ? "bg-red-500/20 text-red-300 border-red-500/30 text-[10px]"
                                : "bg-amber-500/20 text-amber-300 border-amber-500/30 text-[10px]"
                            }
                          >
                            {alert.alert_type.replace("_", " ")}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-300 mt-1">{alert.message}</p>
                      </div>
                    </div>

                    {alert.requires_approval && (
                      <div className="flex items-center gap-2 pt-2 border-t border-gray-700/50">
                        <Zap className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-xs text-amber-300 font-medium">
                          Requires your approval to proceed
                        </span>
                        <div className="ml-auto flex gap-2">
                          <Button variant="outline" size="sm" aria-label={`Pause variant ${alert.variant_name}`}>
                            Pause Variant
                          </Button>
                          <Button variant="default" size="sm" aria-label={`Approve variant ${alert.variant_name}`}>
                            <ThumbsUp className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                            Approve
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
