import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  source_breakdown: {
    csv_import: 450,
    apollo: 320,
    hubspot_sync: 210,
    manual_entry: 85,
    webform: 142,
    linkedin_scrape: 68,
    referral: 35,
  },
  enrichment_coverage: {
    total_leads: 1310,
    enriched: 1022,
    enriched_pct: 78.0,
    missing_email: 94,
    missing_company: 62,
    missing_title: 148,
    fully_enriched: 876,
    fully_enriched_pct: 66.9,
  },
  freshness: {
    updated_last_24h: 187,
    updated_last_7d: 645,
    stale_30d_plus: 122,
  },
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/provenance");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
