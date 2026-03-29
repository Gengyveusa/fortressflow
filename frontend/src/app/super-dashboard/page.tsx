"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
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
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
  BarChart,
  Bar,
} from "recharts";
import {
  Users,
  DollarSign,
  TrendingDown,
  GitMerge,
  Globe,
  FlaskConical,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Phone,
  Star,
  Download,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Shield,
  Zap,
  Eye,
  Languages,
  Accessibility,
  Activity,
  Flame,
  UserPlus,
  MessageSquare,
  Package,
} from "lucide-react";

// ============================================================
// Types
// ============================================================

interface ProactiveInsightsResponse {
  insights: {
    id: string;
    type: string;
    title: string;
    description: string;
    action_label?: string;
    action_value?: string;
  }[];
  kpi_snapshot?: {
    total_leads: number;
    total_leads_trend: number;
    revenue_at_risk: number;
    revenue_at_risk_trend: number;
    churn_rate: number;
    churn_rate_trend: number;
    dedup_health: number;
    dedup_health_trend: number;
    community_members: number;
    community_members_trend: number;
    experiments_active: number;
    experiments_active_trend: number;
  };
}

interface ExperimentSummary {
  total_experiments: number;
  active_experiments: number;
  reward_history: { day?: string; step?: number; exploitation?: number; exploration?: number; exploit?: number; explore?: number }[];
  strategy: string;
  metrics: Record<string, any>;
  variants: {
    id: string;
    name: string;
    avg_reward: number;
    reward?: number;
    pulls: number;
    confidence: number;
    conversion_rate?: number;
    is_champion?: boolean;
    [key: string]: any;
  }[];
}

interface ChurnPredictions {
  total_customers: number;
  at_risk: number;
  high_risk: number;
  critical: number;
  potential_revenue_at_risk: number;
  predictions: {
    customer_id: string;
    company: string;
    churn_probability: number;
    risk_level: string;
    contributing_factors: string[];
    recommended_actions: string[];
  }[];
  distribution?: { label: string; value: number; color: string }[];
  at_risk_accounts?: any[];
  [key: string]: any;
}

interface DedupHealth {
  total_records: number;
  duplicates_found: number;
  duplicates_merged: number;
  pending_review: number;
  duplicate_rate: number;
  merge_accuracy: number;
  last_scan: string;
  golden_records: number;
  crm_sync_status: Record<string, string>;
  savings: Record<string, any>;
  [key: string]: any;
}

interface CommunityStats {
  total_members: number;
  max_capacity: number;
  waitlist_size: number;
  spots_remaining: number;
  active_events: number;
  scarcity_percentage: number;
  members_joined_this_week: number;
  recent_joins?: { name: string; joined_at: string }[];
  growth_rate: number;
  active_discussions: number;
  events_upcoming: number;
}

interface CallAnalytics {
  total_calls: number;
  total_duration_minutes: number;
  sentiment_distribution: { label: string; value: number; color: string }[];
  action_items_count: number;
  avg_sentiment_score: number;
  calls_this_week: number;
  top_topics: { topic: string; count: number }[];
}

interface PluginMarketplace {
  plugins: {
    id: string;
    name: string;
    description: string;
    rating: number;
    installs: number;
    category: string;
    icon_url?: string;
  }[];
  total_available: number;
}

// ============================================================
// Animated number component
// ============================================================

function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  duration = 1200,
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  duration?: number;
}) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    let start = 0;
    const startTime = performance.now();
    const target = value;

    function tick(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (target - start) * eased;
      setDisplay(current);
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    }

    requestAnimationFrame(tick);
    return () => {
      start = display;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  const formatted =
    decimals > 0
      ? display.toFixed(decimals)
      : Math.round(display).toLocaleString();

  return (
    <span>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}

// ============================================================
// Trend indicator
// ============================================================

function TrendIndicator({ value }: { value: number }) {
  if (value === 0)
    return (
      <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
        --
      </span>
    );
  const positive = value > 0;
  return (
    <span
      className={`inline-flex items-center text-xs font-medium ml-2 ${
        positive
          ? "text-emerald-600 dark:text-emerald-400"
          : "text-red-500 dark:text-red-400"
      }`}
      aria-label={`${positive ? "Up" : "Down"} ${Math.abs(value).toFixed(1)}%`}
    >
      {positive ? (
        <ArrowUpRight className="h-3 w-3 mr-0.5" />
      ) : (
        <ArrowDownRight className="h-3 w-3 mr-0.5" />
      )}
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

// ============================================================
// Skeletons
// ============================================================

function KPICardSkeleton() {
  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardContent className="pt-6">
        <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-3" />
        <div className="h-8 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-2" />
        <div className="h-3 w-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      </CardContent>
    </Card>
  );
}

function ChartSkeleton({ height = "h-[260px]" }: { height?: string }) {
  return (
    <div
      className={`${height} w-full bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse`}
    />
  );
}

function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-10 bg-gray-100 dark:bg-gray-800 rounded animate-pulse"
        />
      ))}
    </div>
  );
}

