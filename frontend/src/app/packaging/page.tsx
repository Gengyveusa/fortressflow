"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  ShieldCheck,
  ScanLine,
  CheckCircle2,
  Clock,
  Truck,
  Factory,
  Store,
  Leaf,
  AlertTriangle,
  Star,
  Gift,
  ChevronRight,
  Award,
  Heart,
  Info,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────

interface ProvenanceStep {
  id: string;
  label: string;
  description: string;
  timestamp: string;
  status: "completed" | "current" | "pending";
  location?: string;
}

interface Ingredient {
  name: string;
  purpose: string;
  safety_level: "safe" | "caution" | "allergen";
  allergens?: string[];
}

interface Certification {
  name: string;
  issuer: string;
  verified: boolean;
  expiry?: string;
}

interface HealthTip {
  title: string;
  description: string;
  category: string;
}

interface RewardInfo {
  points_earned: number;
  total_points: number;
  tier: string;
  next_tier: string;
  points_to_next: number;
  scan_streak: number;
}

interface PackagingData {
  product: {
    name: string;
    manufacturer: string;
    batch_id: string;
    production_date: string;
    expiry_date: string;
    category: string;
    sku: string;
    image_url?: string;
  };
  provenance: ProvenanceStep[];
  ingredients: Ingredient[];
  certifications: Certification[];
  health_tips: HealthTip[];
  rewards: RewardInfo;
  verified: boolean;
}

// ── Mock fallback data ──────────────────────────────────────

const MOCK_DATA: PackagingData = {
  product: {
    name: "FortressGuard Pro Toothpaste",
    manufacturer: "FortressFlow Oral Health Co.",
    batch_id: "BT-2026-03-0491",
    production_date: "2026-02-15",
    expiry_date: "2028-02-15",
    category: "Oral Care",
    sku: "FFG-PRO-150ML",
  },
  provenance: [
    {
      id: "1",
      label: "Manufacturing",
      description: "Produced at FDA-registered facility in Austin, TX",
      timestamp: "2026-02-15T08:00:00Z",
      status: "completed",
      location: "Austin, TX",
    },
    {
      id: "2",
      label: "Quality Check",
      description: "Passed 47-point quality inspection. Batch certified.",
      timestamp: "2026-02-16T14:30:00Z",
      status: "completed",
      location: "Austin, TX",
    },
    {
      id: "3",
      label: "Shipping",
      description: "Dispatched via cold-chain logistics to regional hub",
      timestamp: "2026-02-18T06:00:00Z",
      status: "completed",
      location: "Dallas, TX",
    },
    {
      id: "4",
      label: "Retail",
      description: "Received and shelved at authorized retail partner",
      timestamp: "2026-02-20T10:15:00Z",
      status: "current",
      location: "Your Local Store",
    },
  ],
  ingredients: [
    { name: "Sodium Fluoride", purpose: "Cavity protection", safety_level: "safe" },
    { name: "Hydrated Silica", purpose: "Gentle abrasive", safety_level: "safe" },
    { name: "Sorbitol", purpose: "Humectant", safety_level: "safe" },
    { name: "Sodium Lauryl Sulfate", purpose: "Foaming agent", safety_level: "caution" },
    { name: "Xylitol", purpose: "Sweetener & anti-bacterial", safety_level: "safe" },
    { name: "Menthol", purpose: "Flavor", safety_level: "safe" },
    { name: "Coconut Oil", purpose: "Natural moisturizer", safety_level: "allergen", allergens: ["Tree Nut (Coconut)"] },
  ],
  certifications: [
    { name: "ADA Accepted", issuer: "American Dental Association", verified: true, expiry: "2027-12-31" },
    { name: "FDA Cleared", issuer: "U.S. Food & Drug Administration", verified: true },
    { name: "Vegan", issuer: "Vegan Society", verified: true, expiry: "2027-06-30" },
    { name: "Cruelty-Free", issuer: "Leaping Bunny", verified: true, expiry: "2027-06-30" },
  ],
  health_tips: [
    { title: "Brush for 2 Minutes", description: "Divide your mouth into 4 quadrants and spend 30 seconds on each for thorough cleaning.", category: "technique" },
    { title: "Fluoride Boost", description: "Don't rinse immediately after brushing. Let the fluoride sit on your teeth for maximum protection.", category: "ingredient" },
    { title: "Replace Every 3 Months", description: "Swap your toothbrush or brush head every 3 months for optimal effectiveness.", category: "general" },
  ],
  rewards: {
    points_earned: 50,
    total_points: 1250,
    tier: "Silver",
    next_tier: "Gold",
    points_to_next: 750,
    scan_streak: 7,
  },
  verified: true,
};

