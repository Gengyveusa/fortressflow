"use client";

import { BarChart3, TrendingUp, TrendingDown, AlertTriangle, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MetricsData, MetricItem, MetricAlert } from "./types";

function MetricRow({ metric }: { metric: MetricItem }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 dark:text-gray-400">{metric.label}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
            {metric.value}
          </span>
          {metric.change && (
            <span
              className={cn(
                "text-xs font-medium flex items-center gap-0.5",
                metric.changeDirection === "up" && "text-green-600 dark:text-green-400",
                metric.changeDirection === "down" && "text-red-600 dark:text-red-400",
                metric.changeDirection === "neutral" && "text-gray-500"
              )}
            >
              {metric.changeDirection === "up" && <TrendingUp className="w-3 h-3" />}
              {metric.changeDirection === "down" && <TrendingDown className="w-3 h-3" />}
              {metric.change}
            </span>
          )}
        </div>
      </div>
      {metric.progress != null && (
        <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 dark:bg-blue-400 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(metric.progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function AlertRow({ alert }: { alert: MetricAlert }) {
  const isWarning = alert.type === "warning";
  return (
    <div
      className={cn(
        "flex items-start gap-2 px-2.5 py-1.5 rounded-lg text-xs",
        isWarning
          ? "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300"
          : "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300"
      )}
    >
      {isWarning ? (
        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
      ) : (
        <MessageCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
      )}
      <span>{alert.text}</span>
    </div>
  );
}

interface MetricsCardProps {
  data: MetricsData;
}

export function MetricsCard({ data }: MetricsCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        <span className="font-semibold text-sm text-gray-800 dark:text-gray-200">
          {data.title}
        </span>
      </div>

      {/* Metrics */}
      <div className="px-3 py-2.5 space-y-2.5">
        {data.metrics.map((metric, i) => (
          <MetricRow key={i} metric={metric} />
        ))}
      </div>

      {/* Alerts */}
      {data.alerts && data.alerts.length > 0 && (
        <div className="px-3 pb-2.5 space-y-1.5">
          {data.alerts.map((alert, i) => (
            <AlertRow key={i} alert={alert} />
          ))}
        </div>
      )}
    </div>
  );
}