// ============================================================
// Custom chart tooltip
// ============================================================

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg px-3 py-2 text-xs"
      role="tooltip"
    >
      <p className="font-semibold text-gray-700 dark:text-gray-300 mb-1">
        {label}
      </p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: entry.color }}
          />
          <span className="text-gray-500 dark:text-gray-400 capitalize">
            {entry.name}:
          </span>
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {typeof entry.value === "number"
              ? entry.value.toLocaleString()
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// Star rating display
// ============================================================

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`${rating} out of 5 stars`}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${
            i < full
              ? "text-amber-400 fill-amber-400"
              : i === full && half
              ? "text-amber-400 fill-amber-400/50"
              : "text-gray-300 dark:text-gray-600"
          }`}
        />
      ))}
      <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
        {rating.toFixed(1)}
      </span>
    </span>
  );
}

// ============================================================
// CRM sync status badge
// ============================================================

function SyncStatusBadge({ status }: { status: string | Record<string, string> }) {
  const config: Record<
    string,
    { label: string; className: string; icon: typeof CheckCircle2 }
  > = {
    synced: {
      label: "Synced",
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800",
      icon: CheckCircle2,
    },
    syncing: {
      label: "Syncing...",
      className:
        "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 border-blue-200 dark:border-blue-800",
      icon: RefreshCw,
    },
    error: {
      label: "Sync Error",
      className:
        "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-red-200 dark:border-red-800",
      icon: AlertTriangle,
    },
    idle: {
      label: "Idle",
      className:
        "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 border-gray-200 dark:border-gray-700",
      icon: Clock,
    },
  };

  // Handle Record<string, string> (e.g. {hubspot: "synced", apollo: "synced"})
  const statusKey = typeof status === "string" ? status : Object.values(status).every(v => v === "synced") ? "synced" : Object.values(status).some(v => v === "error") ? "error" : "syncing";
  const c = config[statusKey] ?? config.idle;
  const Icon = c.icon;

  return (
    <Badge
      variant="outline"
      className={`${c.className} gap-1.5`}
    >
      <Icon
        className={`h-3 w-3 ${statusKey === "syncing" ? "animate-spin" : ""}`}
      />
      {c.label}
    </Badge>
  );
}

// ============================================================
// Main Page
// ============================================================

export default function SuperDashboardPage() {
  const [language, setLanguage] = useState<"en" | "es">("en");
  const [highContrast, setHighContrast] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  // Check user preference for reduced motion
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // ── Data fetching ─────────────────────────────────────

  const {
    data: proactive,
    isLoading: proactiveLoading,
  } = useQuery<ProactiveInsightsResponse>({
    queryKey: ["super-dashboard", "proactive"],
    queryFn: () => api.get("/insights/proactive").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const {
    data: experiments,
    isLoading: experimentsLoading,
  } = useQuery<ExperimentSummary>({
    queryKey: ["super-dashboard", "experiments"],
    queryFn: () =>
      api.get("/insights/experiments/summary").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const {
    data: churn,
    isLoading: churnLoading,
  } = useQuery<ChurnPredictions>({
    queryKey: ["super-dashboard", "churn"],
    queryFn: () =>
      api.get("/insights/churn/predictions").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const {
    data: dedup,
    isLoading: dedupLoading,
  } = useQuery<DedupHealth>({
    queryKey: ["super-dashboard", "dedup"],
    queryFn: () =>
      api.get("/insights/deduplication/health").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const {
    data: community,
    isLoading: communityLoading,
  } = useQuery<CommunityStats>({
    queryKey: ["super-dashboard", "community"],
    queryFn: () =>
      api.get("/insights/community/stats").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const {
    data: calls,
    isLoading: callsLoading,
  } = useQuery<CallAnalytics>({
    queryKey: ["super-dashboard", "calls"],
    queryFn: () =>
      api.get("/insights/calls/analytics").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const {
    data: plugins,
    isLoading: pluginsLoading,
  } = useQuery<PluginMarketplace>({
    queryKey: ["super-dashboard", "plugins"],
    queryFn: () =>
      api.get("/insights/plugins/marketplace").then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  // ── KPI data ──────────────────────────────────────────

  const kpi = proactive?.kpi_snapshot;

  const kpiCards = useMemo(
    () => [
      {
        label: language === "en" ? "Total Leads" : "Leads Totales",
        value: kpi?.total_leads ?? 0,
        trend: kpi?.total_leads_trend ?? 0,
        icon: Users,
        gradient: "from-blue-500 to-cyan-500",
        bgLight: "bg-blue-50 dark:bg-blue-950/50",
        textColor: "text-blue-600 dark:text-blue-400",
      },
      {
        label: language === "en" ? "Revenue at Risk" : "Ingresos en Riesgo",
        value: kpi?.revenue_at_risk ?? 0,
        trend: kpi?.revenue_at_risk_trend ?? 0,
        icon: DollarSign,
        gradient: "from-red-500 to-orange-500",
        bgLight: "bg-red-50 dark:bg-red-950/50",
        textColor: "text-red-600 dark:text-red-400",
        prefix: "$",
        invert: true,
      },
      {
        label: language === "en" ? "Churn Rate" : "Tasa de Abandono",
        value: kpi?.churn_rate ?? 0,
        trend: kpi?.churn_rate_trend ?? 0,
        icon: TrendingDown,
        gradient: "from-amber-500 to-yellow-500",
        bgLight: "bg-amber-50 dark:bg-amber-950/50",
        textColor: "text-amber-600 dark:text-amber-400",
        suffix: "%",
        decimals: 1,
        invert: true,
      },
      {
        label: language === "en" ? "Dedup Health" : "Salud Dedup",
        value: kpi?.dedup_health ?? 0,
        trend: kpi?.dedup_health_trend ?? 0,
        icon: GitMerge,
        gradient: "from-emerald-500 to-teal-500",
        bgLight: "bg-emerald-50 dark:bg-emerald-950/50",
        textColor: "text-emerald-600 dark:text-emerald-400",
        suffix: "%",
        decimals: 1,
      },
      {
        label: language === "en" ? "Community Members" : "Miembros",
        value: kpi?.community_members ?? 0,
        trend: kpi?.community_members_trend ?? 0,
        icon: Globe,
        gradient: "from-purple-500 to-pink-500",
        bgLight: "bg-purple-50 dark:bg-purple-950/50",
        textColor: "text-purple-600 dark:text-purple-400",
      },
      {
        label: language === "en" ? "Experiments Active" : "Experimentos Activos",
        value: kpi?.experiments_active ?? 0,
        trend: kpi?.experiments_active_trend ?? 0,
        icon: FlaskConical,
        gradient: "from-violet-500 to-indigo-500",
        bgLight: "bg-violet-50 dark:bg-violet-950/50",
        textColor: "text-violet-600 dark:text-violet-400",
      },
    ],
    [kpi, language]
  );

  // ── Helpers ───────────────────────────────────────────

  const t = useCallback(
    (en: string, es: string) => (language === "en" ? en : es),
    [language]
  );

  const animDuration = reducedMotion ? 0 : 1200;

  // ── Render ────────────────────────────────────────────

  return (
    <div
      className={`space-y-8 pb-12 ${
        highContrast ? "contrast-more" : ""
      }`}
      role="main"
      aria-label={t("Command Center Dashboard", "Panel de Control")}
    >
      {/* ────────────────────────────────────────────────────────
          HEADER
      ──────────────────────────────────────────────────────── */}
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-purple-600 via-blue-500 to-cyan-400 bg-clip-text text-transparent">
              {t("Command Center", "Centro de Comando")}
            </span>
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-xl">
            {t(
              "Real-time intelligence across experiments, churn, deduplication, community, and calls.",
              "Inteligencia en tiempo real: experimentos, abandono, deduplicacion, comunidad y llamadas."
            )}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap" role="toolbar" aria-label="Dashboard controls">
          {/* Language toggle */}
          <Button
            variant="outline"
            size="sm"
            className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800 gap-1.5"
            onClick={() => setLanguage((l) => (l === "en" ? "es" : "en"))}
            aria-label={t("Switch to Spanish", "Cambiar a Ingles")}
          >
            <Languages className="h-4 w-4" />
            {language === "en" ? "ES" : "EN"}
          </Button>

          {/* High contrast toggle */}
          <Button
            variant="outline"
            size="sm"
            className={`dark:border-gray-700 dark:hover:bg-gray-800 gap-1.5 ${
              highContrast
                ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 border-yellow-300 dark:border-yellow-700"
                : "dark:text-gray-300"
            }`}
            onClick={() => setHighContrast((v) => !v)}
            aria-label={t(
              "Toggle high contrast mode",
              "Alternar modo de alto contraste"
            )}
            aria-pressed={highContrast}
          >
            <Accessibility className="h-4 w-4" />
            {t("Contrast", "Contraste")}
          </Button>

          {/* Reduced motion toggle */}
          <Button
            variant="outline"
            size="sm"
            className={`dark:border-gray-700 dark:hover:bg-gray-800 gap-1.5 ${
              reducedMotion
                ? "bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
                : "dark:text-gray-300"
            }`}
            onClick={() => setReducedMotion((v) => !v)}
            aria-label={t(
              "Toggle reduced motion",
              "Alternar movimiento reducido"
            )}
            aria-pressed={reducedMotion}
          >
            <Eye className="h-4 w-4" />
            {t("Motion", "Movimiento")}
          </Button>
        </div>
      </header>

      {/* ────────────────────────────────────────────────────────
          KPI CARDS ROW
      ──────────────────────────────────────────────────────── */}
      <section aria-label={t("Key Performance Indicators", "Indicadores Clave")}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {proactiveLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <KPICardSkeleton key={i} />
              ))
            : kpiCards.map((card) => {
                const Icon = card.icon;
                return (
                  <Card
                    key={card.label}
                    className="dark:bg-gray-900 dark:border-gray-800 overflow-hidden relative group"
                  >
                    {/* Gradient accent bar */}
                    <div
                      className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${card.gradient}`}
                    />
                    <CardContent className="pt-6 pb-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          {card.label}
                        </span>
                        <div className={`p-2 rounded-lg ${card.bgLight}`}>
                          <Icon className={`h-4 w-4 ${card.textColor}`} />
                        </div>
                      </div>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        <AnimatedNumber
                          value={card.value}
                          prefix={card.prefix ?? ""}
                          suffix={card.suffix ?? ""}
                          decimals={card.decimals ?? 0}
                          duration={animDuration}
                        />
                      </p>
                      <TrendIndicator value={card.trend} />
                    </CardContent>
                  </Card>
                );
              })}
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────
          RL EXPERIMENTS PANEL
      ──────────────────────────────────────────────────────── */}
      <section aria-label={t("RL Experiments", "Experimentos RL")}>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
                  <FlaskConical className="h-5 w-5 text-violet-500" />
                  {t("RL Experiments", "Experimentos RL")}
                </CardTitle>
                <CardDescription className="dark:text-gray-400">
                  {t(
                    "Multi-armed bandit reward history and variant performance",
                    "Historial de recompensas y rendimiento de variantes"
                  )}
                </CardDescription>
              </div>
              {experiments && (
                <div className="flex items-center gap-3">
                  <Badge
                    variant="outline"
                    className="dark:border-gray-600 dark:text-gray-300"
                  >
                    {experiments.active_experiments}{" "}
                    {t("Active", "Activos")}
                  </Badge>
                  <Badge
                    variant="secondary"
                    className="dark:bg-gray-800 dark:text-gray-300"
                  >
                    {experiments.total_experiments} {t("Total", "Total")}
                  </Badge>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {experimentsLoading ? (
              <ChartSkeleton />
            ) : !experiments?.reward_history?.length ? (
              <div className="h-[260px] flex items-center justify-center">
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  {t("No experiment data yet.", "Sin datos de experimentos.")}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Area chart */}
                <div className="lg:col-span-2">
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart
                      data={experiments.reward_history}
                      margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="exploitGrad"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#8b5cf6"
                            stopOpacity={0.4}
                          />
                          <stop
                            offset="95%"
                            stopColor="#8b5cf6"
                            stopOpacity={0}
                          />
                        </linearGradient>
                        <linearGradient
                          id="exploreGrad"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#06b6d4"
                            stopOpacity={0.4}
                          />
                          <stop
                            offset="95%"
                            stopColor="#06b6d4"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700"
                      />
                      <XAxis
                        dataKey="step"
                        tick={{ fontSize: 11, fill: "#9ca3af" }}
                        axisLine={false}
                        tickLine={false}
                        label={{
                          value: t("Step", "Paso"),
                          position: "insideBottomRight",
                          offset: -5,
                          style: { fontSize: 11, fill: "#9ca3af" },
                        }}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: "#9ca3af" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        content={<ChartTooltip />}
                      />
                      <Area
                        type="monotone"
                        dataKey="exploit"
                        stroke="#8b5cf6"
                        fill="url(#exploitGrad)"
                        strokeWidth={2.5}
                        name={t("Exploitation", "Explotacion")}
                        dot={false}
                        animationDuration={reducedMotion ? 0 : 800}
                      />
                      <Area
                        type="monotone"
                        dataKey="explore"
                        stroke="#06b6d4"
                        fill="url(#exploreGrad)"
                        strokeWidth={2.5}
                        name={t("Exploration", "Exploracion")}
                        dot={false}
                        animationDuration={reducedMotion ? 0 : 800}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                  <div className="flex items-center gap-4 mt-2 px-1">
                    {[
                      {
                        label: t("Exploitation", "Explotacion"),
                        color: "#8b5cf6",
                      },
                      {
                        label: t("Exploration", "Exploracion"),
                        color: "#06b6d4",
                      },
                    ].map(({ label, color }) => (
                      <span
                        key={label}
                        className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400"
                      >
                        <span
                          className="w-2.5 h-2.5 rounded-sm"
                          style={{ background: color }}
                        />
                        {label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Variant cards */}
                <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                    {t("Variant Performance", "Rendimiento de Variantes")}
                  </h3>
                  {experiments.variants?.length ? (
                    experiments.variants.map((v) => (
                      <div
                        key={v.id}
                        className={`p-3 rounded-lg border ${
                          (v as any).is_champion
                            ? "border-violet-300 dark:border-violet-700 bg-violet-50 dark:bg-violet-950/30"
                            : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                            {v.name}
                          </span>
                          {(v as any).is_champion && (
                            <Badge className="bg-violet-600 text-white text-[10px] px-1.5 py-0">
                              {t("Champion", "Campeon")}
                            </Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <span className="text-gray-400 dark:text-gray-500">
                              {t("Reward", "Recompensa")}
                            </span>
                            <p className="font-semibold text-gray-700 dark:text-gray-200">
                              {(v.avg_reward ?? (v as any).reward ?? 0).toFixed(3)}
                            </p>
                          </div>
                          <div>
                            <span className="text-gray-400 dark:text-gray-500">
                              {t("Pulls", "Tiradas")}
                            </span>
                            <p className="font-semibold text-gray-700 dark:text-gray-200">
                              {v.pulls.toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <span className="text-gray-400 dark:text-gray-500">
                              CVR
                            </span>
                            <p className="font-semibold text-gray-700 dark:text-gray-200">
                              {(((v as any).conversion_rate ?? v.confidence ?? 0) * 100).toFixed(1)}%
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {t("No variants configured.", "Sin variantes.")}
                    </p>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ────────────────────────────────────────────────────────
          CHURN DETECTION + DEDUP HEALTH
      ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Churn Detection */}
        <section aria-label={t("Churn Detection", "Deteccion de Abandono")}>
          <Card className="dark:bg-gray-900 dark:border-gray-800 h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                {t("Churn Detection", "Deteccion de Abandono")}
              </CardTitle>
              <CardDescription className="dark:text-gray-400">
                {t(
                  "Risk distribution and at-risk accounts",
                  "Distribucion de riesgo y cuentas en riesgo"
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {churnLoading ? (
                <ChartSkeleton height="h-[240px]" />
              ) : !churn ? (
                <div className="h-[240px] flex items-center justify-center">
                  <p className="text-sm text-gray-400 dark:text-gray-500">
                    {t("No churn data available.", "Sin datos de abandono.")}
                  </p>
                </div>
              ) : (
                <Tabs defaultValue="chart" className="w-full">
                  <TabsList className="mb-4">
                    <TabsTrigger value="chart">
                      {t("Distribution", "Distribucion")}
                    </TabsTrigger>
                    <TabsTrigger value="table">
                      {t("At-Risk Accounts", "Cuentas en Riesgo")}
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="chart">
                    {(() => {
                      const chartDist = [
                        { label: "Critical", value: churn.critical ?? 0, color: "#ef4444" },
                        { label: "High", value: churn.high_risk ?? 0, color: "#f97316" },
                        { label: "Medium", value: churn.at_risk ?? 0, color: "#eab308" },
                        { label: "Low", value: Math.max(0, (churn.total_customers ?? 0) - (churn.at_risk ?? 0)), color: "#22c55e" },
                      ];
                      return chartDist.some(d => d.value > 0) ? (
                      <ResponsiveContainer width="100%" height={240}>
                        <PieChart>
                          <Pie
                            data={chartDist}
                            cx="50%"
                            cy="50%"
                            innerRadius={55}
                            outerRadius={90}
                            dataKey="value"
                            nameKey="label"
                            paddingAngle={3}
                            animationDuration={reducedMotion ? 0 : 600}
                          >
                            {chartDist.map((entry, idx) => (
                              <Cell
                                key={idx}
                                fill={entry.color}
                                stroke="none"
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            content={<ChartTooltip />}
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 12 }}
                            iconType="circle"
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-8">
                        {t("No distribution data.", "Sin datos de distribucion.")}
                      </p>
                    );
                    })()}
                  </TabsContent>

                  <TabsContent value="table">
                    {(churn.predictions ?? churn.at_risk_accounts)?.length ? (
                      <div className="max-h-[280px] overflow-y-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>
                                {t("Account", "Cuenta")}
                              </TableHead>
                              <TableHead className="text-right">
                                {t("Risk", "Riesgo")}
                              </TableHead>
                              <TableHead className="text-right">
                                {t("Revenue", "Ingresos")}
                              </TableHead>
                              <TableHead className="text-right">
                                {t("Action", "Accion")}
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {(churn.predictions ?? churn.at_risk_accounts ?? [])
                              .slice(0, 8)
                              .map((acct: any) => (
                                <TableRow key={acct.customer_id ?? acct.id}>
                                  <TableCell className="font-medium text-gray-800 dark:text-gray-200">
                                    <div>
                                      <p className="text-sm truncate max-w-[160px]">
                                        {acct.company ?? acct.account_name}
                                      </p>
                                      <p className="text-xs text-gray-400 dark:text-gray-500">
                                        {acct.risk_level ?? "MEDIUM"}
                                      </p>
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <Badge
                                      variant={
                                        (acct.churn_probability ?? acct.risk_score ?? 0) >= 0.8
                                          ? "destructive"
                                          : (acct.churn_probability ?? acct.risk_score ?? 0) >= 0.5
                                          ? "default"
                                          : "secondary"
                                      }
                                      className="text-[11px]"
                                    >
                                      {((acct.churn_probability ?? acct.risk_score ?? 0) * 100).toFixed(0)}%
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-right text-sm font-medium text-gray-700 dark:text-gray-300">
                                    {acct.contributing_factors?.[0] ?? "--"}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-7 text-xs dark:border-gray-700 dark:text-gray-300"
                                      aria-label={`${t(
                                        "Engage",
                                        "Contactar"
                                      )} ${acct.company ?? acct.account_name}`}
                                    >
                                      <Zap className="h-3 w-3 mr-1" />
                                      {t("Engage", "Contactar")}
                                    </Button>
                                  </TableCell>
                                </TableRow>
                              ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-8">
                        {t(
                          "No at-risk accounts detected.",
                          "No se detectaron cuentas en riesgo."
                        )}
                      </p>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Deduplication Health */}
        <section
          aria-label={t("Deduplication Health", "Salud de Deduplicacion")}
        >
          <Card className="dark:bg-gray-900 dark:border-gray-800 h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
                    <GitMerge className="h-5 w-5 text-emerald-500" />
                    {t("Deduplication Health", "Salud de Deduplicacion")}
                  </CardTitle>
                  <CardDescription className="dark:text-gray-400">
                    {t(
                      "Merge progress and CRM sync status",
                      "Progreso de fusiones y estado de sincronizacion CRM"
                    )}
                  </CardDescription>
                </div>
                {dedup && (
                  <SyncStatusBadge status={dedup.crm_sync_status} />
                )}
              </div>
            </CardHeader>
            <CardContent>
              {dedupLoading ? (
                <TableSkeleton rows={4} />
              ) : !dedup ? (
                <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-8">
                  {t("No dedup data available.", "Sin datos de deduplicacion.")}
                </p>
              ) : (
                <div className="space-y-6">
                  {/* Merge completion progress */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
                        {t("Merge Completion", "Finalizacion de Fusiones")}
                      </span>
                      <span className="text-sm font-bold text-gray-800 dark:text-gray-100">
                        {dedup.duplicates_found && dedup.duplicates_merged ? ((dedup.duplicates_merged / dedup.duplicates_found) * 100).toFixed(1) : "0.0"}%
                      </span>
                    </div>
                    <Progress
                      value={dedup.duplicates_found ? (dedup.duplicates_merged / dedup.duplicates_found) * 100 : 0}
                      className="h-3"
                    />
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700">
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                        {t("Duplicates Found", "Duplicados Encontrados")}
                      </p>
                      <p className="text-xl font-bold text-gray-800 dark:text-gray-100">
                        <AnimatedNumber
                          value={dedup.duplicates_found ?? 0}
                          duration={animDuration}
                        />
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700">
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                        {t("Total Merged", "Total Fusionados")}
                      </p>
                      <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                        <AnimatedNumber
                          value={dedup.duplicates_merged ?? 0}
                          duration={animDuration}
                        />
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700">
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                        {t("Pending Review", "Pendiente de Revision")}
                      </p>
                      <p className="text-xl font-bold text-amber-600 dark:text-amber-400">
                        <AnimatedNumber
                          value={dedup.pending_review}
                          duration={animDuration}
                        />
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700">
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">
                        {t("Auto-Merged", "Auto-Fusionados")}
                      </p>
                      <p className="text-xl font-bold text-blue-600 dark:text-blue-400">
                        <AnimatedNumber
                          value={dedup.golden_records ?? 0}
                          duration={animDuration}
                        />
                      </p>
                    </div>
                  </div>

                  {/* Confidence + last sync */}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-800">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4 text-gray-400" />
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {t("Avg Confidence", "Confianza Promedio")}:{" "}
                        <span className="font-semibold text-gray-700 dark:text-gray-200">
                          {((dedup.merge_accuracy ?? 0) * 100).toFixed(1)}%
                        </span>
                      </span>
                    </div>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {t("Last sync", "Ultima sinc")}:{" "}
                      {dedup.last_scan
                        ? new Date(dedup.last_scan).toLocaleString()
                        : "--"}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </div>

      {/* ────────────────────────────────────────────────────────
          COMMUNITY METRICS
      ──────────────────────────────────────────────────────── */}
      <section aria-label={t("Community Metrics", "Metricas de Comunidad")}>
        <Card className="dark:bg-gray-900 dark:border-gray-800 overflow-hidden relative">
          {/* Gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-500 via-pink-500 to-rose-500" />
          <CardHeader className="pb-2">
            <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
              <Globe className="h-5 w-5 text-purple-500" />
              {t("Community Metrics", "Metricas de Comunidad")}
            </CardTitle>
            <CardDescription className="dark:text-gray-400">
              {t(
                "Membership, waitlist, and engagement overview",
                "Membresia, lista de espera y engagement"
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {communityLoading ? (
              <ChartSkeleton height="h-[180px]" />
            ) : !community ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-8">
                {t("No community data.", "Sin datos de comunidad.")}
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Capacity gauge */}
                <div className="flex flex-col items-center justify-center">
                  <div className="relative w-36 h-36">
                    <svg
                      viewBox="0 0 120 120"
                      className="w-full h-full transform -rotate-90"
                      role="img"
                      aria-label={`${t(
                        "Community capacity",
                        "Capacidad de comunidad"
                      )} ${Math.round(
                        (community.total_members / (community.max_capacity || 500)) * 100
                      )}%`}
                    >
                      <circle
                        cx="60"
                        cy="60"
                        r="50"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="10"
                        className="text-gray-200 dark:text-gray-700"
                      />
                      <circle
                        cx="60"
                        cy="60"
                        r="50"
                        fill="none"
                        stroke="url(#communityGauge)"
                        strokeWidth="10"
                        strokeLinecap="round"
                        strokeDasharray={`${
                          (community.total_members / (community.max_capacity || 500)) *
                          314.16
                        } 314.16`}
                        className={
                          reducedMotion
                            ? ""
                            : "transition-all duration-1000 ease-out"
                        }
                      />
                      <defs>
                        <linearGradient
                          id="communityGauge"
                          x1="0%"
                          y1="0%"
                          x2="100%"
                          y2="0%"
                        >
                          <stop offset="0%" stopColor="#a855f7" />
                          <stop offset="100%" stopColor="#ec4899" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        {community.total_members.toLocaleString()}
                      </span>
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        / {(community.max_capacity || 500).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <span className="mt-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                    {t("Member Capacity", "Capacidad de Miembros")}
                  </span>
                </div>

                {/* Stats + FOMO */}
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-950/40 dark:to-pink-950/40 border border-purple-100 dark:border-purple-800">
                    <div className="flex items-center gap-2 mb-1">
                      <Clock className="h-4 w-4 text-purple-500" />
                      <span className="text-sm font-semibold text-purple-800 dark:text-purple-300">
                        {t("Waitlist", "Lista de Espera")}
                      </span>
                    </div>
                    <p className="text-3xl font-bold text-purple-700 dark:text-purple-200">
                      <AnimatedNumber
                        value={community.waitlist_size ?? 0}
                        duration={animDuration}
                      />
                    </p>
                  </div>

                  {/* FOMO element: spots remaining */}
                  <div className="p-4 rounded-lg bg-gradient-to-br from-rose-50 to-orange-50 dark:from-rose-950/40 dark:to-orange-950/40 border border-rose-100 dark:border-rose-800">
                    <div className="flex items-center gap-2 mb-1">
                      <Flame className="h-4 w-4 text-rose-500" />
                      <span className="text-sm font-semibold text-rose-800 dark:text-rose-300">
                        {t("Spots Remaining", "Lugares Disponibles")}
                      </span>
                    </div>
                    <p className="text-3xl font-bold text-rose-700 dark:text-rose-200">
                      <AnimatedNumber
                        value={community.spots_remaining}
                        duration={animDuration}
                      />
                    </p>
                    {community.spots_remaining <= 50 && (
                      <p
                        className={`text-xs text-rose-600 dark:text-rose-400 mt-1 font-medium ${
                          reducedMotion ? "" : "animate-pulse"
                        }`}
                      >
                        {t("Almost full! Act now.", "Casi lleno! Actua ahora.")}
                      </p>
                    )}
                  </div>
                </div>

                {/* Recent joins + stats */}
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700 text-center">
                      <Activity className="h-4 w-4 text-gray-400 mx-auto mb-1" />
                      <p className="text-lg font-bold text-gray-800 dark:text-gray-100">
                        {community.active_events ?? 0}
                      </p>
                      <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                        {t("Discussions", "Discusiones")}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700 text-center">
                      <TrendingDown className="h-4 w-4 text-gray-400 mx-auto mb-1 rotate-180" />
                      <p className="text-lg font-bold text-gray-800 dark:text-gray-100">
                        {(community.scarcity_percentage ?? 0).toFixed(1)}%
                      </p>
                      <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                        {t("Growth", "Crecimiento")}
                      </p>
                    </div>
                  </div>

                  {/* Recent joins */}
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                      {t("Recent Joins", "Nuevos Miembros")}
                    </h4>
                    <div className="space-y-2">
                      {community.recent_joins?.slice(0, 4).map((join, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-2 text-xs"
                        >
                          <UserPlus className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                          <span className="text-gray-700 dark:text-gray-300 truncate">
                            {join.name}
                          </span>
                          <span className="text-gray-400 dark:text-gray-500 ml-auto flex-shrink-0">
                            {new Date(join.joined_at).toLocaleDateString()}
                          </span>
                        </div>
                      ))}
                      {(!community.recent_joins ||
                        community.recent_joins.length === 0) && (
                        <p className="text-xs text-gray-400 dark:text-gray-500">
                          {t("No recent joins.", "Sin nuevos miembros.")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ────────────────────────────────────────────────────────
          CALL ANALYTICS + PLUGIN MARKETPLACE
      ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Call Analytics */}
        <section
          className="lg:col-span-2"
          aria-label={t("Call Analytics", "Analitica de Llamadas")}
        >
          <Card className="dark:bg-gray-900 dark:border-gray-800 h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
                <Phone className="h-5 w-5 text-blue-500" />
                {t("Call Analytics", "Analitica de Llamadas")}
              </CardTitle>
              <CardDescription className="dark:text-gray-400">
                {t(
                  "Sentiment distribution, call volume, and action items",
                  "Distribucion de sentimiento, volumen de llamadas y acciones"
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {callsLoading ? (
                <ChartSkeleton height="h-[220px]" />
              ) : !calls ? (
                <div className="h-[220px] flex items-center justify-center">
                  <p className="text-sm text-gray-400 dark:text-gray-500">
                    {t("No call data available.", "Sin datos de llamadas.")}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Sentiment chart */}
                  <div>
                    {calls.sentiment_distribution?.length ? (
                      <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                          <Pie
                            data={calls.sentiment_distribution}
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={75}
                            dataKey="value"
                            nameKey="label"
                            paddingAngle={2}
                            animationDuration={reducedMotion ? 0 : 600}
                          >
                            {calls.sentiment_distribution.map(
                              (entry, idx) => (
                                <Cell
                                  key={idx}
                                  fill={entry.color}
                                  stroke="none"
                                />
                              )
                            )}
                          </Pie>
                          <Tooltip
                            content={<ChartTooltip />}
                          />
                          <Legend
                            wrapperStyle={{ fontSize: 11 }}
                            iconType="circle"
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-[220px] flex items-center justify-center">
                        <p className="text-sm text-gray-400 dark:text-gray-500">
                          {t("No sentiment data.", "Sin datos de sentimiento.")}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Call stats */}
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-800">
                        <Phone className="h-4 w-4 text-blue-500 mb-1" />
                        <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                          <AnimatedNumber
                            value={calls.total_calls}
                            duration={animDuration}
                          />
                        </p>
                        <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                          {t("Total Calls", "Total Llamadas")}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-800">
                        <Activity className="h-4 w-4 text-indigo-500 mb-1" />
                        <p className="text-xl font-bold text-indigo-700 dark:text-indigo-300">
                          {calls.calls_this_week ?? 0}
                        </p>
                        <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                          {t("This Week", "Esta Semana")}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-800">
                        <CheckCircle2 className="h-4 w-4 text-amber-500 mb-1" />
                        <p className="text-xl font-bold text-amber-700 dark:text-amber-300">
                          <AnimatedNumber
                            value={calls.action_items_count ?? 0}
                            duration={animDuration}
                          />
                        </p>
                        <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                          {t("Action Items", "Acciones")}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-100 dark:border-emerald-800">
                        <Clock className="h-4 w-4 text-emerald-500 mb-1" />
                        <p className="text-xl font-bold text-emerald-700 dark:text-emerald-300">
                          {(calls.total_duration_minutes ?? 0).toLocaleString()}
                        </p>
                        <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase">
                          {t("Minutes", "Minutos")}
                        </p>
                      </div>
                    </div>

                    {/* Top topics */}
                    {calls.top_topics?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                          {t("Top Topics", "Temas Principales")}
                        </h4>
                        <div className="space-y-1.5">
                          {calls.top_topics.slice(0, 4).map((topic, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between text-xs"
                            >
                              <span className="text-gray-700 dark:text-gray-300 truncate">
                                {topic.topic}
                              </span>
                              <Badge
                                variant="secondary"
                                className="text-[10px] dark:bg-gray-800 dark:text-gray-300 ml-2"
                              >
                                {topic.count}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* Plugin Marketplace Preview */}
        <section
          aria-label={t("Plugin Marketplace", "Mercado de Plugins")}
        >
          <Card className="dark:bg-gray-900 dark:border-gray-800 h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg dark:text-gray-100 flex items-center gap-2">
                    <Package className="h-5 w-5 text-cyan-500" />
                    {t("Marketplace", "Mercado")}
                  </CardTitle>
                  <CardDescription className="dark:text-gray-400">
                    {t("Top-rated plugins", "Plugins mejor valorados")}
                  </CardDescription>
                </div>
                {plugins && (
                  <Badge
                    variant="outline"
                    className="dark:border-gray-600 dark:text-gray-300"
                  >
                    {plugins.total_available} {t("available", "disponibles")}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pluginsLoading ? (
                <TableSkeleton rows={5} />
              ) : !plugins?.plugins?.length ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <Package className="h-10 w-10 text-gray-300 dark:text-gray-600 mb-2" />
                  <p className="text-sm text-gray-400 dark:text-gray-500">
                    {t("No plugins available.", "Sin plugins disponibles.")}
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                  {plugins.plugins.slice(0, 8).map((plugin) => (
                    <div
                      key={plugin.id}
                      className="p-3 rounded-lg border border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-cyan-200 dark:hover:border-cyan-800 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-100 to-blue-100 dark:from-cyan-900/40 dark:to-blue-900/40 flex items-center justify-center flex-shrink-0">
                          <Package className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                            {plugin.name}
                          </p>
                          <p className="text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                            {plugin.description}
                          </p>
                          <div className="flex items-center gap-3 mt-1.5">
                            <StarRating rating={plugin.rating} />
                            <span className="text-[10px] text-gray-400 dark:text-gray-500">
                              <Download className="h-3 w-3 inline mr-0.5" />
                              {plugin.installs.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="mt-2">
                        <Badge
                          variant="outline"
                          className="text-[10px] dark:border-gray-600 dark:text-gray-400"
                        >
                          {plugin.category}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </div>

      {/* ────────────────────────────────────────────────────────
          FOOTER LIVE INDICATOR
      ──────────────────────────────────────────────────────── */}
      <footer
        className="flex items-center justify-center gap-2 pt-4 pb-2"
        aria-label={t("Dashboard status", "Estado del panel")}
      >
        <span
          className={`w-2 h-2 rounded-full bg-emerald-500 ${
            reducedMotion ? "" : "animate-pulse"
          }`}
        />
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {t("Live data - refreshing every 30s", "Datos en vivo - actualizando cada 30s")}
        </span>
      </footer>
    </div>
  );
}
