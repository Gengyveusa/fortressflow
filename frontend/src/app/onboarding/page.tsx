"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Shield,
  Building2,
  Target,
  Radio,
  Rocket,
  ChevronRight,
  ChevronLeft,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// ── Types ───────────────────────────────────────────────────────────────────

interface OnboardingData {
  businessType: string;
  companyName: string;
  targetSpecialties: string[];
  targetRegion: string;
  targetStates: string;
  channels: string[];
  launchNow: boolean;
}

const BUSINESS_TYPES = [
  { label: "Dental Practice", value: "dental_practice" },
  { label: "DSO", value: "dso" },
  { label: "Dental Lab", value: "dental_lab" },
  { label: "Medical Device", value: "medical_device" },
];

const TARGET_SPECIALTIES = [
  { label: "Periodontists", value: "periodontists" },
  { label: "Oral Surgeons", value: "oral_surgeons" },
  { label: "General Dentists", value: "general_dentists" },
  { label: "Office Managers", value: "office_managers" },
];

const REGION_OPTIONS = [
  { label: "Nationwide", value: "nationwide" },
  { label: "Specific States", value: "specific_states" },
  { label: "My Metro Area", value: "metro" },
];

const CHANNEL_OPTIONS = [
  { label: "Email", value: "email", icon: "mail" },
  { label: "LinkedIn", value: "linkedin", icon: "linkedin" },
  { label: "SMS", value: "sms", icon: "message" },
];

// ── Option Chip ─────────────────────────────────────────────────────────────

function OptionChip({
  label,
  selected,
  onClick,
  multi,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  multi?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-4 py-2.5 rounded-xl text-sm font-medium transition-all border",
        selected
          ? "bg-blue-600 text-white border-blue-600 dark:bg-blue-500 dark:border-blue-500 shadow-sm"
          : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950/20"
      )}
    >
      {multi && selected && <Check className="w-3.5 h-3.5 inline mr-1.5 -mt-0.5" />}
      {label}
    </button>
  );
}

// ── Step Components ─────────────────────────────────────────────────────────

function WelcomeStep() {
  return (
    <div className="flex flex-col items-center text-center gap-6 py-8">
      <div className="w-20 h-20 rounded-2xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
        <Shield className="w-10 h-10 text-blue-600 dark:text-blue-400" />
      </div>
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Welcome to FortressFlow
        </h1>
        <p className="text-gray-500 dark:text-gray-400 text-lg max-w-md">
          Let&apos;s set up your account so you can start reaching your ideal customers.
        </p>
      </div>
    </div>
  );
}

function BusinessStep({
  data,
  onChange,
}: {
  data: OnboardingData;
  onChange: (patch: Partial<OnboardingData>) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
          <Building2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Your Business
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            What kind of business are you?
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {BUSINESS_TYPES.map((bt) => (
          <OptionChip
            key={bt.value}
            label={bt.label}
            selected={data.businessType === bt.value}
            onClick={() => onChange({ businessType: bt.value })}
          />
        ))}
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Company Name
        </label>
        <Input
          value={data.companyName}
          onChange={(e) => onChange({ companyName: e.target.value })}
          placeholder="Your company name"
          className="dark:bg-gray-800 dark:border-gray-700"
        />
      </div>
    </div>
  );
}

function TargetStep({
  data,
  onChange,
}: {
  data: OnboardingData;
  onChange: (patch: Partial<OnboardingData>) => void;
}) {
  const toggleSpecialty = (val: string) => {
    const current = data.targetSpecialties;
    const next = current.includes(val)
      ? current.filter((s) => s !== val)
      : [...current, val];
    onChange({ targetSpecialties: next });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
          <Target className="w-5 h-5 text-purple-600 dark:text-purple-400" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Your Target
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Who are you trying to reach?
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {TARGET_SPECIALTIES.map((s) => (
          <OptionChip
            key={s.value}
            label={s.label}
            selected={data.targetSpecialties.includes(s.value)}
            onClick={() => toggleSpecialty(s.value)}
            multi
          />
        ))}
      </div>

      <div className="space-y-3">
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Which regions?
        </p>
        <div className="flex flex-wrap gap-2">
          {REGION_OPTIONS.map((r) => (
            <OptionChip
              key={r.value}
              label={r.label}
              selected={data.targetRegion === r.value}
              onClick={() => onChange({ targetRegion: r.value })}
            />
          ))}
        </div>
        {data.targetRegion === "specific_states" && (
          <Input
            value={data.targetStates}
            onChange={(e) => onChange({ targetStates: e.target.value })}
            placeholder="e.g., Texas, California, Florida"
            className="dark:bg-gray-800 dark:border-gray-700"
          />
        )}
      </div>
    </div>
  );
}