// ── Provenance icon mapper ──────────────────────────────────

const PROVENANCE_ICONS: Record<string, React.ElementType> = {
  Manufacturing: Factory,
  "Quality Check": ShieldCheck,
  Shipping: Truck,
  Retail: Store,
};

// ── Scan Animation Component ────────────────────────────────

function ScanAnimation() {
  return (
    <div className="relative flex items-center justify-center w-32 h-32 mx-auto">
      <div className="absolute inset-0 rounded-2xl border-2 border-emerald-500/30 animate-ping" />
      <div className="absolute inset-2 rounded-xl border-2 border-emerald-500/50 animate-pulse" />
      <div className="relative z-10 flex items-center justify-center w-20 h-20 rounded-xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-emerald-500/40">
        <ScanLine className="w-10 h-10 text-emerald-400" />
      </div>
    </div>
  );
}

// ── Safety Badge helper ─────────────────────────────────────

function SafetyBadge({ level }: { level: string }) {
  if (level === "safe") {
    return (
      <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30">
        <CheckCircle2 className="w-3 h-3 mr-1" aria-hidden="true" /> Safe
      </Badge>
    );
  }
  if (level === "allergen") {
    return (
      <Badge className="bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30">
        <AlertTriangle className="w-3 h-3 mr-1" aria-hidden="true" /> Allergen
      </Badge>
    );
  }
  return (
    <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 hover:bg-amber-500/30">
      <Info className="w-3 h-3 mr-1" aria-hidden="true" /> Caution
    </Badge>
  );
}

// ── Tier color mapper ───────────────────────────────────────

function tierColor(tier: string): string {
  switch (tier.toLowerCase()) {
    case "bronze":
      return "text-orange-400";
    case "silver":
      return "text-gray-300";
    case "gold":
      return "text-yellow-400";
    case "platinum":
      return "text-cyan-300";
    default:
      return "text-gray-400";
  }
}

// ── Main Page ───────────────────────────────────────────────

