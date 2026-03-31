"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Crown,
  Shield,
  Users,
  Star,
  Lock,
  Copy,
  Check,
  ChevronRight,
  Clock,
  Calendar,
  UserPlus,
  Award,
  Zap,
  TrendingUp,
  Eye,
  MessageSquare,
  Gift,
  Sparkles,
  ArrowRight,
  Link2,
  ExternalLink,
  CircleCheck,
  Circle,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────────────

interface CommunityStats {
  total_members: number;
  spots_remaining: number;
  max_capacity: number;
  joined_this_week: number;
  waitlist_count: number;
  member?: MemberProfile | null;
  upcoming_events?: CommunityEvent[];
  exclusive_content?: ExclusiveContent[];
}

interface MemberProfile {
  id: string;
  name: string;
  avatar_url: string | null;
  tier: "founding" | "premium" | "standard";
  reputation_score: number;
  badges: MemberBadge[];
  joined_at: string;
  onboarding_progress: OnboardingStep[];
  invite_codes: InviteCode[];
  connections_suggested: ConnectionSuggestion[];
}

interface MemberBadge {
  id: string;
  name: string;
  icon: string;
  earned_at: string;
}

interface OnboardingStep {
  id: string;
  label: string;
  description: string;
  completed: boolean;
  day: number;
}

interface InviteCode {
  code: string;
  uses: number;
  max_uses: number;
  created_at: string;
}

interface CommunityEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  spots_total: number;
  spots_taken: number;
  is_registered: boolean;
  event_type: "workshop" | "ama" | "roundtable" | "masterclass";
}

interface ExclusiveContent {
  id: string;
  title: string;
  description: string;
  category: string;
  published_at: string;
  is_locked: boolean;
  read_count: number;
}

interface ConnectionSuggestion {
  id: string;
  name: string;
  avatar_url: string | null;
  title: string;
  company: string;
  mutual_connections: number;
  match_reason: string;
}

interface WaitlistFormData {
  email: string;
  company: string;
  role: string;
  referral_code: string;
}

// ── Fallback ────────────────────────────────────────────────────────────────

const FALLBACK_STATS: CommunityStats = {
  total_members: 0,
  spots_remaining: 100,
  max_capacity: 500,
  joined_this_week: 0,
  waitlist_count: 0,
  member: null,
  upcoming_events: [],
  exclusive_content: [],
};

// ── API Calls ───────────────────────────────────────────────────────────────

function useCommunityStats() {
  return useQuery({
    queryKey: ["community-stats"],
    queryFn: async () => {
      try {
        const r = await api.get<CommunityStats>("/insights/community/stats");
        return r.data;
      } catch {
        return FALLBACK_STATS;
      }
    },
  });
}

// ── Utility Components ──────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-gray-200 dark:bg-gray-700",
        className
      )}
    />
  );
}

function SectionSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading content">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
      <span className="sr-only">Loading...</span>
    </div>
  );
}

function AvatarCircle({
  name,
  url,
  size = "md",
}: {
  name: string;
  url?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClasses = {
    sm: "h-8 w-8 text-xs",
    md: "h-10 w-10 text-sm",
    lg: "h-14 w-14 text-lg",
  };
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center font-semibold bg-gradient-to-br from-purple-500 to-blue-500 text-white shrink-0",
        sizeClasses[size]
      )}
      aria-hidden="true"
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt=""
          className="rounded-full h-full w-full object-cover"
        />
      ) : (
        initials
      )}
    </div>
  );
}

const TIER_CONFIG = {
  founding: {
    label: "Founding Member",
    color:
      "bg-gradient-to-r from-amber-500 to-yellow-400 text-black",
    icon: Crown,
  },
  premium: {
    label: "Premium Member",
    color:
      "bg-gradient-to-r from-purple-600 to-indigo-500 text-white",
    icon: Star,
  },
  standard: {
    label: "Member",
    color:
      "bg-gradient-to-r from-blue-600 to-cyan-500 text-white",
    icon: Shield,
  },
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  workshop: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  ama: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  roundtable:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  masterclass:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
};

// ── Hero Banner ─────────────────────────────────────────────────────────────

