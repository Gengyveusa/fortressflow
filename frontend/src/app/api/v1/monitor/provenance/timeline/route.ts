import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function GET(req: NextRequest) {
  try {
    return await proxyToBackend(req, "/api/v1/monitor/provenance/timeline");
  } catch {
    return NextResponse.json({ timeline: [], error: "Backend unavailable" }, { status: 502 });
  }
}
