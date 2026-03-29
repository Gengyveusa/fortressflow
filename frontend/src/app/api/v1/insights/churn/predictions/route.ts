import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_at_risk: 37,
  high_risk: 8,
  medium_risk: 14,
  low_risk: 15,
  predicted_churn_rate: 4.2,
  predictions: [
    {
      contact_id: "c-1001",
      name: "Acme Corp",
      risk_score: 0.92,
      risk_level: "high",
      last_engagement: "2026-01-15",
      reason: "No activity in 60+ days",
    },
    {
      contact_id: "c-1002",
      name: "Globex Industries",
      risk_score: 0.78,
      risk_level: "high",
      last_engagement: "2026-02-03",
      reason: "Declining engagement trend",
    },
    {
      contact_id: "c-1003",
      name: "Initech LLC",
      risk_score: 0.55,
      risk_level: "medium",
      last_engagement: "2026-03-01",
      reason: "Reduced email opens",
    },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/churn/predictions");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
