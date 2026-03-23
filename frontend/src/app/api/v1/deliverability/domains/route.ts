import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json([
    { id: "dom-1", domain: "outreach.fortressflow.com", health_score: 95, warmup_progress: 100, total_sent: 8500, total_bounced: 85, created_at: "2026-02-01T00:00:00Z" },
    { id: "dom-2", domain: "mail.gengyve.com", health_score: 88, warmup_progress: 72, total_sent: 3200, total_bounced: 48, created_at: "2026-02-15T00:00:00Z" },
    { id: "dom-3", domain: "reach.fortressflow.io", health_score: 92, warmup_progress: 100, total_sent: 2862, total_bounced: 28, created_at: "2026-03-01T00:00:00Z" },
  ]);
}

export async function POST() {
  return NextResponse.json({
    id: "dom-new",
    domain: "new-domain.com",
    health_score: 100,
    warmup_progress: 0,
    total_sent: 0,
    total_bounced: 0,
    created_at: "2026-03-22T08:00:00Z",
  }, { status: 201 });
}