export default function PackagingPage() {
  const [activeTab, setActiveTab] = useState("provenance");

  const { data, isLoading, error } = useQuery<PackagingData>({
    queryKey: ["packaging-auth"],
    queryFn: async () => {
      try {
        const res = await api.get("/insights/auth/packaging");
        return res.data;
      } catch {
        return MOCK_DATA;
      }
    },
    staleTime: 1000 * 60 * 5,
  });

  const pkg = data ?? MOCK_DATA;

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-6 px-4">
        <ScanAnimation />
        <div className="text-center space-y-2">
          <h2 className="text-lg font-semibold text-gray-100">Scanning Product...</h2>
          <p className="text-sm text-gray-400">Verifying authenticity via blockchain ledger</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* ── Hero ──────────────────────────────────────────── */}
      <section aria-label="Product verification hero" role="region" className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-900/40 via-gray-900 to-cyan-900/40 border border-emerald-500/20 p-8">
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative z-10 flex flex-col md:flex-row items-center gap-6">
          <ScanAnimation />
          <div className="text-center md:text-left space-y-2">
            <h1 className="text-2xl md:text-3xl font-bold text-gray-50">
              Verify Your Product
            </h1>
            <p className="text-gray-400 text-sm max-w-md">
              This product has been authenticated via NFC/QR connected packaging.
              Every step from manufacture to shelf is verified on-chain.
            </p>
            {pkg.verified && (
              <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-sm px-3 py-1">
                <ShieldCheck className="w-4 h-4 mr-1.5" aria-hidden="true" />
                <span className="sr-only">Product status:</span>
                Authenticity Verified
              </Badge>
            )}
          </div>
        </div>
      </section>

      {/* ── Product Card ─────────────────────────────────── */}
      <section aria-label="Product information" role="region">
      <Card className="dark:bg-gray-900 dark:border-gray-800">
        <CardHeader>
          <CardTitle className="text-base dark:text-gray-100">Product Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-6">
            {/* Image placeholder */}
            <div className="flex-shrink-0 w-full sm:w-40 h-40 rounded-xl bg-gradient-to-br from-gray-800 to-gray-700 border border-gray-700 flex items-center justify-center" role="img" aria-label={`Product image placeholder for ${pkg.product.name}`}>
              <div className="text-center space-y-2">
                <ShieldCheck className="w-10 h-10 text-emerald-500 mx-auto" aria-hidden="true" />
                <span className="text-[10px] text-gray-500 uppercase tracking-widest">Product Image</span>
              </div>
            </div>
            {/* Details */}
            <div className="flex-1 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Product</span>
                <p className="font-medium text-gray-100">{pkg.product.name}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Manufacturer</span>
                <p className="font-medium text-gray-100">{pkg.product.manufacturer}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Batch ID</span>
                <p className="font-mono text-gray-300">{pkg.product.batch_id}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">SKU</span>
                <p className="font-mono text-gray-300">{pkg.product.sku}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Produced</span>
                <p className="text-gray-300">{new Date(pkg.product.production_date).toLocaleDateString()}</p>
              </div>
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Expires</span>
                <p className="text-gray-300">{new Date(pkg.product.expiry_date).toLocaleDateString()}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      </section>

      {/* ── Tabbed Sections ──────────────────────────────── */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" aria-label="Product detail tabs">
        <TabsList className="w-full grid grid-cols-4 dark:bg-gray-800/60">
          <TabsTrigger value="provenance">Provenance</TabsTrigger>
          <TabsTrigger value="ingredients">Ingredients</TabsTrigger>
          <TabsTrigger value="certifications">Certifications</TabsTrigger>
          <TabsTrigger value="tips">Tips & Rewards</TabsTrigger>
        </TabsList>

        {/* ── Provenance Timeline ─────────────────────────── */}
        <TabsContent value="provenance">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100">Provenance Timeline</CardTitle>
              <CardDescription>Track this product from factory to shelf</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative pl-8" role="list" aria-label="Product provenance timeline">
                {/* vertical line */}
                <div className="absolute left-[15px] top-2 bottom-2 w-0.5 bg-gradient-to-b from-emerald-500 via-cyan-500 to-gray-700" />

                {pkg.provenance.map((step, i) => {
                  const Icon = PROVENANCE_ICONS[step.label] ?? CheckCircle2;
                  const isCompleted = step.status === "completed";
                  const isCurrent = step.status === "current";

                  return (
                    <div key={step.id} className="relative pb-8 last:pb-0" role="listitem">
                      {/* node */}
                      <div
                        className={`absolute -left-8 top-0.5 flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                          isCompleted
                            ? "bg-emerald-500/20 border-emerald-500 text-emerald-400"
                            : isCurrent
                            ? "bg-cyan-500/20 border-cyan-500 text-cyan-400 ring-4 ring-cyan-500/20"
                            : "bg-gray-800 border-gray-600 text-gray-500"
                        }`}
                      >
                        <Icon className="w-4 h-4" aria-hidden="true" />
                      </div>

                      <div className="ml-4">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-gray-100">{step.label}</h4>
                          {isCompleted && (
                            <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-[10px]">
                              Verified
                            </Badge>
                          )}
                          {isCurrent && (
                            <Badge className="bg-cyan-500/15 text-cyan-400 border-cyan-500/30 text-[10px]">
                              Current
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{step.description}</p>
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(step.timestamp).toLocaleString()}
                          </span>
                          {step.location && (
                            <span className="flex items-center gap-1">
                              <Store className="w-3 h-3" />
                              {step.location}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Ingredients ─────────────────────────────────── */}
        <TabsContent value="ingredients">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100">Ingredients</CardTitle>
              <CardDescription>Full ingredient list with safety information</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3" role="list" aria-label="Product ingredients">
                {pkg.ingredients.map((ing, i) => (
                  <div
                    key={i}
                    role="listitem"
                    className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-gray-600/50 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-gray-100">{ing.name}</span>
                        <SafetyBadge level={ing.safety_level} />
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{ing.purpose}</p>
                      {ing.allergens && ing.allergens.length > 0 && (
                        <div className="flex items-center gap-1 mt-1">
                          <AlertTriangle className="w-3 h-3 text-red-400" aria-hidden="true" />
                          <span className="sr-only">Allergen warning:</span>
                          <span className="text-[11px] text-red-400">
                            Contains: {ing.allergens.join(", ")}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Certifications ──────────────────────────────── */}
        <TabsContent value="certifications">
          <Card className="dark:bg-gray-900 dark:border-gray-800">
            <CardHeader>
              <CardTitle className="text-base dark:text-gray-100">Certifications</CardTitle>
              <CardDescription>Verified quality and compliance certifications</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" role="list" aria-label="Product certifications">
                {pkg.certifications.map((cert, i) => (
                  <div
                    key={i}
                    role="listitem"
                    className="relative overflow-hidden rounded-xl border border-gray-700/50 bg-gray-800/40 p-4 hover:border-emerald-500/30 transition-colors"
                  >
                    <div className="absolute top-3 right-3">
                      {cert.verified ? (
                        <>
                          <CheckCircle2 className="w-5 h-5 text-emerald-400" aria-hidden="true" />
                          <span className="sr-only">Verified</span>
                        </>
                      ) : (
                        <>
                          <Clock className="w-5 h-5 text-gray-500" aria-hidden="true" />
                          <span className="sr-only">Pending verification</span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <Award className="w-5 h-5 text-emerald-400" aria-hidden="true" />
                      </div>
                      <div>
                        <h4 className="font-medium text-sm text-gray-100">{cert.name}</h4>
                        <p className="text-xs text-gray-400">{cert.issuer}</p>
                      </div>
                    </div>
                    {cert.expiry && (
                      <p className="text-[11px] text-gray-500 mt-3">
                        Valid until {new Date(cert.expiry).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Tips & Rewards ──────────────────────────────── */}
        <TabsContent value="tips">
          <div className="space-y-4">
            {/* Health Tips */}
            <Card className="dark:bg-gray-900 dark:border-gray-800" role="region" aria-label="Personalized health tips">
              <CardHeader>
                <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                  <Heart className="w-4 h-4 text-pink-400" aria-hidden="true" />
                  Personalized Health Tips
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3" role="list" aria-label="Health tips">
                  {pkg.health_tips.map((tip, i) => (
                    <div
                      key={i}
                      role="listitem"
                      className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/40 border border-gray-700/50"
                    >
                      <div className="flex-shrink-0 mt-0.5 flex items-center justify-center w-6 h-6 rounded-full bg-pink-500/10 text-pink-400">
                        <Leaf className="w-3.5 h-3.5" aria-hidden="true" />
                      </div>
                      <div>
                        <h4 className="font-medium text-sm text-gray-100">{tip.title}</h4>
                        <p className="text-xs text-gray-400 mt-0.5">{tip.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Rewards */}
            <Card className="dark:bg-gray-900 dark:border-gray-800" role="region" aria-label="Scan rewards">
              <CardHeader>
                <CardTitle className="text-base dark:text-gray-100 flex items-center gap-2">
                  <Gift className="w-4 h-4 text-amber-400" aria-hidden="true" />
                  Scan Rewards
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Points earned banner */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-amber-900/30 to-yellow-900/20 border border-amber-500/20">
                  <div>
                    <p className="text-xs text-amber-400/80 uppercase tracking-wide">Points Earned This Scan</p>
                    <p className="text-2xl font-bold text-amber-300">+{pkg.rewards.points_earned}</p>
                  </div>
                  <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                    <Star className="w-4 h-4 text-amber-400" aria-hidden="true" />
                    <span className="text-sm font-semibold text-amber-300">
                      {pkg.rewards.total_points} pts
                    </span>
                  </div>
                </div>

                {/* Tier progress */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className={`font-semibold ${tierColor(pkg.rewards.tier)}`}>
                      {pkg.rewards.tier} Tier
                    </span>
                    <span className="text-gray-400 flex items-center gap-1">
                      {pkg.rewards.next_tier}
                      <ChevronRight className="w-3 h-3" />
                    </span>
                  </div>
                  <Progress
                    value={pkg.rewards.total_points}
                    max={pkg.rewards.total_points + pkg.rewards.points_to_next}
                    className="h-2"
                    aria-label={`Rewards progress: ${pkg.rewards.tier} tier`}
                    aria-valuenow={pkg.rewards.total_points}
                    aria-valuemin={0}
                    aria-valuemax={pkg.rewards.total_points + pkg.rewards.points_to_next}
                  />
                  <p className="text-xs text-gray-500">
                    {pkg.rewards.points_to_next} points to {pkg.rewards.next_tier}
                  </p>
                </div>

                {/* Streak */}
                <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/40 border border-gray-700/50" aria-label={`${pkg.rewards.scan_streak} day scan streak`}>
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-orange-500/10 text-orange-400">
                    <span className="text-lg font-bold">{pkg.rewards.scan_streak}</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-100">Day Scan Streak</p>
                    <p className="text-xs text-gray-400">Keep scanning daily to earn bonus points!</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="text-center py-4" aria-label="Page footer">
        <p className="text-xs text-gray-600">
          Verification powered by FortressFlow Connected Packaging
        </p>
      </footer>
    </div>
  );
}
