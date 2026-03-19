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
import { useDashboardStats, useDeliverabilityStats } from "@/lib/hooks";

const recentActivity = [
  { id: 1, text: "New lead imported: jane@acme.com", time: "2 min ago", icon: Users },
  { id: 2, text: "Sequence 'Q4 Outreach' enrolled 12 leads", time: "18 min ago", icon: GitBranch },
  { id: 3, text: "Consent granted for john@corp.io (email)", time: "1 h ago", icon: ShieldCheck },
  { id: 4, text: "Bounce detected: bad@invalid.net", time: "3 h ago", icon: AlertTriangle },
  { id: 5, text: "Warmup completed for sales@example.com", time: "5 h ago", icon: Activity },
];

function StatSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="h-4 w-24 bg-gray-200 rounded animate-pulse" />
      </CardHeader>
      <CardContent>
        <div className="h-8 w-16 bg-gray-200 rounded animate-pulse" />
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useDashboardStats();
  const { data: deliv, isLoading: delivLoading, error: delivError } = useDeliverabilityStats();

  const statCards = [
    { label: "Total Leads", value: stats?.total_leads, icon: Users, color: "text-blue-600 bg-blue-50" },
    { label: "Active Consents", value: stats?.active_consents, icon: ShieldCheck, color: "text-green-600 bg-green-50" },
    { label: "Touches Sent", value: stats?.touches_sent, icon: Send, color: "text-purple-600 bg-purple-50" },
    {
      label: "Response Rate",
      value: stats?.response_rate != null ? `${(stats.response_rate * 100).toFixed(1)}%` : undefined,
      icon: TrendingUp,
      color: "text-orange-600 bg-orange-50",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading
          ? Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />)
          : statCards.map((s) => (
              <Card key={s.label}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardDescription className="text-sm font-medium">{s.label}</CardDescription>
                  <div className={`p-2 rounded-lg ${s.color}`}>
                    <s.icon className="h-4 w-4" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold">
                    {statsError ? "—" : (s.value ?? "—")}
                  </p>
                </CardContent>
              </Card>
            ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {recentActivity.map((a) => (
              <div key={a.id} className="flex items-start gap-3">
                <div className="p-1.5 rounded-md bg-gray-100 mt-0.5">
                  <a.icon className="h-4 w-4 text-gray-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate">{a.text}</p>
                  <p className="text-xs text-gray-400">{a.time}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Deliverability Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {delivLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-4 bg-gray-200 rounded animate-pulse" />
                ))}
              </div>
            ) : delivError ? (
              <p className="text-sm text-red-500">Failed to load deliverability data.</p>
            ) : deliv ? (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Bounce Rate</span>
                  <span className="font-medium">{(deliv.bounce_rate * 100).toFixed(1)}%</span>
                </div>
                <Progress value={Math.min(deliv.bounce_rate * 100, 100)} className="h-2" />

                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Spam Rate</span>
                  <span className="font-medium">{(deliv.spam_rate * 100).toFixed(1)}%</span>
                </div>
                <Progress value={Math.min(deliv.spam_rate * 100, 100)} className="h-2" />

                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Emails Sent</span>
                  <span className="font-medium">{deliv.total_sent.toLocaleString()}</span>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Badge variant={deliv.warmup_active > 0 ? "default" : "secondary"}>
                    {deliv.warmup_active} warming up
                  </Badge>
                  <Badge variant="outline">{deliv.warmup_completed} completed</Badge>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-400">No data yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/leads/import">
              <Upload className="h-4 w-4 mr-2" />
              Import Leads
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/sequences">
              <GitBranch className="h-4 w-4 mr-2" />
              Create Sequence
            </Link>
          </Button>
          <Button asChild variant="outline">
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
