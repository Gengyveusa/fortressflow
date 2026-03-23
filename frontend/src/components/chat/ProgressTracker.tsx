"use client";

import { CheckCircle2, Loader2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProgressData, ProgressStep } from "./types";

const statusConfig = {
  done: {
    icon: CheckCircle2,
    color: "text-green-500 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-950/30",
  },
  in_progress: {
    icon: Loader2,
    color: "text-blue-500 dark:text-blue-400",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    animate: true,
  },
  pending: {
    icon: Clock,
    color: "text-gray-400 dark:text-gray-500",
    bg: "bg-gray-50 dark:bg-gray-900",
  },
};

function StepRow({ step }: { step: ProgressStep }) {
  const config = statusConfig[step.status];
  const Icon = config.icon;

  return (
    <div className={cn("flex items-start gap-2.5 px-3 py-2 rounded-lg", config.bg)}>
      <Icon
        className={cn(
          "w-4 h-4 mt-0.5 flex-shrink-0",
          config.color,
          "animate" in config && config.animate && "animate-spin"
        )}
      />
      <div className="flex-1 min-w-0">
        <span
          className={cn(
            "text-xs",
            step.status === "pending"
              ? "text-gray-400 dark:text-gray-500"
              : "text-gray-700 dark:text-gray-300"
          )}
        >
          {step.label}
        </span>
        {step.detail && (
          <span className="text-xs text-gray-500 dark:text-gray-400 ml-1.5">
            {step.detail}
          </span>
        )}
      </div>
    </div>
  );
}

interface ProgressTrackerProps {
  data: ProgressData;
}

export function ProgressTracker({ data }: ProgressTrackerProps) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden">
      <div className="space-y-0.5 p-1.5">
        {data.steps.map((step, i) => (
          <StepRow key={i} step={step} />
        ))}
      </div>
    </div>
  );
}
