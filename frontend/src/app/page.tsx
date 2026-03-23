"use client";

import Link from "next/link";
import {
  Users,
  ShieldCheck,
  Send,
  TrendingUp,
  Upload,
  GitBranch,
  ClipboardCheck,
  AlertTriangle,
  Activity,
} from "lucide-react";
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
import {
  useDashboardStats,
  useDeliverabilityStats,
  useSequencesAnalytics,
  useOutreachDaily,
  useRecentActivity,
} from "@/lib/hooks";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { InsightsBannerList } from "@/components/chat/InsightsBanner";
import { useChatPanel } from "@/components/chat/ChatPanelContext";

// ── Skeleton ──────────────────────────────────────────────
function StatSkeleton() {
  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardHeader className="pb-2">
        <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      </CardHeader>
      <CardContent>
        <div className="h-8 w-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
      </CardContent>
    </Card>
  );
}

function ChartSkeleton() {
  return (
    <div className="h-48 w-full bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
  );
}

// ── Custom Tooltip ────────────────────────────────────────
interface CustomTooltipProps {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 dark:text-gray-300 mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-gray-500 dark:text-gray-400 capitalize">{entry.name}:</span>
          <span className="font-medium text-gray-700 dark:text-gray-200">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────
export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useDashboardStats();
  const { data: deliv, isLoading: delivLoading, error: delivError } = useDeliverabilityStats();
  const { data: seqAnalytics, isLoading: seqLoading } = useSequencesAnalytics();
  const { data: outreachData, isLoading: outreachLoading, error: outreachError } = useOutreachDaily();
  const { data: recentActivity, isLoading: activityLoading, error: activityError } = useRecentActivity();
  const { sendFromExternal } = useChatPanel();

  const statCards = [
    { label: "Total Leads", value: stats?.total_leads, icon: Users, color: "text-blue-600 bg-blue-50 dark:bg-blue-950 dark:text-blue-300" },
    { label: "Active Consents", value: stats?.active_consents, icon: ShieldCheck, color: "text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-300" },
    { label: "Touches Sent", value: stats?.touches_sent, icon: Send, color: "text-purple-600 bg-purple-50 dark:bg-purple-950 dark:text-purple-300" },
    {
      label: "Response Rate",
      value: stats?.response_rate != null ? `${(stats.response_rate * 100).toFixed(1)}%` : undefined,
      icon: TrendingUp,
      color: "text-orange-600 bg-orange-50 dark:bg-orange-950 dark:text-orange-300",
    },
  ];

  // Build bar chart data from sequences analytics
  const seqBarData = (seqAnalytics?.sequences ?? [])
    .slice(0, 6)
    .map((s) => ({
      name: s.sequence_name,
      shortName: s.sequence_name.length > 12 ? s.sequence_name.slice(0, 10) + "…" : s.sequence_name,
      "Open Rate": Math.round(s.open_rate * 100),
      "Reply Rate": Math.round(s.reply_rate * 100),
    }));

