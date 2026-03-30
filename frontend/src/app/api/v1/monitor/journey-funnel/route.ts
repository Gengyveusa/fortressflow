import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  stages: [
    { stage: "Discovered", count: 1247, pct_of_top: 100.0 },
    { stage: "Enriched", count: 980, pct_of_top: 78.6 },
    { stage: "Contacted", count: 654, pct_of_top: 52.4 },
    { stage: "Engaged", count: 234, pct_of_top: 18.8 },
    { stage: "Replied", count: 89, pct_of_top: 7.1 },
    { stage: "Meeting", count: 23, pct_of_top: 1.8 },
    { stage: "Won", count: 7, pct_of_top: 0.6 },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/journey-funnel");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
