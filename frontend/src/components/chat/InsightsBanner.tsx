"use client";

import { useState, useEffect } from "react";
import { Lightbulb, X, TrendingUp, AlertTriangle, MessageCircle, Award, Linkedin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { insightsApi } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────────────

export interface ProactiveInsight {
  id: string;
  type: "high_performer" | "warning" | "action_needed" | "milestone" | "suggestion";
  title: string;
  description: string;
  action_label?: string;
  action_value?: string;
}

const typeConfig = {
  high_performer: {
    icon: TrendingUp,
    border: "border-green-200 dark:border-green-800",
    bg: "bg-green-50 dark:bg-green-950/30",
    iconColor: "text-green-600 dark:text-green-400",
  },
  warning: {
    icon: AlertTriangle,
    border: "border-amber-200 dark:border-amber-800",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    iconColor: "text-amber-600 dark:text-amber-400",
  },
  action_needed: {
    icon: MessageCircle,
    border: "border-blue-200 dark:border-blue-800",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    iconColor: "text-blue-600 dark:text-blue-400",
  },
  milestone: {
    icon: Award,
    border: "border-purple-200 dark:border-purple-800",
    bg: "bg-purple-50 dark:bg-purple-950/30",
    iconColor: "text-purple-600 dark:text-purple-400",
  },
  suggestion: {
    icon: Linkedin,
    border: "border-indigo-200 dark:border-indigo-800",
    bg: "bg-indigo-50 dark:bg-indigo-950/30",
    iconColor: "text-indigo-600 dark:text-indigo-400",
  },
};

const LS_DISMISSED_KEY = "fortressflow-dismissed-insights";

function getDismissed(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(LS_DISMISSED_KEY) || "[]");
  } catch {
    return [];
  }
}

function dismissInsight(id: string) {
  const dismissed = getDismissed();
  if (!dismissed.includes(id)) {
    dismissed.push(id);
    localStorage.setItem(LS_DISMISSED_KEY, JSON.stringify(dismissed));
  }
}

// ── Single Banner ───────────────────────────────────────────────────────────

function InsightBanner({
  insight,
  onDismiss,
  onAction,
}: {
  insight: ProactiveInsight;
  onDismiss: () => void;
  onAction?: () => void;
}) {
  const config = typeConfig[insight.type] || typeConfig.suggestion;
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-4 py-3 rounded-xl border",
        config.border,
        config.bg,
        "animate-in slide-in-from-top-2 fade-in duration-300"
      )}
    >
      <Lightbulb className={cn("w-5 h-5 flex-shrink-0 mt-0.5", config.iconColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
          {insight.title}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          {insight.description}
        </p>
        {insight.action_label && (
          <Button
            size="sm"
            className="mt-2 h-7 text-xs"
            onClick={onAction}
          >
            {insight.action_label}
          </Button>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-0.5 flex-shrink-0"
        aria-label="Dismiss insight"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ── Insights Container ──────────────────────────────────────────────────────

interface InsightsBannerListProps {
  onOpenChat?: (message: string) => void;
}

export function InsightsBannerList({ onOpenChat }: InsightsBannerListProps) {
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [dismissed, setDismissed] = useState<string[]>([]);

  useEffect(() => {
    setDismissed(getDismissed());
    fetchInsights();
  }, []);

  const fetchInsights = async () => {
    try {
      const res = await insightsApi.getProactive();
      setInsights(res.data.insights || []);
    } catch {
      // Silently fail — insights are non-critical
    }
  };

  const handleDismiss = (id: string) => {
    dismissInsight(id);
    setDismissed((prev) => [...prev, id]);
  };

  const visible = insights.filter((i) => !dismissed.includes(i.id));

  if (visible.length === 0) return null;

  return (
    <div className="space-y-2 mb-4">
      {visible.slice(0, 3).map((insight) => (
        <InsightBanner
          key={insight.id}
          insight={insight}
          onDismiss={() => handleDismiss(insight.id)}
          onAction={() => {
            if (insight.action_value && onOpenChat) {
              onOpenChat(insight.action_value);
            }
          }}
        />
      ))}
    </div>
  );
}