  return (
    <div className="space-y-6">
      {/* ── Proactive Insights ── */}
      <InsightsBannerList onOpenChat={sendFromExternal} />

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading
          ? Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />)
          : statCards.map((s) => (
              <Card key={s.label} className="dark:bg-gray-900 dark:border-gray-800">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardDescription className="text-sm font-medium dark:text-gray-400">
                    {s.label}
                  </CardDescription>
                  <div className={`p-2 rounded-lg ${s.color}`}>
                    <s.icon className="h-4 w-4" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {statsError ? "—" : (s.value ?? "—")}
                  </p>
                </CardContent>
              </Card>
            ))}
      </div>

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Outreach Volume 7d */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-base dark:text-gray-100">Outreach Volume (7d)</CardTitle>
            <CardDescription className="dark:text-gray-400">Daily touches by channel</CardDescription>
          </CardHeader>
          <CardContent>
            {outreachLoading ? (
              <ChartSkeleton />
            ) : outreachError ? (
              <div className="h-48 flex items-center justify-center">
                <p className="text-sm text-red-500">Failed to load outreach data.</p>
              </div>
            ) : !outreachData?.length ? (
              <div className="h-48 flex items-center justify-center">
                <p className="text-sm text-gray-400 dark:text-gray-500">No outreach data yet.</p>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={outreachData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                    <defs>
                      <linearGradient id="emailGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="smsGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="linkedinGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11, fill: "#9ca3af" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#9ca3af" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="email" stroke="#3b82f6" fill="url(#emailGrad)" strokeWidth={2.5} name="email" />
                    <Area type="monotone" dataKey="sms" stroke="#10b981" fill="url(#smsGrad)" strokeWidth={2.5} name="sms" />
                    <Area type="monotone" dataKey="linkedin" stroke="#a78bfa" fill="url(#linkedinGrad)" strokeWidth={2.5} name="linkedin" />
                  </AreaChart>
                </ResponsiveContainer>
                <div className="flex items-center gap-4 mt-2 px-1">
                  {[
                    { label: "Email", color: "#3b82f6" },
                    { label: "SMS", color: "#10b981" },
                    { label: "LinkedIn", color: "#a78bfa" },
                  ].map(({ label, color }) => (
                    <span key={label} className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                      <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                      {label}
                    </span>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Sequence Performance */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-base dark:text-gray-100">Sequence Performance</CardTitle>
            <CardDescription className="dark:text-gray-400">Open & reply rates by sequence (%)</CardDescription>
          </CardHeader>
          <CardContent>
            {seqLoading ? (
              <ChartSkeleton />
            ) : !seqBarData.length ? (
              <div className="h-48 flex items-center justify-center">
                <p className="text-sm text-gray-400 dark:text-gray-500">No sequence data yet.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={seqBarData} margin={{ top: 4, right: 8, left: -16, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                  <XAxis
                    dataKey="shortName"
                    tick={{ fontSize: 10, fill: "#9ca3af" }}
                    axisLine={false}
                    tickLine={false}
                    angle={-35}
                    textAnchor="end"
                    interval={0}
                    height={50}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#9ca3af" }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: "rgba(107,114,128,0.1)" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                  <Bar dataKey="Open Rate" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={32} />
                  <Bar dataKey="Reply Rate" fill="#34d399" radius={[3, 3, 0, 0]} maxBarSize={32} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Activity + Deliverability ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {activityLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-10 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
                ))}
              </div>
            ) : activityError ? (
              <p className="text-sm text-red-500">Failed to load recent activity.</p>
            ) : !recentActivity?.length ? (
              <p className="text-sm text-gray-400 dark:text-gray-500">No recent activity.</p>
            ) : (
              recentActivity.map((a) => {
                const IconMap: Record<string, typeof Activity> = {
                  lead: Users,
                  sequence: GitBranch,
                  consent: ShieldCheck,
                  bounce: AlertTriangle,
                  warmup: Activity,
                };
                const Icon = IconMap[a.type] ?? Activity;
                return (
                  <div key={a.id} className="flex items-start gap-3">
                    <div className="p-1.5 rounded-md bg-gray-100 dark:bg-gray-800 mt-0.5">
                      <Icon className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-700 dark:text-gray-300 truncate">{a.text}</p>
                      <p className="text-xs text-gray-400 dark:text-gray-500">{a.time}</p>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">Deliverability Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {delivLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                ))}
              </div>
            ) : delivError ? (
              <p className="text-sm text-red-500">Failed to load deliverability data.</p>
            ) : deliv ? (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Bounce Rate</span>
                  <span className="font-medium dark:text-gray-200">{(deliv.bounce_rate * 100).toFixed(1)}%</span>
                </div>
                <Progress value={Math.max(deliv.bounce_rate * 100, deliv.bounce_rate > 0 ? 3 : 0)} className="h-2.5" />

                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Spam Rate</span>
                  <span className="font-medium dark:text-gray-200">{(deliv.spam_rate * 100).toFixed(1)}%</span>
                </div>
                <Progress value={Math.max(deliv.spam_rate * 100, deliv.spam_rate > 0 ? 3 : 0)} className="h-2.5" />

                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Emails Sent</span>
                  <span className="font-medium dark:text-gray-200">{deliv.total_sent.toLocaleString()}</span>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Badge variant={deliv.warmup_active > 0 ? "default" : "secondary"}>
                    {deliv.warmup_active} warming up
                  </Badge>
                  <Badge variant="outline" className="dark:border-gray-600 dark:text-gray-300">
                    {deliv.warmup_completed} completed
                  </Badge>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-400 dark:text-gray-500">No data yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Quick Actions ── */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/leads/import">
              <Upload className="h-4 w-4 mr-2" />
              Import Leads
            </Link>
          </Button>
          <Button asChild variant="outline" className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
            <Link href="/sequences">
              <GitBranch className="h-4 w-4 mr-2" />
              Create Sequence
            </Link>
          </Button>
          <Button asChild variant="outline" className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800">
            <Link href="/compliance">
              <ClipboardCheck className="h-4 w-4 mr-2" />
              Compliance Check
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
