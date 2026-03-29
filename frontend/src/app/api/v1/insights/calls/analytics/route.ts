import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_calls: 384,
  calls_this_week: 47,
  avg_duration_minutes: 18.5,
  avg_sentiment_score: 0.72,
  outcome_breakdown: {
    positive: 198,
    neutral: 124,
    negative: 62,
  },
  top_keywords: [
    { keyword: "pricing", count: 89 },
    { keyword: "onboarding", count: 67 },
    { keyword: "integration", count: 54 },
    { keyword: "timeline", count: 41 },
    { keyword: "support", count: 38 },
  ],
  weekly_trend: [
    { week: "2026-W09", calls: 39, avg_sentiment: 0.68 },
    { week: "2026-W10", calls: 44, avg_sentiment: 0.71 },
    { week: "2026-W11", calls: 52, avg_sentiment: 0.74 },
    { week: "2026-W12", calls: 47, avg_sentiment: 0.72 },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/calls/analytics");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
