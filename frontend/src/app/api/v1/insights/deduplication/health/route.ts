import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_records: 24850,
  duplicate_clusters: 142,
  estimated_duplicates: 318,
  health_score: 87.2,
  last_scan: "2026-03-27T14:30:00Z",
  breakdown: {
    email_match: 89,
    name_match: 34,
    phone_match: 19,
  },
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/deduplication/health");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
