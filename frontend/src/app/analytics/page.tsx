"use client";

import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  Legend,
} from "recharts";
import { useSequencesAnalytics, useResponseTrends, useChannelBreakdown } from "@/lib/hooks";

const CHANNEL_COLORS = ["#3b82f6", "#0ea5e9", "#22c55e"];

function ChartSkeleton() {
  return (
    <div className="h-64 flex items-center justify-center">
      <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function AnalyticsPage() {
  const { data, isLoading, error } = useSequencesAnalytics();
  const { data: responseTrends, isLoading: trendsLoading, error: trendsError } = useResponseTrends();
  const { data: channelData, isLoading: channelLoading, error: channelError } = useChannelBreakdown();
  const sequences = data?.sequences ?? [];

  // build comparison chart data
  const comparisonData = sequences.map((s) => ({
    name: s.sequence_name,
    shortName: s.sequence_name.length > 14 ? s.sequence_name.slice(0, 12) + "…" : s.sequence_name,
    enrolled: s.enrolled,
    "Open %": +(s.open_rate * 100).toFixed(1),
    "Reply %": +(s.reply_rate * 100).toFixed(1),
    "Bounce %": +(s.bounce_rate * 100).toFixed(1),
  }));

  // top performers sorted by reply rate
  const topPerformers = [...sequences].sort((a, b) => b.reply_rate - a.reply_rate).slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold dark:text-gray-100">Analytics</h1>

      {error && (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-8 text-center text-red-500 text-sm">
            Failed to load analytics data. Please try again.
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Sequence Performance Comparison ─────────── */}
        <Card className="lg:col-span-2 dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">Sequence Performance Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <ChartSkeleton />
            ) : comparisonData.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-10">
                No sequence data available yet.
              </p>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={comparisonData} margin={{ top: 4, right: 8, left: -8, bottom: 50 }}>
                    <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                    <XAxis
                      dataKey="shortName"
                      fontSize={11}
                      angle={-35}
                      textAnchor="end"
                      interval={0}
                      height={60}
                      tick={{ fill: "#9ca3af" }}
                    />
                    <YAxis fontSize={12} tick={{ fill: "#9ca3af" }} />
                    <RTooltip
                      contentStyle={{
                        backgroundColor: "var(--color-tooltip-bg, #fff)",
                        border: "1px solid var(--color-tooltip-border, #e5e7eb)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelFormatter={(_label, payload) => {
                        if (payload?.[0]?.payload?.name) return payload[0].payload.name;
                        return _label;
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                    <Bar dataKey="Open %" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Reply %" fill="#34d399" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Bounce %" fill="#f87171" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Channel Breakdown PieChart ──────────────── */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">Channel Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {channelLoading ? (
              <ChartSkeleton />
            ) : channelError ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-sm text-red-500">Failed to load channel data.</p>
              </div>
            ) : !channelData?.length ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-sm text-gray-400">No channel data yet.</p>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={channelData}
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
                      {channelData.map((_, i) => (
                        <Cell key={i} fill={CHANNEL_COLORS[i % CHANNEL_COLORS.length]} />
                      ))}
                    </Pie>
                    <RTooltip
                      formatter={(value: number, name: string) => [`${value}`, name]}
                      contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      iconType="circle"
                      formatter={(value: string) => (
                        <span className="text-sm text-gray-600 dark:text-gray-300">{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Response Rate Trends LineChart ──────────── */}
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100">Response Rate Trends</CardTitle>
          </CardHeader>
          <CardContent>
            {trendsLoading ? (
              <ChartSkeleton />
            ) : trendsError ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-sm text-red-500">Failed to load response trends.</p>
              </div>
            ) : !responseTrends?.length ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-sm text-gray-400">No trend data yet.</p>
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={responseTrends}>
                    <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                    <XAxis dataKey="week" fontSize={12} tick={{ fill: "#9ca3af" }} />
                    <YAxis fontSize={12} unit="%" tick={{ fill: "#9ca3af" }} />
                    <RTooltip
                      formatter={(v: number) => [`${v}%`, "Response Rate"]}
                      contentStyle={{ borderRadius: 8, fontSize: 12 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="rate"
                      stroke="#3b82f6"
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: "#3b82f6" }}
                      activeDot={{ r: 6 }}
                      name="Response Rate"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Top Performing Sequences ──────────────────── */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Top Performing Sequences</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
              ))}
            </div>
          ) : topPerformers.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">
              No sequence performance data yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sequence</TableHead>
                  <TableHead className="text-right">Enrolled</TableHead>
                  <TableHead className="text-right">Open Rate</TableHead>
                  <TableHead className="text-right">Reply Rate</TableHead>
                  <TableHead className="text-right">Bounce Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topPerformers.map((s) => (
                  <TableRow key={s.sequence_id}>
                    <TableCell className="font-medium">{s.sequence_name}</TableCell>
                    <TableCell className="text-right">{s.enrolled}</TableCell>
                    <TableCell className="text-right">
                      {(s.open_rate * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant={s.reply_rate >= 0.05 ? "default" : "secondary"}>
                        {(s.reply_rate * 100).toFixed(1)}%
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {(s.bounce_rate * 100).toFixed(1)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
