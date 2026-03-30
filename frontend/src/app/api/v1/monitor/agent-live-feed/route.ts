import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = [
  {
    id: "exec-001",
    agent: "groq-enrichment",
    action: "enrich_contact",
    status: "success",
    latency_ms: 142,
    timestamp: "2026-03-29T14:32:01Z",
    lead_id: "lead-4401",
  },
  {
    id: "exec-002",
    agent: "marketing-outreach",
    action: "send_sequence_email",
    status: "success",
    latency_ms: 310,
    timestamp: "2026-03-29T14:31:48Z",
    lead_id: "lead-4388",
  },
  {
    id: "exec-003",
    agent: "data-validator",
    action: "validate_email",
    status: "success",
    latency_ms: 89,
    timestamp: "2026-03-29T14:31:32Z",
    lead_id: "lead-4395",
  },
  {
    id: "exec-004",
    agent: "apollo-sync",
    action: "fetch_company_data",
    status: "error",
    latency_ms: 2150,
    timestamp: "2026-03-29T14:31:15Z",
    lead_id: "lead-4402",
  },
  {
    id: "exec-005",
    agent: "consent-manager",
    action: "check_gdpr_consent",
    status: "success",
    latency_ms: 54,
    timestamp: "2026-03-29T14:30:58Z",
    lead_id: "lead-4390",
  },
  {
    id: "exec-006",
    agent: "groq-enrichment",
    action: "enrich_company",
    status: "success",
    latency_ms: 198,
    timestamp: "2026-03-29T14:30:42Z",
    lead_id: "lead-4389",
  },
  {
    id: "exec-007",
    agent: "scoring-engine",
    action: "compute_lead_score",
    status: "success",
    latency_ms: 76,
    timestamp: "2026-03-29T14:30:25Z",
    lead_id: "lead-4401",
  },
  {
    id: "exec-008",
    agent: "marketing-outreach",
    action: "send_sequence_email",
    status: "throttled",
    latency_ms: 12,
    timestamp: "2026-03-29T14:30:10Z",
    lead_id: "lead-4378",
  },
  {
    id: "exec-009",
    agent: "dedup-agent",
    action: "merge_duplicates",
    status: "success",
    latency_ms: 430,
    timestamp: "2026-03-29T14:29:55Z",
    lead_id: "lead-4365",
  },
  {
    id: "exec-010",
    agent: "webhook-listener",
    action: "process_inbound_reply",
    status: "success",
    latency_ms: 165,
    timestamp: "2026-03-29T14:29:38Z",
    lead_id: "lead-4350",
  },
];

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/agent-live-feed");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
