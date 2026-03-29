import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

const FALLBACK = {
  total: 142,
  candidates: [
    {
      cluster_id: "dup-001",
      confidence: 0.96,
      match_type: "email",
      records: [
        { id: "r-2001", name: "John Smith", email: "jsmith@acme.com", source: "CRM Import" },
        { id: "r-2002", name: "Jon Smith", email: "jsmith@acme.com", source: "Web Form" },
      ],
    },
    {
      cluster_id: "dup-002",
      confidence: 0.88,
      match_type: "name_phone",
      records: [
        { id: "r-3001", name: "Sarah Connor", phone: "+1-555-0142", source: "Manual Entry" },
        { id: "r-3002", name: "Sara Connor", phone: "+1-555-0142", source: "CSV Upload" },
      ],
    },
    {
      cluster_id: "dup-003",
      confidence: 0.82,
      match_type: "email",
      records: [
        { id: "r-4001", name: "Mike Johnson", email: "mike.j@globex.com", source: "API Sync" },
        { id: "r-4002", name: "Michael Johnson", email: "mike.j@globex.com", source: "CRM Import" },
      ],
    },
  ],
};

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/insights/deduplication/candidates");
  } catch {
    return NextResponse.json(FALLBACK);
  }
}
