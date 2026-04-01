import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/provenance");
  } catch {
    return NextResponse.json(
      {
        source_breakdown: {},
        enrichment_coverage: {
          total_leads: 0,
          enriched: 0,
          enriched_pct: 0,
          verified_phone: 0,
          verified_email: 0,
          crm_synced: 0,
        },
        provenance_chain: [],
        error: "Backend unavailable",
      },
      { status: 502 },
    );
  }
}
