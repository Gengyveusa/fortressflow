import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  lead_id: "lead-4401",
  lead_name: "Sarah Chen",
  company: "Nextera Analytics",
  events: [
    {
      event: "imported",
      source: "csv_import",
      timestamp: "2026-03-10T09:15:00Z",
      details: "Imported from Q1 target list batch",
    },
    {
      event: "enriched",
      source: "groq-enrichment",
      timestamp: "2026-03-10T09:16:12Z",
      details: "Added title: VP of Engineering, company size: 150",
    },
    {
      event: "validated",
      source: "data-validator",
      timestamp: "2026-03-10T09:16:45Z",
      details: "Email verified, deliverability score: 97",
    },
    {
      event: "consent_checked",
      source: "consent-manager",
      timestamp: "2026-03-10T09:17:02Z",
      details: "GDPR consent status: opted-in via webform",
    },
    {
      event: "sequence_started",
      source: "marketing-outreach",
      timestamp: "2026-03-12T08:00:00Z",
      details: "Enrolled in sequence: Engineering Leaders Q1",
    },
    {
      event: "email_opened",
      source: "marketing-outreach",
      timestamp: "2026-03-12T14:22:33Z",
      details: "Opened email step 1, device: desktop",
    },
    {
      event: "replied",
      source: "webhook-listener",
      timestamp: "2026-03-13T10:05:17Z",
      details: "Positive reply: interested in a demo next week",
    },
    {
      event: "meeting_booked",
      source: "campaign-scheduler",
      timestamp: "2026-03-13T11:30:00Z",
      details: "Demo scheduled for 2026-03-18 at 2:00 PM EST",
    },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/journey-timeline");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
