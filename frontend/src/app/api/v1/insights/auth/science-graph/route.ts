import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total_nodes: 1856,
  total_edges: 4312,
  clusters: 24,
  avg_connections_per_node: 2.3,
  top_entities: [
    { id: "ent-001", label: "Machine Learning", type: "topic", connections: 87 },
    { id: "ent-002", label: "Data Pipeline", type: "technology", connections: 64 },
    { id: "ent-003", label: "NLP", type: "topic", connections: 52 },
    { id: "ent-004", label: "Feature Engineering", type: "process", connections: 41 },
  ],
  recent_updates: [
    { date: "2026-03-27", nodes_added: 12, edges_added: 28 },
    { date: "2026-03-26", nodes_added: 8, edges_added: 19 },
    { date: "2026-03-25", nodes_added: 15, edges_added: 34 },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/auth/science-graph");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