function ChannelsStep({
  data,
  onChange,
}: {
  data: OnboardingData;
  onChange: (patch: Partial<OnboardingData>) => void;
}) {
  const toggleChannel = (val: string) => {
    const current = data.channels;
    const next = current.includes(val)
      ? current.filter((c) => c !== val)
      : [...current, val];
    onChange({ channels: next });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
          <Radio className="w-5 h-5 text-green-600 dark:text-green-400" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Your Channels
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            How do you want to reach them?
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {CHANNEL_OPTIONS.map((ch) => (
          <OptionChip
            key={ch.value}
            label={ch.label}
            selected={data.channels.includes(ch.value)}
            onClick={() => toggleChannel(ch.value)}
            multi
          />
        ))}
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-4">
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Connect your email
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Set up AWS SES to start sending emails through FortressFlow.
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="text-xs dark:border-gray-600 dark:text-gray-300" asChild>
            <a href="/settings">Configure AWS SES</a>
          </Button>
          <Button size="sm" variant="ghost" className="text-xs text-gray-500">
            I&apos;ll do this later
          </Button>
        </div>
      </div>
    </div>
  );
}

function LaunchStep({
  data,
}: {
  data: OnboardingData;
}) {
  const specialtyNames = data.targetSpecialties
    .map((s) => TARGET_SPECIALTIES.find((t) => t.value === s)?.label)
    .filter(Boolean)
    .join(", ");
  const regionLabel =
    data.targetRegion === "specific_states"
      ? data.targetStates || "selected states"
      : REGION_OPTIONS.find((r) => r.value === data.targetRegion)?.label || "Nationwide";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
          <Rocket className="w-5 h-5 text-orange-600 dark:text-orange-400" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Ready to Launch?
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Want to launch your first campaign now?
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/30 p-4 space-y-2">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Based on what you told me, I recommend:
        </p>
        <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
          &ldquo;50 {specialtyNames || "leads"} in {regionLabel} &mdash;{" "}
          {data.channels.length > 0
            ? `${data.channels.length}-channel`
            : "email"}{" "}
          sequence&rdquo;
        </p>
      </div>
    </div>
  );
}

// ── Steps Config ────────────────────────────────────────────────────────────

const STEPS = [
  { id: "welcome", label: "Welcome" },
  { id: "business", label: "Business" },
  { id: "target", label: "Target" },
  { id: "channels", label: "Channels" },
  { id: "launch", label: "Launch" },
];

// ── Main Page ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [data, setData] = useState<OnboardingData>({
    businessType: "",
    companyName: "",
    targetSpecialties: [],
    targetRegion: "nationwide",
    targetStates: "",
    channels: ["email"],
    launchNow: false,
  });
  const [saving, setSaving] = useState(false);

  const updateData = useCallback((patch: Partial<OnboardingData>) => {
    setData((prev) => ({ ...prev, ...patch }));
  }, []);

  const canProceed = () => {
    switch (step) {
      case 0:
        return true;
      case 1:
        return data.businessType && data.companyName.trim();
      case 2:
        return data.targetSpecialties.length > 0;
      case 3:
        return data.channels.length > 0;
      case 4:
        return true;
      default:
        return true;
    }
  };

  const handleFinish = async (launch: boolean) => {
    setSaving(true);
    try {
      // Save onboarding preferences to backend
      await fetch("/api/v1/settings/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_type: data.businessType,
          company_name: data.companyName,
          target_specialties: data.targetSpecialties,
          target_region: data.targetRegion,
          target_states: data.targetStates,
          channels: data.channels,
          launch_first_campaign: launch,
        }),
      });
    } catch {
      // Continue even if save fails
    }

    // Store onboarding completed flag
    localStorage.setItem("fortressflow-onboarding-completed", "1");

    if (launch) {
      // Redirect to dashboard and auto-open chat with campaign request
      router.push("/?launch=1");
    } else {
      router.push("/");
    }
  };

  const renderStep = () => {
    switch (step) {
      case 0:
        return <WelcomeStep />;
      case 1:
        return <BusinessStep data={data} onChange={updateData} />;
      case 2:
        return <TargetStep data={data} onChange={updateData} />;
      case 3:
        return <ChannelsStep data={data} onChange={updateData} />;
      case 4:
        return <LaunchStep data={data} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 p-4">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="flex items-center gap-1.5 mb-8">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex-1 flex flex-col items-center gap-1">
              <div
                className={cn(
                  "h-1.5 w-full rounded-full transition-colors",
                  i <= step
                    ? "bg-blue-600 dark:bg-blue-500"
                    : "bg-gray-200 dark:bg-gray-700"
                )}
              />
              <span
                className={cn(
                  "text-xs",
                  i <= step
                    ? "text-blue-600 dark:text-blue-400 font-medium"
                    : "text-gray-400 dark:text-gray-500"
                )}
              >
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-lg p-6 min-h-[320px] flex flex-col">
          <div className="flex-1">{renderStep()}</div>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-4 border-t border-gray-100 dark:border-gray-800">
            {step > 0 ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setStep((s) => s - 1)}
                className="text-gray-500 dark:text-gray-400"
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
            ) : (
              <div />
            )}

            {step < STEPS.length - 1 ? (
              <Button
                size="sm"
                onClick={() => setStep((s) => s + 1)}
                disabled={!canProceed()}
              >
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleFinish(false)}
                  disabled={saving}
                  className="dark:border-gray-700 dark:text-gray-300"
                >
                  I&apos;ll explore first
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleFinish(true)}
                  disabled={saving}
                >
                  <Rocket className="w-4 h-4 mr-1" />
                  {saving ? "Setting up..." : "Let's go!"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
