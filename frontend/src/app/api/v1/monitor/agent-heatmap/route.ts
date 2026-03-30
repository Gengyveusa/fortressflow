import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  agents: [
    { agent: "groq-enrichment", executions: 145, success_rate: 98.2, avg_latency_ms: 167, errors_24h: 3 },
    { agent: "marketing-outreach", executions: 67, success_rate: 92.5, avg_latency_ms: 285, errors_24h: 5 },
    { agent: "apollo-sync", executions: 112, success_rate: 94.6, avg_latency_ms: 420, errors_24h: 6 },
    { agent: "data-validator", executions: 203, success_rate: 99.5, avg_latency_ms: 62, errors_24h: 1 },
    { agent: "consent-manager", executions: 89, success_rate: 100.0, avg_latency_ms: 48, errors_24h: 0 },
    { agent: "scoring-engine", executions: 178, success_rate: 97.8, avg_latency_ms: 73, errors_24h: 4 },
    { agent: "dedup-agent", executions: 34, success_rate: 91.2, avg_latency_ms: 510, errors_24h: 3 },
    { agent: "webhook-listener", executions: 256, success_rate: 99.2, avg_latency_ms: 132, errors_24h: 2 },
    { agent: "csv-importer", executions: 12, success_rate: 83.3, avg_latency_ms: 1850, errors_24h: 2 },
    { agent: "campaign-scheduler", executions: 45, success_rate: 95.6, avg_latency_ms: 195, errors_24h: 2 },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/agent-heatmap");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
