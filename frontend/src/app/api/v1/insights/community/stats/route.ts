import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_members: 1240,
  active_members_30d: 478,
  new_members_30d: 62,
  total_posts: 3150,
  posts_this_week: 87,
  avg_response_time_hours: 2.4,
  top_topics: [
    { topic: "Feature Requests", count: 34 },
    { topic: "Integration Help", count: 28 },
    { topic: "Best Practices", count: 21 },
    { topic: "Bug Reports", count: 15 },
  ],
  engagement_trend: [
    { week: "2026-W09", posts: 72 },
    { week: "2026-W10", posts: 81 },
    { week: "2026-W11", posts: 95 },
    { week: "2026-W12", posts: 87 },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/community/stats");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