function HeroBanner({
  spotsRemaining,
  totalCapacity,
  isLoading,
}: {
  spotsRemaining: number;
  totalCapacity: number;
  isLoading: boolean;
}) {
  const spotsPercent = totalCapacity
    ? ((totalCapacity - spotsRemaining) / totalCapacity) * 100
    : 0;

  return (
    <section
      aria-labelledby="hero-heading"
      className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-700 via-indigo-600 to-blue-600 p-8 md:p-12 text-white"
    >
      {/* Background pattern */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage:
            "radial-gradient(circle at 25% 25%, white 1px, transparent 1px), radial-gradient(circle at 75% 75%, white 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
        aria-hidden="true"
      />

      <div className="relative z-10 max-w-3xl">
        <div className="flex items-center gap-2 mb-4">
          <Crown className="h-6 w-6 text-amber-300" aria-hidden="true" />
          <span className="text-sm font-medium tracking-widest uppercase text-purple-200">
            Invitation Only
          </span>
        </div>
        <h1
          id="hero-heading"
          className="text-3xl md:text-5xl font-bold tracking-tight mb-4"
        >
          The Inner Circle
        </h1>
        <p className="text-lg md:text-xl text-purple-100 mb-8 max-w-2xl">
          An exclusive community of top-performing sales professionals sharing
          strategies, insights, and connections that drive results.
        </p>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
          <Button
            size="lg"
            className="bg-white text-purple-700 hover:bg-purple-50 font-semibold px-8 shadow-lg transition-transform hover:scale-105 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-purple-700"
            aria-label="Apply to join The Inner Circle community"
            onClick={() => {
              document
                .getElementById("waitlist-section")
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            <Sparkles className="h-5 w-5 mr-2" aria-hidden="true" />
            Apply to Join
          </Button>
          <div className="text-sm text-purple-200">
            Free to join for qualified professionals
          </div>
        </div>

        {/* Spots remaining indicator */}
        <div
          className="bg-white/10 backdrop-blur-sm rounded-lg p-4 max-w-sm"
          role="status"
          aria-label={`${spotsRemaining} spots remaining out of ${totalCapacity}`}
        >
          {isLoading ? (
            <Skeleton className="h-12 w-full bg-white/20" />
          ) : (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Spots Remaining</span>
                <span className="text-2xl font-bold tabular-nums">
                  {spotsRemaining}
                </span>
              </div>
              <div className="h-2 bg-white/20 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-1000 ease-out",
                    spotsPercent > 90
                      ? "bg-red-400"
                      : spotsPercent > 70
                        ? "bg-amber-400"
                        : "bg-emerald-400"
                  )}
                  style={{ width: `${spotsPercent}%` }}
                />
              </div>
              {spotsPercent > 85 && (
                <p className="text-xs text-amber-300 mt-2 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  Almost full - apply now to secure your spot
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

// ── FOMO Ticker ─────────────────────────────────────────────────────────────

function FomoTicker({
  spotsRemaining,
  joinedThisWeek,
  waitlistCount,
  isLoading,
}: {
  spotsRemaining: number;
  joinedThisWeek: number;
  waitlistCount: number;
  isLoading: boolean;
}) {
  const tickerRef = useRef<HTMLDivElement>(null);

  if (isLoading) return null;

  const items = [
    `Only ${spotsRemaining} spots remaining`,
    `${joinedThisWeek} professionals joined this week`,
    `${waitlistCount} on waitlist`,
  ];
  // Duplicate for seamless scroll loop
  const scrollItems = [...items, ...items];

  return (
    <div
      className="overflow-hidden bg-gradient-to-r from-purple-900 via-indigo-900 to-blue-900 dark:from-purple-950 dark:via-indigo-950 dark:to-blue-950 rounded-lg py-3"
      role="marquee"
      aria-label={`Community status: ${items.join(". ")}`}
    >
      <div
        ref={tickerRef}
        className="flex gap-8 animate-[ticker_20s_linear_infinite] whitespace-nowrap"
        aria-hidden="true"
      >
        {scrollItems.map((text, i) => (
          <span
            key={i}
            className="flex items-center gap-2 text-sm font-medium text-purple-200 px-4"
          >
            <Zap className="h-4 w-4 text-amber-400 shrink-0" />
            {text}
            <span className="text-purple-500 mx-2" aria-hidden="true">
              |
            </span>
          </span>
        ))}
      </div>
      {/* SR-only live text */}
      <div className="sr-only" role="status" aria-live="polite">
        {items.join(". ")}
      </div>
      <style jsx>{`
        @keyframes ticker {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}

// ── Member Dashboard - Overview Tab ─────────────────────────────────────────

function OverviewTab({ member }: { member: MemberProfile }) {
  const tierCfg = TIER_CONFIG[member.tier];
  const TierIcon = tierCfg.icon;

  return (
    <div className="space-y-6">
      {/* Profile card */}
      <Card className="dark:bg-gray-900 dark:border-gray-800 overflow-hidden">
        <div className="bg-gradient-to-r from-purple-600/10 to-blue-600/10 dark:from-purple-900/20 dark:to-blue-900/20 p-6">
          <div className="flex items-start gap-4">
            <AvatarCircle
              name={member.name}
              url={member.avatar_url}
              size="lg"
            />
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold dark:text-gray-100 truncate">
                {member.name}
              </h3>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <Badge
                  className={cn(
                    "gap-1 border-0",
                    tierCfg.color
                  )}
                >
                  <TierIcon className="h-3 w-3" aria-hidden="true" />
                  {tierCfg.label}
                </Badge>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Member since{" "}
                  {new Date(member.joined_at).toLocaleDateString("en-US", {
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              </div>
            </div>
          </div>
        </div>
        <CardContent className="pt-6">
          <div
            className="grid grid-cols-2 md:grid-cols-4 gap-4"
            role="list"
            aria-label="Member statistics"
          >
            <StatCard
              label="Reputation Score"
              value={member.reputation_score}
              icon={<TrendingUp className="h-5 w-5" aria-hidden="true" />}
              color="text-purple-600 dark:text-purple-400"
            />
            <StatCard
              label="Badges Earned"
              value={member.badges.length}
              icon={<Award className="h-5 w-5" aria-hidden="true" />}
              color="text-amber-600 dark:text-amber-400"
            />
            <StatCard
              label="Connections"
              value={member.connections_suggested.length}
              icon={<Users className="h-5 w-5" aria-hidden="true" />}
              color="text-blue-600 dark:text-blue-400"
            />
            <StatCard
              label="Invite Codes"
              value={member.invite_codes.length}
              icon={<Gift className="h-5 w-5" aria-hidden="true" />}
              color="text-emerald-600 dark:text-emerald-400"
            />
          </div>
        </CardContent>
      </Card>

      {/* Badges */}
      {member.badges.length > 0 && (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
              <Award className="h-5 w-5 text-amber-500" aria-hidden="true" />
              Badges Earned
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="flex flex-wrap gap-3"
              role="list"
              aria-label="Earned badges"
            >
              {member.badges.map((badge) => (
                <div
                  key={badge.id}
                  role="listitem"
                  className="flex items-center gap-2 bg-gradient-to-r from-amber-50 to-yellow-50 dark:from-amber-900/20 dark:to-yellow-900/20 border border-amber-200 dark:border-amber-800 rounded-full px-4 py-2"
                >
                  <span className="text-lg" role="img" aria-label={badge.name}>
                    {badge.icon}
                  </span>
                  <span className="text-sm font-medium dark:text-gray-200">
                    {badge.name}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div
      role="listitem"
      className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 text-center"
    >
      <div className={cn("flex justify-center mb-2", color)}>{icon}</div>
      <p className="text-2xl font-bold tabular-nums dark:text-gray-100">
        {value}
      </p>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{label}</p>
    </div>
  );
}

// ── Member Dashboard - Onboarding Tab ───────────────────────────────────────

function OnboardingTab({ steps }: { steps: OnboardingStep[] }) {
  const completedCount = steps.filter((s) => s.completed).length;

  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardHeader>
        <CardTitle className="text-base dark:text-gray-100">
          7-Day Welcome Journey
        </CardTitle>
        <div className="mt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {completedCount} of {steps.length} completed
            </span>
            <span className="text-sm font-medium dark:text-gray-300">
              {steps.length > 0
                ? Math.round((completedCount / steps.length) * 100)
                : 0}
              %
            </span>
          </div>
          <Progress
            value={completedCount}
            max={steps.length}
            className="h-2"
            aria-label={`Onboarding progress: ${completedCount} of ${steps.length} steps completed`}
          />
        </div>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3" aria-label="Onboarding steps">
          {steps.map((step, idx) => (
            <li
              key={step.id}
              className={cn(
                "flex items-start gap-3 p-3 rounded-lg transition-colors",
                step.completed
                  ? "bg-emerald-50 dark:bg-emerald-900/10"
                  : "bg-gray-50 dark:bg-gray-800"
              )}
            >
              <div className="mt-0.5 shrink-0">
                {step.completed ? (
                  <CircleCheck
                    className="h-5 w-5 text-emerald-500"
                    aria-hidden="true"
                  />
                ) : (
                  <Circle
                    className="h-5 w-5 text-gray-300 dark:text-gray-600"
                    aria-hidden="true"
                  />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className="text-[10px] px-1.5 py-0 shrink-0"
                  >
                    Day {step.day}
                  </Badge>
                  <span
                    className={cn(
                      "text-sm font-medium",
                      step.completed
                        ? "line-through text-gray-400 dark:text-gray-500"
                        : "dark:text-gray-200"
                    )}
                  >
                    {step.label}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {step.description}
                </p>
              </div>
              <span className="sr-only">
                {step.completed ? "Completed" : "Not completed"}
              </span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

// ── Member Dashboard - Events Tab ───────────────────────────────────────────

function EventsTab({ events }: { events: CommunityEvent[] }) {
  return (
    <div className="space-y-4">
      {events.length === 0 ? (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-12 text-center">
            <Calendar
              className="h-10 w-10 mx-auto text-gray-300 dark:text-gray-600 mb-3"
              aria-hidden="true"
            />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No upcoming events at this time.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div role="list" aria-label="Upcoming community events">
          {events.map((event) => {
            const spotsLeft = event.spots_total - event.spots_taken;
            const almostFull = spotsLeft <= 5 && spotsLeft > 0;
            const full = spotsLeft <= 0;

            return (
              <Card
                key={event.id}
                role="listitem"
                className="dark:bg-gray-900 dark:border-gray-800 mb-4 overflow-hidden"
              >
                <div className="flex flex-col sm:flex-row">
                  {/* Date sidebar */}
                  <div className="sm:w-24 bg-gradient-to-b from-purple-600 to-indigo-600 p-4 flex sm:flex-col items-center justify-center gap-2 text-white">
                    <span className="text-xs uppercase tracking-wider opacity-80">
                      {new Date(event.date).toLocaleDateString("en-US", {
                        month: "short",
                      })}
                    </span>
                    <span className="text-2xl font-bold">
                      {new Date(event.date).getDate()}
                    </span>
                  </div>
                  {/* Content */}
                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Badge
                            className={cn(
                              "text-[10px] border-0",
                              EVENT_TYPE_COLORS[event.event_type] ??
                                "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                            )}
                          >
                            {event.event_type}
                          </Badge>
                          {almostFull && (
                            <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-0 text-[10px]">
                              Almost Full
                            </Badge>
                          )}
                          {full && (
                            <Badge className="bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 border-0 text-[10px]">
                              Full
                            </Badge>
                          )}
                        </div>
                        <h4 className="font-semibold dark:text-gray-100">
                          {event.title}
                        </h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          {event.description}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          <Clock
                            className="h-3 w-3 inline-block mr-1"
                            aria-hidden="true"
                          />
                          {new Date(event.date).toLocaleTimeString("en-US", {
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </p>
                        <p
                          className={cn(
                            "text-xs mt-1 font-medium tabular-nums",
                            almostFull
                              ? "text-red-600 dark:text-red-400"
                              : "text-gray-500 dark:text-gray-400"
                          )}
                        >
                          {spotsLeft > 0
                            ? `${spotsLeft} spots left`
                            : "Waitlist only"}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3">
                      <Button
                        size="sm"
                        disabled={event.is_registered || full}
                        variant={event.is_registered ? "outline" : "default"}
                        className={cn(
                          event.is_registered &&
                            "text-emerald-600 border-emerald-300 dark:text-emerald-400 dark:border-emerald-700"
                        )}
                        aria-label={
                          event.is_registered
                            ? `Registered for ${event.title}`
                            : `Register for ${event.title}`
                        }
                      >
                        {event.is_registered ? (
                          <>
                            <Check
                              className="h-4 w-4 mr-1"
                              aria-hidden="true"
                            />
                            Registered
                          </>
                        ) : full ? (
                          "Join Waitlist"
                        ) : (
                          "Register Now"
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Member Dashboard - Network Tab ──────────────────────────────────────────

function NetworkTab({
  connections,
}: {
  connections: ConnectionSuggestion[];
}) {
  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardHeader>
        <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-blue-500" aria-hidden="true" />
          Recommended Connections
        </CardTitle>
      </CardHeader>
      <CardContent>
        {connections.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-6">
            No connection recommendations yet. Complete your onboarding to
            unlock suggestions.
          </p>
        ) : (
          <div role="list" aria-label="Suggested connections" className="space-y-3">
            {connections.map((conn) => (
              <div
                key={conn.id}
                role="listitem"
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
              >
                <AvatarCircle
                  name={conn.name}
                  url={conn.avatar_url}
                  size="md"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium dark:text-gray-100 truncate">
                    {conn.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {conn.title} at {conn.company}
                  </p>
                  <p className="text-xs text-purple-600 dark:text-purple-400 mt-0.5">
                    {conn.match_reason}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">
                    {conn.mutual_connections} mutual
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-1 h-7 text-xs"
                    aria-label={`Connect with ${conn.name}`}
                  >
                    Connect
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Waitlist Section ────────────────────────────────────────────────────────

function WaitlistSection() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<WaitlistFormData>({
    email: "",
    company: "",
    role: "",
    referral_code: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [priorityScore, setPriorityScore] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: (data: WaitlistFormData) =>
      api.post("/insights/community/waitlist", data),
    onSuccess: (res) => {
      setSubmitted(true);
      setPriorityScore(
        (res.data as { priority_score?: number })?.priority_score ?? null
      );
      queryClient.invalidateQueries({ queryKey: ["community-stats"] });
    },
  });

  const handleChange = useCallback(
    (field: keyof WaitlistFormData) =>
      (e: React.ChangeEvent<HTMLInputElement>) => {
        setForm((prev) => ({ ...prev, [field]: e.target.value }));
      },
    []
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email || !form.company || !form.role) return;
    mutation.mutate(form);
  };

  if (submitted) {
    return (
      <Card className="dark:bg-gray-900 dark:border-gray-800 overflow-hidden">
        <div className="bg-gradient-to-r from-emerald-500 to-teal-500 p-8 text-center text-white">
          <CircleCheck
            className="h-12 w-12 mx-auto mb-4"
            aria-hidden="true"
          />
          <h3 className="text-xl font-bold mb-2">
            You&apos;re on the List!
          </h3>
          <p className="text-emerald-100">
            We&apos;ll review your application and reach out soon.
          </p>
          {priorityScore !== null && (
            <div className="mt-4 inline-flex items-center gap-2 bg-white/20 backdrop-blur-sm rounded-full px-4 py-2">
              <Zap className="h-4 w-4" aria-hidden="true" />
              <span className="text-sm font-medium">
                Priority Score: {priorityScore}
              </span>
            </div>
          )}
        </div>
      </Card>
    );
  }

  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardHeader>
        <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-purple-500" aria-hidden="true" />
          Join the Waitlist
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" aria-label="Waitlist application form">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="waitlist-email"
                className="block text-sm font-medium dark:text-gray-300 mb-1"
              >
                Work Email <span className="text-red-500">*</span>
              </label>
              <Input
                id="waitlist-email"
                type="email"
                placeholder="you@company.com"
                value={form.email}
                onChange={handleChange("email")}
                required
                aria-required="true"
                className="dark:bg-gray-800 dark:border-gray-700"
              />
            </div>
            <div>
              <label
                htmlFor="waitlist-company"
                className="block text-sm font-medium dark:text-gray-300 mb-1"
              >
                Company <span className="text-red-500">*</span>
              </label>
              <Input
                id="waitlist-company"
                type="text"
                placeholder="Your company"
                value={form.company}
                onChange={handleChange("company")}
                required
                aria-required="true"
                className="dark:bg-gray-800 dark:border-gray-700"
              />
            </div>
            <div>
              <label
                htmlFor="waitlist-role"
                className="block text-sm font-medium dark:text-gray-300 mb-1"
              >
                Role <span className="text-red-500">*</span>
              </label>
              <Input
                id="waitlist-role"
                type="text"
                placeholder="e.g. VP of Sales"
                value={form.role}
                onChange={handleChange("role")}
                required
                aria-required="true"
                className="dark:bg-gray-800 dark:border-gray-700"
              />
            </div>
            <div>
              <label
                htmlFor="waitlist-referral"
                className="block text-sm font-medium dark:text-gray-300 mb-1"
              >
                Referral Code
              </label>
              <Input
                id="waitlist-referral"
                type="text"
                placeholder="Optional"
                value={form.referral_code}
                onChange={handleChange("referral_code")}
                className="dark:bg-gray-800 dark:border-gray-700"
              />
            </div>
          </div>
          <Button
            type="submit"
            className="w-full sm:w-auto bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <div
                  className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"
                  aria-hidden="true"
                />
                Submitting...
              </>
            ) : (
              <>
                <ArrowRight className="h-4 w-4 mr-2" aria-hidden="true" />
                Apply Now
              </>
            )}
          </Button>
          {mutation.isError && (
            <p className="text-sm text-red-500" role="alert">
              Something went wrong. Please try again.
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

// ── Content Preview ─────────────────────────────────────────────────────────

function ContentPreview({
  content,
}: {
  content: ExclusiveContent[];
}) {
  if (content.length === 0) return null;

  return (
    <section aria-labelledby="content-heading">
      <div className="flex items-center gap-2 mb-4">
        <Eye className="h-5 w-5 text-purple-500" aria-hidden="true" />
        <h2
          id="content-heading"
          className="text-lg font-semibold dark:text-gray-100"
        >
          Exclusive Research
        </h2>
        <Badge className="bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 border-0 text-[10px]">
          Members Only
        </Badge>
      </div>
      <div
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        role="list"
        aria-label="Exclusive research content"
      >
        {content.map((item) => (
          <Card
            key={item.id}
            role="listitem"
            className={cn(
              "dark:bg-gray-900 dark:border-gray-800 overflow-hidden group transition-all",
              item.is_locked
                ? "opacity-75 hover:opacity-100"
                : "hover:shadow-lg hover:shadow-purple-500/5"
            )}
          >
            {/* Gradient top bar */}
            <div
              className="h-1 bg-gradient-to-r from-purple-500 to-blue-500"
              aria-hidden="true"
            />
            <CardContent className="pt-4">
              <div className="flex items-start justify-between mb-2">
                <Badge
                  variant="outline"
                  className="text-[10px] dark:border-gray-700"
                >
                  {item.category}
                </Badge>
                {item.is_locked && (
                  <Lock
                    className="h-4 w-4 text-gray-400 dark:text-gray-500"
                    aria-label="Locked - members only"
                  />
                )}
              </div>
              <h4 className="font-semibold text-sm dark:text-gray-100 mb-1 line-clamp-2">
                {item.title}
              </h4>
              <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3">
                {item.is_locked
                  ? "Join to unlock this exclusive content..."
                  : item.description}
              </p>
              <div className="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500">
                <span>
                  {new Date(item.published_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <span className="flex items-center gap-1">
                  <Eye className="h-3 w-3" aria-hidden="true" />
                  {item.read_count} reads
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

// ── Invite Management ───────────────────────────────────────────────────────

function InviteManagement({ inviteCodes }: { inviteCodes: InviteCode[] }) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const generateMutation = useMutation({
    mutationFn: () => api.post("/insights/community/invite-code"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community-stats"] });
    },
  });

  const copyToClipboard = useCallback(
    async (code: string) => {
      try {
        await navigator.clipboard.writeText(code);
        setCopiedCode(code);
        setTimeout(() => setCopiedCode(null), 2000);
      } catch {
        // Fallback: select text for manual copy
      }
    },
    []
  );

  return (
    <Card className="dark:bg-gray-900 dark:border-gray-800">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
            <Link2 className="h-5 w-5 text-indigo-500" aria-hidden="true" />
            Invite Management
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            aria-label="Generate new invite code"
          >
            {generateMutation.isPending ? (
              <div
                className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin"
                aria-hidden="true"
              />
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-1" aria-hidden="true" />
                Generate Code
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {inviteCodes.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-6">
            No invite codes yet. Generate one to invite colleagues.
          </p>
        ) : (
          <div className="space-y-3" role="list" aria-label="Your invite codes">
            {inviteCodes.map((invite) => (
              <div
                key={invite.code}
                role="listitem"
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800"
              >
                <code className="flex-1 text-sm font-mono bg-white dark:bg-gray-900 border dark:border-gray-700 rounded px-3 py-2 truncate">
                  {invite.code}
                </code>
                <div className="text-right shrink-0">
                  <p className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                    {invite.uses}/{invite.max_uses} used
                  </p>
                  <Progress
                    value={invite.uses}
                    max={invite.max_uses}
                    className="h-1 w-16 mt-1"
                    aria-label={`${invite.uses} of ${invite.max_uses} invite uses`}
                  />
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="shrink-0"
                  onClick={() => copyToClipboard(invite.code)}
                  aria-label={`Copy invite code ${invite.code}`}
                >
                  {copiedCode === invite.code ? (
                    <Check className="h-4 w-4 text-emerald-500" aria-hidden="true" />
                  ) : (
                    <Copy className="h-4 w-4" aria-hidden="true" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function CommunityPage() {
  const { data: stats, isLoading, error } = useCommunityStats();

  const spotsRemaining = stats?.spots_remaining ?? 0;
  const totalCapacity = stats?.max_capacity ?? 100;
  const joinedThisWeek = stats?.joined_this_week ?? 0;
  const waitlistCount = stats?.waitlist_count ?? 0;
  const member = stats?.member ?? null;
  const events = stats?.upcoming_events ?? [];
  const exclusiveContent = stats?.exclusive_content ?? [];

  return (
    <div className="space-y-6 pb-12">
      <h1 className="sr-only">Community Portal</h1>

      {/* Error state */}
      {error && (
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="py-8 text-center text-red-500 text-sm">
            Failed to load community data. Please try again.
          </CardContent>
        </Card>
      )}

      {/* 1. Hero Banner */}
      <HeroBanner
        spotsRemaining={spotsRemaining}
        totalCapacity={totalCapacity}
        isLoading={isLoading}
      />

      {/* 2. FOMO Ticker */}
      <FomoTicker
        spotsRemaining={spotsRemaining}
        joinedThisWeek={joinedThisWeek}
        waitlistCount={waitlistCount}
        isLoading={isLoading}
      />

      {/* 3. Member Dashboard (only for logged-in members) */}
      {isLoading ? (
        <SectionSkeleton />
      ) : member ? (
        <section aria-labelledby="dashboard-heading">
          <h2
            id="dashboard-heading"
            className="text-lg font-semibold dark:text-gray-100 mb-4 flex items-center gap-2"
          >
            <Shield className="h-5 w-5 text-purple-500" aria-hidden="true" />
            Member Dashboard
          </h2>
          <Tabs defaultValue="overview" className="w-full">
            <TabsList className="mb-4" aria-label="Dashboard sections">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
              <TabsTrigger value="events">Events</TabsTrigger>
              <TabsTrigger value="network">Network</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <OverviewTab member={member} />
            </TabsContent>

            <TabsContent value="onboarding">
              <OnboardingTab steps={member.onboarding_progress} />
            </TabsContent>

            <TabsContent value="events">
              <EventsTab events={events} />
            </TabsContent>

            <TabsContent value="network">
              <NetworkTab connections={member.connections_suggested} />
            </TabsContent>
          </Tabs>
        </section>
      ) : null}

      {/* 4. Waitlist Section */}
      <section id="waitlist-section" aria-labelledby="waitlist-heading">
        <h2
          id="waitlist-heading"
          className="text-lg font-semibold dark:text-gray-100 mb-4"
        >
          {member ? "Invite Others" : "Reserve Your Spot"}
        </h2>
        {member ? null : <WaitlistSection />}
      </section>

      {/* 5. Content Preview */}
      <ContentPreview content={exclusiveContent} />

      {/* 6. Invite Management (members only) */}
      {member && (
        <section aria-labelledby="invite-heading">
          <h2 id="invite-heading" className="sr-only">
            Invite Management
          </h2>
          <InviteManagement inviteCodes={member.invite_codes} />
        </section>
      )}
    </div>
  );
}
