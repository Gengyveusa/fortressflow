"use client";

import { useState } from "react";
import { Globe, Plus, AlertTriangle, Activity } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  Legend,
} from "recharts";
import { useDomains, useDeliverabilityStats, useBounceDaily } from "@/lib/hooks";
import { deliverabilityApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

function DomainSkeleton() {
  return (
    <Card className="animate-pulse dark:bg-gray-900 dark:border-gray-800">
      <CardContent className="pt-6 space-y-3">
        <div className="h-5 w-40 bg-gray-200 dark:bg-gray-700 rounded" />
        <div className="h-3 w-full bg-gray-100 dark:bg-gray-800 rounded" />
        <div className="h-4 w-20 bg-gray-100 dark:bg-gray-800 rounded" />
      </CardContent>
    </Card>
  );
}

export default function DeliverabilityPage() {
  const { data: domains, isLoading: domainsLoading, error: domainsError } = useDomains();
  const { data: stats, isLoading: statsLoading } = useDeliverabilityStats();
  const { data: bounceData, isLoading: bounceLoading, error: bounceError } = useBounceDaily();
  const queryClient = useQueryClient();

  const [newDomain, setNewDomain] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");

  const handleAddDomain = async () => {
    if (!newDomain.trim()) return;
    setAdding(true);
    setAddError("");
    try {
      await deliverabilityApi.addDomain(newDomain.trim());
      queryClient.invalidateQueries({ queryKey: ["domains"] });
      setNewDomain("");
    } catch {
      setAddError("Failed to add domain. Please try again.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold dark:text-gray-100">Deliverability</h1>

      {/* ── Summary stats ────────────────────────────── */}
      {statsLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="pt-6">
                <div className="h-4 w-24 bg-gray-200 rounded mb-2" />
                <div className="h-7 w-16 bg-gray-200 rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <p className="text-sm text-gray-500 dark:text-gray-400">Bounce Rate</p>
              <p className="text-2xl font-bold dark:text-gray-100">{(stats.bounce_rate * 100).toFixed(1)}%</p>
              <p className="text-xs text-gray-400 dark:text-gray-500">{stats.total_bounced} of {stats.total_sent} emails</p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <p className="text-sm text-gray-500 dark:text-gray-400">Spam Complaints</p>
              <p className="text-2xl font-bold dark:text-gray-100">{stats.spam_complaints}</p>
              <p className="text-xs text-gray-400 dark:text-gray-500">{(stats.spam_rate * 100).toFixed(2)}% spam rate</p>
            </CardContent>
          </Card>
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardContent className="pt-6">
              <p className="text-sm text-gray-500 dark:text-gray-400">Warmup Status</p>
              <p className="text-2xl font-bold dark:text-gray-100">{stats.warmup_active} active</p>
              <p className="text-xs text-gray-400 dark:text-gray-500">{stats.warmup_completed} completed</p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* ── Domain health cards ──────────────────────── */}
      <div>
        <h2 className="text-base font-medium mb-3 dark:text-gray-100">Domain Health</h2>
        {domainsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <DomainSkeleton key={i} />
            ))}
          </div>
        ) : domainsError ? (
          <Card>
            <CardContent className="py-8 text-center text-red-500 text-sm">
              Failed to load domains.
            </CardContent>
          </Card>
        ) : !domains?.length ? (
          <Card>
            <CardContent className="py-8 text-center text-gray-400 text-sm">
              No domains configured yet. Add one below.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {domains.map((d) => (
              <Card key={d.id} className="dark:bg-gray-900 dark:border-gray-800">
                <CardContent className="pt-6 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Globe className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      <span className="font-medium text-sm dark:text-gray-200">{d.domain}</span>
                    </div>
                    <Badge
                      variant={d.health_score >= 80 ? "default" : d.health_score >= 50 ? "secondary" : "destructive"}
                    >
                      {d.health_score}%
                    </Badge>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                      <span>Warmup Progress</span>
                      <span>{d.warmup_progress}%</span>
                    </div>
                    <Progress value={d.warmup_progress} className="h-2" />
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {d.total_sent} sent · {d.total_bounced} bounced
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* ── Add domain form ──────────────────────────── */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Add Domain</CardTitle>
          <CardDescription className="dark:text-gray-400">Register a new sending domain for warmup and monitoring.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 max-w-md">
            <Input
              placeholder="e.g. outreach.company.com"
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
            />
            <Button onClick={handleAddDomain} disabled={adding || !newDomain.trim()}>
              <Plus className="h-4 w-4 mr-1" /> {adding ? "Adding…" : "Add"}
            </Button>
          </div>
          {addError && (
            <p className="text-sm text-red-500 mt-2 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> {addError}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Bounce rate chart ────────────────────────── */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Bounce Rate (Last 7 Days)</CardTitle>
        </CardHeader>
        <CardContent>
          {bounceLoading ? (
            <div className="h-64 flex items-center justify-center">
              <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : bounceError ? (
            <div className="h-64 flex items-center justify-center">
              <p className="text-sm text-red-500">Failed to load bounce data.</p>
            </div>
          ) : !bounceData?.length ? (
            <div className="h-64 flex items-center justify-center">
              <p className="text-sm text-gray-400">No bounce data yet.</p>
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bounceData}>
                  <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-gray-200 dark:[&>line]:stroke-gray-700" />
                  <XAxis dataKey="date" fontSize={12} tick={{ fill: "#9ca3af" }} />
                  <YAxis fontSize={12} tick={{ fill: "#9ca3af" }} />
                  <RTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} />
                  <Bar dataKey="sent" fill="#3b82f6" name="Sent" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="bounced" fill="#f87171" name="Bounced" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Spam complaint tracker ───────────────────── */}
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Spam Complaint Tracker</CardTitle>
        </CardHeader>
        <CardContent>
          {stats && stats.spam_complaints > 0 ? (
            <div className="flex items-center gap-3 p-4 bg-yellow-50 dark:bg-yellow-950/30 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-500" />
              <div>
                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-400">
                  {stats.spam_complaints} spam complaint{stats.spam_complaints !== 1 ? "s" : ""} detected
                </p>
                <p className="text-xs text-yellow-600 dark:text-yellow-500">
                  Spam rate: {(stats.spam_rate * 100).toFixed(2)}%. Keep it below 0.1% to maintain good deliverability.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-950/30 rounded-lg border border-green-200 dark:border-green-800">
              <Activity className="h-5 w-5 text-green-600 dark:text-green-500" />
              <div>
                <p className="text-sm font-medium text-green-800 dark:text-green-400">No spam complaints</p>
                <p className="text-xs text-green-600 dark:text-green-500">Your sending reputation looks healthy.</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
