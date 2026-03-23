"use client";

import { Rocket, Mail, Linkedin, MessageSquare, Phone, Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ActionPreviewData, SequenceStepPreview } from "./types";

const channelIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  email: Mail,
  linkedin: Linkedin,
  sms: MessageSquare,
  call: Phone,
};

function StepRow({ step }: { step: SequenceStepPreview }) {
  const Icon = channelIcons[step.channel] || Mail;
  return (
    <div className="flex items-center gap-2 py-1.5 px-2 text-xs text-gray-700 dark:text-gray-300">
      <span className="text-gray-400 dark:text-gray-500 w-12 flex-shrink-0 font-mono">
        Day {step.day}
      </span>
      <Icon className="w-3.5 h-3.5 flex-shrink-0 text-blue-500 dark:text-blue-400" />
      <span className="truncate">{step.description}</span>
    </div>
  );
}

interface ActionPreviewProps {
  data: ActionPreviewData;
  onConfirm: () => void;
  onModify: () => void;
  onCancel: () => void;
}

export function ActionPreview({ data, onConfirm, onModify, onCancel }: ActionPreviewProps) {
  return (
    <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 bg-blue-100/60 dark:bg-blue-900/30 border-b border-blue-200 dark:border-blue-800">
        <Rocket className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        <span className="font-semibold text-sm text-blue-800 dark:text-blue-200">
          {data.title || "Campaign Ready"}
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 space-y-2">
        <p className="text-xs text-gray-600 dark:text-gray-400">
          <span className="font-medium text-gray-700 dark:text-gray-300">Target:</span> {data.target}
        </p>
        <p className="text-xs text-gray-600 dark:text-gray-400">
          <span className="font-medium text-gray-700 dark:text-gray-300">Qualified:</span> {data.qualified}
        </p>

        {data.steps.length > 0 && (
          <>
            <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mt-2">
              Sequence: {data.steps.length} steps over {data.steps[data.steps.length - 1]?.day || 0} days
            </p>
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
              {data.steps.map((step, i) => (
                <StepRow key={i} step={step} />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-t border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/20">
        <Button
          size="sm"
          className="h-7 text-xs bg-green-600 hover:bg-green-700 text-white"
          onClick={onConfirm}
        >
          <Check className="w-3 h-3 mr-1" />
          Launch
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs dark:border-gray-600 dark:text-gray-300"
          onClick={onModify}
        >
          <Pencil className="w-3 h-3 mr-1" />
          Modify
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-xs text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400"
          onClick={onCancel}
        >
          <X className="w-3 h-3 mr-1" />
          Cancel
        </Button>
      </div>
    </div>
  );
}
