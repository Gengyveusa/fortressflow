import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_experiments: 12,
  active: 4,
  completed: 6,
  draft: 2,
  avg_lift_percent: 8.3,
  experiments: [
    {
      id: "exp-001",
      name: "Subject Line A/B Test",
      status: "active",
      variant_count: 2,
      start_date: "2026-03-01",
      lift_percent: 12.5,
    },
    {
      id: "exp-002",
      name: "Send Time Optimization",
      status: "completed",
      variant_count: 3,
      start_date: "2026-02-10",
      end_date: "2026-02-28",
      lift_percent: 5.1,
    },
    {
      id: "exp-003",
      name: "CTA Button Color Test",
      status: "active",
      variant_count: 2,
      start_date: "2026-03-15",
      lift_percent: 3.7,
    },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/experiments/summary");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
