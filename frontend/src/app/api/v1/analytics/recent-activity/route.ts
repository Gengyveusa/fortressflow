import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { id: 1, text: "Imported 150 leads from HubSpot CSV", time: "2 minutes ago", type: "lead" },
    { id: 2, text: "Sequence \"Cold Outreach — SaaS\" enrolled 42 new leads", time: "15 minutes ago", type: "sequence" },
    { id: 3, text: "Consent granted: sarah.chen@acmetech.io (email)", time: "28 minutes ago", type: "consent" },
    { id: 4, text: "Bounce detected: invalid@oldcompany.com", time: "1 hour ago", type: "bounce" },
    { id: 5, text: "Domain warmup completed: outreach.fortressflow.com", time: "2 hours ago", type: "warmup" },
    { id: 6, text: "New lead enriched: Marcus Rivera — VP Sales, TechCorp", time: "3 hours ago", type: "lead" },
    { id: 7, text: "Sequence \"Re-engagement\" reply rate hit 14%", time: "4 hours ago", type: "sequence" },
    { id: 8, text: "DNC list updated: +3 entries from compliance scan", time: "5 hours ago", type: "consent" },
  ]);
}
