"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Rocket,
  Mail,
  MessageSquare,
  Linkedin,
  Clock,
  GitBranch,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePresets } from "@/lib/hooks";
import { presetsApi } from "@/lib/api";

const STEP_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  sms: MessageSquare,
  linkedin: Linkedin,
  wait: Clock,
  condition: GitBranch,
};

const STEP_COLORS: Record<string, string> = {
  email: "bg-blue-100 text-blue-700",
  sms: "bg-green-100 text-green-700",
  linkedin: "bg-sky-100 text-sky-700",
  wait: "bg-amber-100 text-amber-700",
  condition: "bg-purple-100 text-purple-700",
};

const CATEGORY_BADGES: Record<string, { label: string; color: string }> = {
  cold_outreach: { label: "Cold Outreach", color: "bg-orange-50 text-orange-700 border-orange-200" },
  follow_up: { label: "Follow-up", color: "bg-green-50 text-green-700 border-green-200" },
  re_engagement: { label: "Re-engagement", color: "bg-purple-50 text-purple-700 border-purple-200" },
};

function formatDelay(hours: number): string {
  if (hours === 0) return "Immediate";
  if (hours < 24) return `${hours}h delay`;
  const days = Math.round(hours / 24);
  return `${days}d delay`;
}

export default function PresetsPage() {
  const { data: presets, isLoading, error } = usePresets();
  const [deploying, setDeploying] = useState<number | null>(null);
  const [deployed, setDeployed] = useState<Set<number>>(new Set());
  const router = useRouter();

  const handleDeploy = async (index: number) => {
    setDeploying(index);
    try {
      const result = await presetsApi.deploy(index);
      setDeployed((prev) => new Set(prev).add(index));
      // Navigate to the new sequence after a brief delay
      setTimeout(() => {
        router.push(`/sequences/${result.data.sequence_id}`);
      }, 1500);
    } catch {
      // ignore
    } finally {
      setDeploying(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-2">
          <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-gray-500">Loading presets&hellip;</p>
        </div>
      </div>
    );
  }

  if (error || !presets) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-red-500 text-sm">
          Failed to load presets. Please try again.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold">Gengyve Sequence Presets</h1>
        <p className="text-sm text-gray-500 mt-1">
          One-click deploy pre-built outreach sequences with proven templates for dental office and DSO outreach.
        </p>
      </div>

      {/* Preset Cards */}
      <div className="space-y-6">
        {presets.map((preset, index) => {
          const badge = CATEGORY_BADGES[preset.category] ?? { label: preset.category, color: "bg-gray-100" };
          const isDeployed = deployed.has(index);
          const isDeploying = deploying === index;
          const templateSteps = preset.steps.filter((s) => s.has_template);
          const waitSteps = preset.steps.filter((s) => s.step_type === "wait");
          const totalDays = Math.round(
            preset.steps.reduce((acc, s) => acc + s.delay_hours, 0) / 24
          );

          return (
            <Card key={index} className="overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg">{preset.name}</CardTitle>
                      <Badge className={badge.color}>{badge.label}</Badge>
                    </div>
                    <CardDescription>{preset.description}</CardDescription>
                  </div>
                  <Button
                    onClick={() => handleDeploy(index)}
                    disabled={isDeploying || isDeployed}
                    className={isDeployed ? "bg-green-600 hover:bg-green-600" : ""}
                  >
                    {isDeployed ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 mr-1" /> Deployed
                      </>
                    ) : isDeploying ? (
                      <>
                        <div className="h-4 w-4 mr-1 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Deploying&hellip;
                      </>
                    ) : (
                      <>
                        <Rocket className="h-4 w-4 mr-1" /> Deploy Sequence
                      </>
                    )}
                  </Button>
                </div>
                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-gray-500 mt-2">
                  <span>{preset.steps.length} steps</span>
                  <span>{templateSteps.length} templates</span>
                  <span>~{totalDays} days total</span>
                </div>
              </CardHeader>

              <CardContent>
                {/* Visual Step Flow */}
                <div className="flex items-center gap-1 overflow-x-auto pb-2">
                  {preset.steps.map((step, si) => {
                    const StepIcon = STEP_ICONS[step.step_type] ?? Mail;
                    const color = STEP_COLORS[step.step_type] ?? "bg-gray-100";
                    return (
                      <div key={si} className="flex items-center gap-1 shrink-0">
                        <div className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium ${color}`}>
                          <StepIcon className="h-4 w-4" />
                          <span className="capitalize">{step.step_type}</span>
                          {step.step_type === "wait" && step.delay_hours > 0 && (
                            <span className="text-xs opacity-70">({formatDelay(step.delay_hours)})</span>
                          )}
                        </div>
                        {si < preset.steps.length - 1 && (
                          <ArrowRight className="h-4 w-4 text-gray-300 shrink-0" />
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Template Details */}
                {templateSteps.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Templates Included</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {templateSteps.map((step, ti) => {
                        const StepIcon = STEP_ICONS[step.step_type] ?? Mail;
                        return (
                          <div
                            key={ti}
                            className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg text-sm"
                          >
                            <StepIcon className="h-4 w-4 text-gray-400 shrink-0" />
                            <span className="text-gray-700 truncate">
                              {step.template_name}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
